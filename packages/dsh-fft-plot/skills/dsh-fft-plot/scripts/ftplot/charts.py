"""图型注册表。**这是唯一的扩展点。**

新增一种图，只做两件事：

1. 在下面写一个函数并加 `@chart('名字')` 装饰器；
2. 在 SKILL.md 的图型表里加一行（给模型看的字段说明）。

函数签名固定为 `(c, rect, cfg, rows)`：

- `c`    —— `canvas.Svg`，画布；`c.t[...]` 取主题色
- `rect` —— `(x, y, w, h)` 绘图区像素矩形，已避开标题与页脚
- `cfg`  —— spec 里 `chart:` 的内容，字段由本图型自己定义
- `rows` —— 数据行 `list[dict]`

约定：**列名缺失或类型不符必须报错**，绝不静默丢行——金融图上少一根线而不报错，
比直接失败更危险。颜色用 `resolve_color()`，既接受主题键也接受 `#RRGGBB`。
"""
import math

from .canvas import (Axes, fmt_compact, fmt_date_label, fmt_num, fmt_pct, has_multiple_years,
                      nice_ticks, text_width)

#: 图型注册表。键是 `chart.type` 的取值。
CHARTS = {}


def chart(name):
    """把一个函数登记成 `chart.type = name` 的渲染器。"""
    def deco(fn):
        CHARTS[name] = fn
        return fn
    return deco


def render(c, rect, cfg, rows):
    """按 `cfg['type']` 分派。未知类型列出全部可用值，便于直接改正。"""
    kind = cfg.get('type')
    if kind is None:
        raise ValueError("chart.type is required; available: " + ", ".join(sorted(CHARTS)))
    if kind not in CHARTS:
        raise KeyError(f"unknown chart.type {kind!r}; available: " + ", ".join(sorted(CHARTS)))
    if not rows:
        raise ValueError(f'chart type {kind!r} needs rows, but the data is empty')
    return CHARTS[kind](c, rect, cfg, rows)


# ---------------------------------------------------------------- 取值

def column(rows, name):
    """取一列原始值；任一行缺这个键就报错（含行号）。"""
    out = []
    for i, row in enumerate(rows):
        if name not in row:
            raise KeyError(f'column {name!r} missing at row {i}; available: '
                           + ', '.join(sorted(row)))
        out.append(row[name])
    return out


def numbers(rows, name):
    """取数值列。数值字符串按数值处理，无法转换则报错。"""
    out = []
    for i, value in enumerate(column(rows, name)):
        if isinstance(value, bool) or value is None:
            raise TypeError(f'column {name!r} is not numeric at row {i}: {value!r}')
        try:
            out.append(float(value))
        except (TypeError, ValueError):
            raise TypeError(f'column {name!r} is not numeric at row {i}: {value!r}') from None
    return out


def labels(rows, name):
    """取标签列，统一转成字符串。"""
    return [str(v) for v in column(rows, name)]


def resolve_color(theme, token, default='down'):
    """`#RRGGBB` 原样返回；否则按主题键取，取不到时用 fallback，绝不画成黑色。"""
    if token is None:
        return theme.get(default, theme['ink'])
    if isinstance(token, str) and token.startswith('#'):
        return token
    return theme.get(token, theme.get(default, theme['ink']))


def padded_domain(*groups, include_zero=True, pad=0.10):
    """由若干组数值算 y 轴范围，留出上下留白。"""
    values = [v for group in groups for v in group if v is not None and math.isfinite(v)]
    if not values:
        return (0.0, 1.0)
    lo, hi = min(values), max(values)
    if include_zero:
        lo, hi = min(lo, 0.0), max(hi, 0.0)
    if hi == lo:
        hi = lo + (abs(lo) * 0.1 or 1.0)
    span = hi - lo
    return (lo - span * pad, hi + span * pad)


class XAxis:
    """x 轴。

    三种定位方式，由 `kind` 选择：

    - `auto`（默认）：能被 `float()` 解析的按真实数值定位（天数、年份、比率），
      其余按行序等距。
    - `category`：一律按行序等距——**日期必须用这个**。`20260810` 是可解析的整数，
      若按数值定位，`0810→0811` 的差值（1）与 `0814→0817`（3，跨周末）不相等，
      横轴就会按日历日拉开，交易日之间的间距看着忽宽忽窄。
    - `value`：强制按数值定位，非数值直接报错。
    """

    def __init__(self, values, kind='auto'):
        self.raw = [str(v) for v in values]
        self.numeric = None
        if kind == 'category':
            return
        try:
            self.numeric = [float(v) for v in values]
        except (TypeError, ValueError):
            if kind == 'value':
                raise TypeError(
                    'chart.x_kind is "value" but the x column has non-numeric entries: '
                    + ', '.join(repr(v) for v in self.raw[:5])) from None
            self.numeric = None

    def __len__(self):
        return len(self.raw)

    def position(self, index):
        """第 index 行在 x 轴上的数据坐标。"""
        if self.numeric is not None:
            return self.numeric[index]
        return float(index)

    def domain(self):
        """x 轴数据范围（两端各留一点，避免首尾贴着边框）。"""
        if self.numeric is not None:
            lo, hi = min(self.numeric), max(self.numeric)
            if hi == lo:
                hi = lo + 1
            span = hi - lo
            return (lo - span * 0.02, hi + span * 0.02)
        return (-0.5, len(self.raw) - 0.5)

    def ticks(self, max_ticks=8, min_gap_px=None, width_px=None, label_size=12.5):
        """挑出要显示标签的下标。**按像素等距分配，始终含首尾。**

        早先的写法是"固定步长抽样 + 末尾强行补最后一根"，两个毛病：抽出来的点可能
        彼此挨着（`09-01` 后面紧跟 `09-23`，只隔 76px），末尾那根还可能撞上倒数第二个。
        这里改成：先按可用宽度算出最多能放几个，再在 `[0, n-1]` 上等距取值——
        间距天然均匀，首尾天然在内。
        """
        n = len(self.raw)
        if n == 0:
            return []
        if n == 1:
            return [0]

        if width_px and min_gap_px is None:
            min_gap_px = text_width('0' * 8, label_size)

        # 按宽度决定能容纳几个标签；放不下就宁可少放，也不让字叠在一起。
        capacity = n
        if width_px and min_gap_px:
            capacity = max(2, int(width_px // min_gap_px) + 1)
        count = min(max_ticks, capacity, n)

        if count >= n:
            return list(range(n))
        if count == 2:
            return [0, n - 1]
        step = (n - 1) / (count - 1)
        picked = sorted({round(i * step) for i in range(count)})
        picked[-1] = n - 1          # 浮点舍入后确保末位在内
        return picked


# ---------------------------------------------------------------- line

@chart('line')
def line(c, rect, cfg, rows):
    """时序折线。

    字段：`x`（x 列名）、`series`（必填，`[{col,label,color,dash}]`）、
    `band`（可选 `{lo,hi,label,color}`）、`refs`（可选 `[{y,label,color}]`）、
    `marks`（可选，要打点的 x 值列表）、`annotate`（可选 `[{x,text,color,dy}]`）、
    `y_fmt`（`num`/`pct`）、`y_dec`（小数位）。
    """
    x_col = cfg.get('x')
    if x_col is None:
        raise ValueError('line chart needs "x" (the column holding the x axis values)')
    series_cfg = cfg.get('series') or []
    if not series_cfg:
        raise ValueError('line chart needs at least one entry in "series"')

    xaxis = XAxis(column(rows, x_col), kind=cfg.get('x_kind', 'auto'))
    n = len(xaxis)
    series = [{'label': s.get('label', s['col']), 'col': s['col'],
               'values': numbers(rows, s['col']),
               'color': resolve_color(c.t, s.get('color'), 'down'),
               'dash': s.get('dash')} for s in series_cfg]
    for s in series:
        if len(s['values']) != n:
            raise ValueError(f"series {s['col']!r} has {len(s['values'])} values but x has {n}")

    band = cfg.get('band')
    band_lo = band_hi = None
    if band:
        band_lo, band_hi = numbers(rows, band['lo']), numbers(rows, band['hi'])

    refs = cfg.get('refs') or []
    dom_values = [v for s in series for v in s['values']]
    if band_lo:
        dom_values += band_lo + band_hi
    dom_values += [float(r['y']) for r in refs if r.get('y') is not None]
    y_domain = padded_domain(dom_values, include_zero=cfg.get('include_zero', True))

    ax = Axes(c, rect, xaxis.domain(), y_domain)
    y_fmt = cfg.get('y_fmt', 'num')
    y_dec = cfg.get('y_dec', 0)
    formatter = (lambda v: fmt_pct(v, y_dec)) if y_fmt == 'pct' else (lambda v: fmt_num(v, y_dec))
    ticks = nice_ticks(y_domain[0], y_domain[1], cfg.get('y_ticks', 5))
    ax.grid_y(ticks, [formatter(t) for t in ticks], c.t['line'])

    # 分布带：上下边界围出的多边形
    if band:
        color = resolve_color(c.t, band.get('color'), 'band')
        upper = [(ax.px(xaxis.position(i)), ax.py(v)) for i, v in enumerate(band_hi)]
        lower = [(ax.px(xaxis.position(i)), ax.py(v)) for i, v in enumerate(reversed(band_lo))]
        c.polygon(upper + lower, color, opacity=band.get('opacity', 0.13))
        if band.get('label'):
            c.text(upper[0][0] + 6, upper[0][1] - 6, band['label'], size=12,
                   fill=c.t['mute'])

    # 参考线
    for ref in refs:
        if ref.get('y') is None:
            continue
        color = resolve_color(c.t, ref.get('color'), 'accent')
        y = ax.py(float(ref['y']))
        c.line(rect[0], y, rect[0] + rect[2], y, color, ref.get('width', 1.6),
               dash=ref.get('dash', '6 4'))
        if ref.get('label'):
            c.text(rect[0] + 6, y - 7, ref['label'], size=12.5, fill=color)

    # 折线
    for s in series:
        pts = [(ax.px(xaxis.position(i)), ax.py(v)) for i, v in enumerate(s['values'])]
        if cfg.get('area') and len(series) == 1:
            baseline = ax.py(max(y_domain[0], 0.0))
            c.polygon(pts + [(pts[-1][0], baseline), (pts[0][0], baseline)],
                      s['color'], opacity=0.16)
        c.polyline(pts, s['color'], width=s.get('width', 2.6), dash=s['dash'])
        # 线尾标系列名
        if len(series) > 1 and s.get('label'):
            lx, ly = pts[-1]
            c.text(lx + 8, ly, s['label'], size=12.5, fill=s['color'], weight='bold',
                   baseline='middle')

    # 标记点 + 数值
    if cfg.get('marks'):
        primary = series[0]
        for mark in cfg['marks']:
            idx = _index_of_mark(xaxis, mark)
            if idx is None:
                continue
            px, py = ax.px(xaxis.position(idx)), ax.py(primary['values'][idx])
            c.circle(px, py, 4.6, c.t['card'], stroke=primary['color'], stroke_width=2.4)
            c.text(px, py - 13, formatter(primary['values'][idx]), size=13,
                   fill=primary['color'], weight='bold', anchor='middle')

    # 文字标注
    for note in cfg.get('annotate') or []:
        idx = _index_of_mark(xaxis, note.get('x'))
        if idx is None:
            continue
        px, py = ax.px(xaxis.position(idx)), ax.py(series[0]['values'][idx])
        c.text(px + note.get('dx', 8), py + note.get('dy', 0), note.get('text', ''),
               size=note.get('size', 13), fill=resolve_color(c.t, note.get('color'), 'up'),
               weight='bold', anchor=note.get('anchor', 'start'))

    # x 标签：先按像素宽度挑出不重叠的位置，再把日期收敛成短标签。
    # 日期识别统一交给 `fmt_date_label`——它对认不出的值原样返回，所以「第5天」
    # 「2024Q3」这类非日期标签不会被误改。特意不另设开关：多一个 `date_axis`
    # 布尔就会和 `x_kind` 职责重叠，两者给出矛盾设置时无人能判断该听谁的。
    label_size = 12.5
    picked = xaxis.ticks(cfg.get('x_ticks', 8), width_px=ax.w, label_size=label_size)
    compact_dates = not has_multiple_years(xaxis.raw)
    for i in picked:
        label = fmt_date_label(xaxis.raw[i], compact=compact_dates)
        c.text(ax.px(xaxis.position(i)), rect[1] + rect[3] + 21, label,
               size=label_size, fill=c.t['mute'], anchor='middle')


def _index_of_mark(xaxis, mark):
    """把 marks/annotate 里写的 x 值换算成行下标；数值与字符串都试。"""
    if mark is None:
        return None
    text = str(mark)
    if text in xaxis.raw:
        return xaxis.raw.index(text)
    try:
        wanted = float(mark)
    except (TypeError, ValueError):
        return None
    if xaxis.numeric is not None:
        for i, value in enumerate(xaxis.numeric):
            if abs(value - wanted) < 1e-9:
                return i
    return None


# ---------------------------------------------------------------- barh

@chart('barh')
def barh(c, rect, cfg, rows):
    """横向条形，用于横截面排名（热榜、板块涨幅、个股贡献）。

    字段：`label`（标签列）、`value`（数值列）、`sign`（可选，带正负的列，
    决定红/蓝）、`rank`（可选，名次列，画在标签前）、`top`（默认 10）、
    `fmt`（`compact`/`num`/`pct`）、`dec`（小数位）。
    说明文字用 spec 顶层的 `legend`，不在这里——图内元素与页脚说明要由
    同一个游标排布，图型自己贴底边写说明会和结论行撞在一起。
    """
    label_col = cfg.get('label')
    value_col = cfg.get('value')
    if label_col is None or value_col is None:
        raise ValueError('barh chart needs "label" and "value" column names')

    pairs = list(zip(labels(rows, label_col), numbers(rows, value_col),
                     numbers(rows, cfg['sign']) if cfg.get('sign') else [None] * len(rows),
                     labels(rows, cfg['rank']) if cfg.get('rank') else [None] * len(rows)))
    if cfg.get('sort', True):
        pairs.sort(key=lambda p: p[1], reverse=not cfg.get('ascending', False))
    pairs = pairs[:int(cfg.get('top', 10))]
    if not pairs:
        raise ValueError('barh chart has no rows to draw')

    fmt_kind, dec = cfg.get('fmt', 'num'), cfg.get('dec', 0)
    if fmt_kind == 'pct':
        formatter = lambda v: fmt_pct(v, dec, signed=bool(cfg.get('sign')))  # noqa: E731
    elif fmt_kind == 'compact':
        formatter = lambda v: fmt_compact(v, dec or 1)  # noqa: E731
    else:
        formatter = lambda v: fmt_num(v, dec)  # noqa: E731

    label_pad = cfg.get('label_width', 168)
    value_pad = cfg.get('value_width', 104)
    plot_x = rect[0] + label_pad
    plot_w = max(rect[2] - label_pad - value_pad, 40)
    max_value = max(abs(p[1]) for p in pairs) or 1.0
    rows_n = len(pairs)
    slot = rect[3] / rows_n
    bar_h = min(slot * 0.62, cfg.get('bar_max', 34))

    for i, (label, value, sign, rank) in enumerate(pairs):
        cy = rect[1] + slot * (i + 0.5)
        # 金融惯例：涨红跌蓝；无 sign 列时整组同色。
        if sign is None:
            tone = resolve_color(c.t, cfg.get('color'), 'down')
        elif sign > 0:
            tone = c.t['up']
        elif sign < 0:
            tone = c.t['down']
        else:
            tone = c.t['neutral']

        width = abs(value) / max_value * plot_w
        c.rect(plot_x, cy - bar_h / 2, max(width, 1.5), bar_h, tone,
               rx=min(3, bar_h / 2), opacity=cfg.get('bar_opacity', 0.92))

        head = f'#{rank}  {label}' if rank else label
        c.text(rect[0], cy, _ellipsis(head, 13.5, label_pad - 14), size=13.5,
               fill=c.t['ink'], anchor='start', baseline='middle')
        c.text(plot_x + width + 8, cy, formatter(value), size=13, fill=tone,
               weight='bold', anchor='start', baseline='middle')


def _ellipsis(text, size, max_width):
    """按估算宽度截断并加省略号，避免长标签压到条形上。"""
    if text_width(text, size) <= max_width:
        return text
    cut = text
    while cut and text_width(cut + '…', size) > max_width:
        cut = cut[:-1]
    return cut + '…'


# ---------------------------------------------------------------- table

@chart('table')
def table(c, rect, cfg, rows):
    """表格，用于名录类数据（基金列表、成分股、接口字段）。

    字段：`columns`（必填，`[{col,label,align,dec}]`）、`top`（默认 12）、
    `row_height`（默认 30）、`font_size`（默认 13）。
    """
    columns = cfg.get('columns') or []
    if not columns:
        raise ValueError('table chart needs "columns": [{col, label}]')
    limit = int(cfg.get('top', 12))
    shown = rows[:limit]
    size = cfg.get('font_size', 13)
    row_h = cfg.get('row_height', 30)

    weights = [col.get('weight', 1) for col in columns]
    total = sum(weights) or 1
    widths = [rect[2] * w / total for w in weights]
    offsets, acc = [], rect[0]
    for w in widths:
        offsets.append(acc)
        acc += w

    # 表头
    y = rect[1] + size
    for col, x, w in zip(columns, offsets, widths):
        align = col.get('align', 'left')
        tx = x if align == 'left' else x + w - 6
        c.text(tx, y, col.get('label', col['col']), size=size, fill=c.t['mute'],
               weight='bold', anchor='start' if align == 'left' else 'end')
    y += row_h * 0.55
    c.line(rect[0], y, rect[0] + rect[2], y, c.t['line'], 1)

    # 数据行
    for r, row in enumerate(shown):
        y += row_h
        if r % 2 == 1:
            c.rect(rect[0], y - size - 6, rect[2], row_h - 4, c.t['card'], opacity=0.7)
        for col, x, w in zip(columns, offsets, widths):
            raw = row.get(col['col'])
            text = _cell_text(raw, col)
            align = col.get('align', 'left')
            tx = x if align == 'left' else x + w - 6
            c.text(tx, y, _ellipsis(text, size, w - 12), size=size, fill=c.t['ink'],
                   anchor='start' if align == 'left' else 'end')

    if len(rows) > limit:
        c.text(rect[0], y + row_h * 0.9, f'（共 {len(rows)} 条，此处显示前 {limit} 条）',
               size=12, fill=c.t['mute'])


def _cell_text(raw, col):
    """单元格取值：按 `dec` 格式化数值，缺失写 `—`（不写 None）。"""
    if raw is None:
        return '—'
    dec = col.get('dec')
    if dec is not None:
        try:
            return fmt_num(float(raw), int(dec))
        except (TypeError, ValueError):
            return str(raw)
    return str(raw)
