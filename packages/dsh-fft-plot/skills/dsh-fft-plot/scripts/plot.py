#!/usr/bin/env python3
"""ft-plot 入口：spec(JSON) → 独立 SVG。

用法：
    python3 plot.py --spec spec.json --out /abs/path/chart.svg
    python3 plot.py --spec spec.json --out chart.svg --theme poster --width 1000

产物是自包含 SVG（无外链、无脚本、浅色底），可直接写进 Markdown 图片语法内联显示。
只依赖 Python 标准库。

**布局原则**：头部（chip/标题/副标题）与底部（说明/结论/页脚）都走同一个游标顺序排布，
任何元素都不自己算 y 坐标。上一版让 `legend` 自己贴绘图区底边，结果和第一条结论撞在
一起；游标是唯一能防止这类重叠的写法。

这些头部元素全是可选的——图在聊天流中间时，前后已有文字说明，不传就不会占位，
绘图区自动上移占满。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ftplot import charts, spec as specmod, theme as thememod  # noqa: E402
from ftplot.canvas import Svg, text_width, wrap  # noqa: E402

MARGIN = 60
NOTE_STEP = 27          # 结论行行距
LEGEND_STEP = 26        # 图内说明行高
HEADER_GAP = 26         # 头部与绘图区的间距
BOTTOM_GAP = 20         # 绘图区与底部说明的间距
FOOTER_H = 54           # 页脚高度（分隔线 + 两行小字）
#: x 轴标签占用的高度：标签画在绘图区底边之下 21px，字高约 13px，再加 12px 呼吸。
#: 绘图区高度必须先扣掉它，否则底部的说明行会紧贴横轴标签——只有 9px 间距时，
#: 12.5px 的字高就已经和标签糊在一起了。
XAXIS_H = 46
MIN_CHART_H = 170       # 绘图区最小高度，低于此值直接失败而不是画出糊掉的图


def main():
    ap = argparse.ArgumentParser(description='render a JSON chart spec into standalone SVG')
    ap.add_argument('--spec', required=True, help='spec JSON path')
    ap.add_argument('--out', required=True, help='output SVG path')
    ap.add_argument('--theme', default=None, help='override spec theme (paper/poster/slate)')
    ap.add_argument('--width', type=int, default=None)
    ap.add_argument('--height', type=int, default=None)
    args = ap.parse_args()

    spec = specmod.load(args.spec)
    rows = specmod.rows_of(spec)
    theme = thememod.load(args.theme or spec.get('theme', 'paper'))
    width = args.width or int(spec.get('width', 1200))
    height = args.height or int(spec.get('height', 700))

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
        lines = wrap(str(title), 26, width - 2 * MARGIN)
        cursor = svg.text_block(MARGIN, cursor + 24, lines, size=26, fill=theme['ink'],
                                weight='bold', line_height=37)

    subtitle = spec.get('subtitle')
    if subtitle:
        sub_lines = wrap(str(subtitle), 14.5, width - 2 * MARGIN)
        cursor = svg.text_block(MARGIN, cursor + 22, sub_lines, size=14.5,
                                fill=theme['mute'], line_height=22)

    has_header = bool(chip or title or subtitle)
    chart_top = cursor + (HEADER_GAP if has_header else 8)

    # ---------------- 底部：先精确算高，再倒推绘图区高度
    legend = spec.get('legend')
    notes = [str(n) for n in (spec.get('notes') or [])]
    legend_h = LEGEND_STEP if legend else 0
    notes_h = len(notes) * NOTE_STEP
    notes_gap = 12 if (legend and notes) else 0

    footer_top = height - FOOTER_H
    bottom_top = footer_top - (legend_h + notes_gap + notes_h)
    if legend or notes:
        bottom_top -= BOTTOM_GAP
    # 绘图区高度要扣掉 x 轴标签的地盘，否则底边就是标签基线，标签会压到说明行上。
    # 横条图与表格没有 x 轴标签，不扣这 46px，把空间还给图形本身。
    axis_h = XAXIS_H if spec['chart'].get('type') in ('line', 'bar') else 0
    chart_h = bottom_top - chart_top - axis_h

    if chart_h < MIN_CHART_H:
        raise SystemExit(
            f'chart area too short ({chart_h:.0f}px < {MIN_CHART_H}px): '
            f'drop the title/subtitle/notes for an inline chart, or pass a taller --height')
    if chart_h <= 0:
        raise SystemExit(f'chart area is negative ({chart_h:.0f}px): lower the header or notes')

    charts.render(svg, (MARGIN, chart_top, width - 2 * MARGIN, chart_h), spec['chart'], rows)

    # ---------------- 底部内容：一个游标顺序排，绝不重叠
    y = bottom_top + BOTTOM_GAP
    if legend:
        svg.text(MARGIN, y + 10, str(legend), size=12.5, fill=theme['mute'])
        y += LEGEND_STEP
    if legend and notes:
        y += notes_gap
    for raw in notes:
        text, size, fill, weight = _note_style(raw, theme)
        svg.text(MARGIN, y + size, text, size=size, fill=fill, weight=weight)
        y += NOTE_STEP

    # ---------------- 页脚（固定贴底）
    svg.line(MARGIN, footer_top, width - MARGIN, footer_top, theme['line'], 1)
    sources = spec.get('sources') or []
    if sources:
        svg.text(MARGIN, footer_top + 20,
                 '数据来源 FTShare 接口：' + ' / '.join(map(str, sources)),
                 size=11.5, fill=theme['mute'])
    if spec.get('sample'):
        svg.text(MARGIN, footer_top + 38, str(spec['sample']), size=11.5, fill=theme['mute'])

    size = svg.save(args.out)
    print(f'{args.out}  ({size} bytes, {width}x{height}, {len(rows)} rows, '
          f'theme={theme["name"]}, chart_h={chart_h:.0f})')


def _note_style(raw, theme):
    """结论行前缀：`**` 加粗主结论、`!` 强调色、`*` 小字注释，其余为普通灰字。"""
    if raw.startswith('**'):
        return raw.strip('*'), 16, theme['ink'], 'bold'
    if raw.startswith('!'):
        return raw[1:], 16, theme['up'], 'bold'
    if raw.startswith('*'):
        return raw[1:], 13, theme['mute'], 'normal'
    return raw, 14.5, theme['mute'], 'normal'


if __name__ == '__main__':
    main()
