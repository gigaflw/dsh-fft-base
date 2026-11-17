#!/usr/bin/env python3
"""ft-plot 入口：spec(JSON) → 独立 SVG。

用法：
    python3 plot.py --spec spec.json --out /abs/path/chart.svg
    python3 plot.py --spec spec.json --out chart.svg --theme poster --width 1000
    python3 plot.py --tokens [--theme paper]        # 打印当前主题的色板/字号/几何

产物是自包含 SVG（无外链、无脚本、浅色底），可直接写进 Markdown 图片语法内联显示。
只依赖 Python 标准库。

**布局原则**：头部（chip/标题/副标题）、底部（说明/结论/页脚）与横轴高度都参与
"先量后排"：文本先按画布宽度折行、算出真实高度，再倒推绘图区。上一版把
`legend`/`notes` 当固定行数、把"哪些图型有横轴"写死成图型名单，结果长文本跑出
画布、新图型的横轴标签压到说明行上；现在两者都由 `charts.py` 的图型元数据和
文本折行决定。
"""
import argparse
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ftplot import charts, spec as specmod, theme as thememod  # noqa: E402
from ftplot.canvas import Svg, text_width, wrap  # noqa: E402

MARGIN = 60
HEADER_GAP = 26         # 头部与绘图区的间距
BOTTOM_GAP = 20         # 绘图区与底部说明的间距
XAXIS_H = 46            # 横轴标签默认占用的高度（图型可声明更小）
MIN_CHART_H = 170       # 绘图区最小高度，低于此值直接失败而不是画出糊掉的图
MIN_WIDTH = 360         # 两侧留白之外至少要放得下一列标签
FOOTER_LINE_H = 18      # 页脚每行高度

#: 结论行前缀 → (字号, 颜色键, 字重, 行高)
_NOTE_STYLES = {
    '**': (16, 'ink', 'bold', 26),
    '!': (16, 'up', 'bold', 26),
    '*': (13, 'mute', 'normal', 20),
    '': (14.5, 'mute', 'normal', 23),
}


def _wrapped(text, size, width):
    """折行；空文本返回空列表。"""
    if text is None or str(text) == '':
        return []
    return wrap(str(text), size, width)


def _bottom_blocks(spec, theme, width):
    """底部说明块：每块含折行后的行、字号、颜色、字重、行高。"""
    blocks = []

    def add(text, style):
        lines = _wrapped(text, style[0], width)
        if lines:
            blocks.append({'lines': lines, 'size': style[0], 'fill': theme[style[1]],
                           'weight': style[2], 'step': style[3]})

    legend = spec.get('legend')
    if legend:
        add(legend, (12.5, 'mute', 'normal', 20))
    for raw in (spec.get('notes') or []):
        add(_note_text(raw), _note_style(raw))
    return blocks


def _note_style(raw):
    raw = str(raw)
    for prefix in ('**', '!', '*'):
        if raw.startswith(prefix):
            return _NOTE_STYLES[prefix]
    return _NOTE_STYLES['']


def _note_text(raw):
    raw = str(raw)
    for prefix in ('**', '!', '*'):
        if raw.startswith(prefix):
            return raw[len(prefix):].strip('*')
    return raw


def _footer_lines(spec, width):
    """页脚文本行（数据来源与样本口径），先折行再定页脚高度。"""
    lines = []
    sources = spec.get('sources') or []
    if sources:
        text = '数据来源 FTShare 接口：' + ' / '.join(map(str, sources))
        lines.extend(_wrapped(text, 11.5, width))
    sample = spec.get('sample')
    if sample:
        lines.extend(_wrapped(sample, 11.5, width))
    return lines


def _tokens(args):
    """打印当前主题的配色、字号与几何常量，供模型手绘 SVG 时引用真值。"""
    theme = thememod.load(args.theme or 'paper')
    width = int(args.width or 1200)
    height = int(args.height or 700)
    payload = {
        'theme': theme['name'],
        'themes': sorted(thememod.THEMES),
        'charts': sorted(charts.CHARTS),
        'canvas': {'width': width, 'height': height, 'margin': MARGIN,
                   'header_gap': HEADER_GAP, 'bottom_gap': BOTTOM_GAP,
                   'xaxis_h': XAXIS_H, 'min_chart_h': MIN_CHART_H,
                   'content_width': width - 2 * MARGIN},
        'colors': {key: theme[key] for key in
                   ('bg', 'card', 'ink', 'mute', 'line', 'up', 'down', 'neutral', 'accent', 'band')},
        'series': list(theme['series']),
        'fonts': {'family': theme['body_font'], 'title_family': theme['title_font']},
        'type_scale': {'title': 26, 'subtitle': 14.5, 'body': 13.5, 'small': 12.5,
                       'tick': 12.5, 'note_bold': 16, 'note_small': 13},
        'chart_types': {kind: {'x_axis': charts.needs_x_axis(kind)} for kind in sorted(charts.CHARTS)},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description='render a JSON chart spec into standalone SVG')
    parser.add_argument('--spec', help='spec JSON path')
    parser.add_argument('--out', help='output SVG path')
    parser.add_argument('--out-dir',
                        help='write <dir>/<slug>-<hash8>.svg instead of --out; hash covers '
                             'spec/rows/theme/size so the same chart keeps the same file')
    parser.add_argument('--slug', default='chart',
                        help='file name prefix for --out-dir (default: chart)')
    parser.add_argument('--theme', default=None, help='override spec theme (paper/ashare/poster/slate)')
    parser.add_argument('--width', type=int, default=None)
    parser.add_argument('--height', type=int, default=None)
    parser.add_argument('--tokens', action='store_true',
                        help='print theme colors, type scale and layout constants as JSON')
    args = parser.parse_args(argv)

    if args.tokens:
        _tokens(args)
        return 0
    if not args.spec or (not args.out and not args.out_dir):
        parser.error('--spec and one of --out/--out-dir are required unless --tokens is used')
    if args.out and args.out_dir:
        parser.error('pass either --out or --out-dir, not both')

    spec = specmod.load(args.spec)
    rows = specmod.rows_of(spec)
    theme = thememod.load(args.theme or spec.get('theme', 'paper'))
    width = int(args.width or spec.get('width', 1200))
    height = int(args.height or spec.get('height', 700))
    if width < MIN_WIDTH:
        raise SystemExit(f'canvas width {width}px is too small: at least {MIN_WIDTH}px '
                         '(raise --width / spec width, or drop the chart)')
    if height < 320:
        raise SystemExit(f'canvas height {height}px is too small: at least 320px '
                         '(raise --height / spec height)')

    if args.out_dir:
        # 固定产物目录（如 <workspace>/.dsh/plots）时由内容决定文件名：
        # 同一张图重复生成不会改名，旧消息的引用也不会被后一次渲染覆盖。
        fingerprint = json.dumps(
            {'spec': {k: v for k, v in spec.items() if k != '_dir'},
             'rows': rows, 'theme': theme['name'], 'width': width, 'height': height},
            sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')
        digest = hashlib.sha256(fingerprint).hexdigest()[:8]
        slug = re.sub(r'[^\w\-]+', '-', str(args.slug)).strip('-') or 'chart'
        args.out = os.path.join(os.path.expanduser(args.out_dir), f'{slug}-{digest}.svg')

    chart_cfg = spec['chart']
    svg = Svg(width, height, theme)
    cursor = MARGIN

    # ---------------- 头部（全部可选）
    chip = spec.get('chip')
    if chip:
        tone = charts.resolve_color(theme, spec.get('chip_tone'), 'down')
        label = str(chip)
        chip_w = text_width(label, 13) + 30
        svg.rect(MARGIN, cursor, chip_w, 30, tone, rx=15, opacity=0.12)
        svg.text(MARGIN + chip_w / 2, cursor + 15, label, size=13, fill=tone,
                 weight='bold', anchor='middle', baseline='middle')
        cursor += 46

    title = spec.get('title')
    if title:
        lines = _wrapped(title, 26, width - 2 * MARGIN)
        cursor = svg.text_block(MARGIN, cursor + 24, lines, size=26, fill=theme['ink'],
                                weight='bold', line_height=37)

    subtitle = spec.get('subtitle')
    if subtitle:
        lines = _wrapped(subtitle, 14.5, width - 2 * MARGIN)
        cursor = svg.text_block(MARGIN, cursor + 22, lines, size=14.5,
                                fill=theme['mute'], line_height=22)

    has_header = bool(chip or title or subtitle)
    chart_top = cursor + (HEADER_GAP if has_header else 8)

    # ---------------- 底部：先量后排列，再倒推绘图区
    blocks = _bottom_blocks(spec, theme, width - 2 * MARGIN)
    blocks_h = sum(len(block['lines']) * block['step'] for block in blocks)
    blocks_h += 4 * max(0, len(blocks) - 1)
    footer_lines = _footer_lines(spec, width - 2 * MARGIN)
    footer_h = (14 + FOOTER_LINE_H * len(footer_lines)) if footer_lines else 0
    footer_top = height - footer_h
    bottom_gap = BOTTOM_GAP if blocks else 8
    chart_bottom = footer_top - bottom_gap - blocks_h
    axis_h = charts.x_axis_height(chart_cfg.get('type'), XAXIS_H)
    chart_h = chart_bottom - chart_top - axis_h

    if chart_h <= 0:
        raise SystemExit(
            f'chart area is negative ({chart_h:.0f}px): canvas {width}x{height} is too short '
            'for this header/notes/footer; raise --height or drop title/subtitle/notes')
    if chart_h < MIN_CHART_H:
        raise SystemExit(
            f'chart area too short ({chart_h:.0f}px < {MIN_CHART_H}px): '
            'drop the title/subtitle/notes for an inline chart, or pass a taller --height')

    charts.render(svg, (MARGIN, chart_top, width - 2 * MARGIN, chart_h), chart_cfg, rows)

    # ---------------- 底部内容：单个游标顺序排，绝不重叠
    y = chart_bottom + bottom_gap
    for block in blocks:
        for index, line in enumerate(block['lines']):
            svg.text(MARGIN, y + block['size'] + index * block['step'], line,
                     size=block['size'], fill=block['fill'], weight=block['weight'])
        y += len(block['lines']) * block['step'] + 4

    # ---------------- 页脚（贴底、按折行后的真实高度）
    if footer_lines:
        svg.line(MARGIN, footer_top, width - MARGIN, footer_top, theme['line'], 1)
        for index, line in enumerate(footer_lines):
            svg.text(MARGIN, footer_top + 18 + index * FOOTER_LINE_H, line,
                     size=11.5, fill=theme['mute'])

    size = svg.save(args.out)
    print(f'{args.out}  ({size} bytes, {width}x{height}, {len(rows)} rows, '
          f'theme={theme["name"]}, chart_h={chart_h:.0f})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
