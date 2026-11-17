"""图型注册表。**这是唯一的扩展点。**

新增一种图，只做两件事：

1. 在下面写一个函数并加 `@chart('名字', x_axis=True)` 装饰器：
   `x_axis=True` 表示图型自己会在绘图区下方画横轴标签，`plot.py` 会据此预留高度；
   不声明就会把标签画进说明区（旧版这里靠一张写死的图型名单）。
2. 在 SKILL.md 的图型表里加一行（给模型看的字段说明）。

函数签名固定为 `(c, rect, cfg, rows)`：

- `c`    —— `canvas.Svg`，画布；`c.t[...]` 取主题色
- `rect` —— `(x, y, w, h)` 绘图区像素矩形，已避开标题与页脚
- `cfg`  —— spec 里 `chart:` 的内容，字段由本图型自己定义
- `rows` —— 数据行 `list[dict]`

约定：**列名缺失或类型不符必须报错**，绝不静默丢行——金融图上少一根线而不报错，
比直接失败更危险。数值列不接受 NaN/Infinity（会写出非法 SVG 坐标）；确实要表示
“没有数据”的间隙时用 JSON `null`，并且该图型要显式允许（如 line 的 series/band）。
颜色用 `resolve_color()`，既接受主题键也接受 `#RRGGBB`。
"""
import math

from .canvas import (Axes, contrast_ink, date_parts, fmt_compact, fmt_date_label, fmt_num,
                     fmt_pct, has_multiple_years, mix_hex, nice_ticks, text_width)
from .theme import series_color

#: 图型注册表。键是 `chart.type` 的取值。
CHARTS = {}

#: 图型元数据：是否自绘横轴、横轴需要多高。布局层只认这里，不认图型名字。
CHART_META = {}


def chart(name, *, x_axis=False, x_axis_height=None, needs_rows=True):
    """把一个函数登记成 `chart.type = name` 的渲染器。

    `x_axis=True` 时 `plot.py` 会在绘图区下方留出横轴标签的高度（默认 46px）；
    `needs_rows=False` 用于示意图这类不消费数据行的图型（此时 spec 可以不写 rows/data）。
    """
    def deco(fn):
        CHARTS[name] = fn
        CHART_META[name] = {'x_axis': bool(x_axis), 'x_axis_height': x_axis_height,
                            'needs_rows': bool(needs_rows)}
        return fn
    return deco


def needs_x_axis(kind):
    """该图型是否自绘横轴标签。未知图型返回 False（真正的报错在 render 里）。"""
    return CHART_META.get(kind, {}).get('x_axis', False)


def needs_rows(kind):
    """该图型是否必须有数据行（示意图为 False）。"""
    return CHART_META.get(kind, {}).get('needs_rows', True)


def x_axis_height(kind, default=46):
    """该图型需要预留的横轴高度；不需要横轴时为 0。"""
    if not needs_x_axis(kind):
        return 0
    return CHART_META.get(kind, {}).get('x_axis_height') or default


def render(c, rect, cfg, rows):
    """按 `cfg['type']` 分派。未知类型列出全部可用值，便于直接改正。"""
    kind = cfg.get('type')
    if kind is None:
        raise ValueError("chart.type is required; available: " + ", ".join(sorted(CHARTS)))
    if kind not in CHARTS:
        raise KeyError(f"unknown chart.type {kind!r}; available: " + ", ".join(sorted(CHARTS)))
    if not rows and needs_rows(kind):
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


def numbers(rows, name, allow_none=False):
    """取数值列。

    - 默认：遇 `None`、布尔或无法转换的值直接报错（含行号）；
    - `allow_none=True`：`None` 作为“没有数据”的间隙保留，`NaN/Infinity` 仍报错；
    - 数值字符串按数值处理。
    """
    out = []
    for i, value in enumerate(column(rows, name)):
        if value is None:
            if allow_none:
                out.append(None)
                continue
            raise TypeError(f'column {name!r} is None at row {i}; '
                            'pass null only for charts that accept gaps')
        if isinstance(value, bool):
            raise TypeError(f'column {name!r} is not numeric at row {i}: {value!r}')
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise TypeError(f'column {name!r} is not numeric at row {i}: {value!r}') from None
        if not math.isfinite(number):
            raise ValueError(f'column {name!r} is not finite at row {i}: {value!r}; '
                             'NaN/Infinity cannot be drawn')
        out.append(number)
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
    """由若干组数值算 y 轴范围，留出上下留白。`None` 视为缺测跳过。"""
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


def _formatter(kind, dec, signed=False):
    """按 `fmt` 生成格式化函数；`signed=True` 时正数带 `+`。"""
    if kind == 'pct':
        return lambda value: fmt_pct(value, dec, signed=signed)
    if kind == 'compact':
        base = lambda value: fmt_compact(value, dec or 1)  # noqa: E731
    else:
        base = lambda value: fmt_num(value, dec)  # noqa: E731
    if signed:
        return lambda value: ('+' if value > 0 else '') + base(value)
    return base


def _ellipsis(text, size, max_width):
    """按估算宽度截断并加省略号，避免长标签压到图形上。"""
    if text_width(text, size) <= max_width:
        return text
    cut = text
    while cut and text_width(cut + '…', size) > max_width:
        cut = cut[:-1]
    return cut + '…'


def _segments(points):
    """把带 `None` 的点列切成连续段，用于折线/面积跨过缺测。"""
    segments, current = [], []
    for point in points:
        if point is None:
            if current:
                segments.append(current)
                current = []
        else:
            current.append(point)
    if current:
        segments.append(current)
    return segments


def _decimals_for_step(step):
    """刻度步长需要的小数位：0.25 → 2，2 → 0。"""
    if not step or not math.isfinite(step):
        return 0
    text = f'{abs(step):.10f}'.rstrip('0').rstrip('.')
    return len(text.split('.')[1]) if '.' in text else 0


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


def _flush_band(c, run, color, opacity):
    """把一段连续的上/下边界围成多边形。"""
    if len(run) < 2:
        return
    upper = [(px, upper) for px, upper, _ in run]
    lower = [(px, lower) for px, _, lower in reversed(run)]
    c.polygon(upper + lower, color, opacity=opacity)


# ---------------------------------------------------------------- line

@chart('line', x_axis=True)
def line(c, rect, cfg, rows):
    """时序折线。

    字段：`x`（x 列名）、`series`（必填，`[{col,label,color,dash}]`）、
    `band`（可选 `{lo,hi,label,color}`）、`refs`（可选 `[{y,label,color}]`）、
    `marks`（可选，要打点的 x 值列表）、`annotate`（可选 `[{x,text,color,dy}]`）、
    `y_fmt`（`num`/`pct`/`compact`）、`y_dec`（小数位，按刻度自动补足）、
    `include_zero`（默认 false；水平/资金类数据显式设 true）。
    `series`/`band` 的值允许 JSON `null`，表示该点没有数据。
    """
    x_col = cfg.get('x')
    if x_col is None:
        raise ValueError('line chart needs "x" (the column holding the x axis values)')
    series_cfg = cfg.get('series') or []
    if not series_cfg:
        raise ValueError('line chart needs at least one entry in "series"')

    xaxis = XAxis(column(rows, x_col), kind=cfg.get('x_kind', 'auto'))
    n = len(xaxis)
    many = len(series_cfg) > 1
    series = []
    for index, entry in enumerate(series_cfg):
        col = entry.get('col')
        if col is None:
            raise ValueError('every series entry needs "col"')
        values = numbers(rows, col, allow_none=True)
        if len(values) != n:
            raise ValueError(f"series {col!r} has {len(values)} values but x has {n}")
        chosen = entry.get('color')
        color = (resolve_color(c.t, chosen)
                 if chosen is not None else
                 (series_color(c.t, index) if many else c.t['down']))
        series.append({'label': entry.get('label', col), 'col': col,
                       'values': values, 'color': color, 'dash': entry.get('dash')})

    band = cfg.get('band')
    band_lo = band_hi = None
    if band:
        band_lo = numbers(rows, band['lo'], allow_none=True)
        band_hi = numbers(rows, band['hi'], allow_none=True)

    refs = cfg.get('refs') or []
    dom_values = [value for item in series for value in item['values']]
    if band_lo:
        dom_values += band_lo + band_hi
    ref_values = []
    for ref in refs:
        if ref.get('y') is None:
            continue
        ref_value = float(ref['y'])
        if not math.isfinite(ref_value):
            raise ValueError(f'ref y must be finite, got {ref["y"]!r}')
        ref_values.append(ref_value)
    dom_values += ref_values
    y_domain = padded_domain(dom_values, include_zero=bool(cfg.get('include_zero', False)))

    ax = Axes(c, rect, xaxis.domain(), y_domain)
    y_fmt = cfg.get('y_fmt', 'num')
    tick_target = int(cfg.get('y_ticks') or max(2, min(7, round(rect[3] / 60))))
    ticks = nice_ticks(y_domain[0], y_domain[1], tick_target)
    step = min((b - a for a, b in zip(ticks, ticks[1:]) if b > a), default=0)
    step_dec = _decimals_for_step(step)
    dec = max(int(cfg.get('y_dec', 0)), step_dec)
    value_formatter = _formatter(y_fmt, dec)
    tick_formatter = (_formatter('compact', dec) if y_fmt == 'compact'
                      else _formatter(y_fmt, step_dec))
    tick_labels = [tick_formatter(t) for t in ticks]
    # 左侧留白放不下完整数字时改用 compact（1,000,000,000 → 10亿）。
    # 宁可换一种数字写法，也不要把轴标签画到画布外——那种图在聊天里看不出错。
    if max((text_width(label, 12.5) for label in tick_labels), default=0) > rect[0] - 8:
        tick_formatter = _formatter('compact', dec)
        value_formatter = tick_formatter
        tick_labels = [tick_formatter(t) for t in ticks]
    ax.grid_y(ticks, tick_labels, c.t['line'])

    # 分布带：上下边界围出的多边形；缺测处断开，不连成假带。
    if band:
        color = resolve_color(c.t, band.get('color'), 'band')
        run = []            # [(px, upper_py, lower_py)]，缺测处断开
        first = None
        for i, (upper, lower) in enumerate(zip(band_hi, band_lo)):
            if upper is None or lower is None:
                _flush_band(c, run, color, band.get('opacity', 0.13))
                run = []
                continue
            point = (ax.px(xaxis.position(i)), ax.py(upper), ax.py(lower))
            if first is None:
                first = point
            run.append(point)
        _flush_band(c, run, color, band.get('opacity', 0.13))
        if band.get('label') and first:
            c.text(first[0] + 6, first[1] - 6, band['label'], size=12, fill=c.t['mute'])

    # 参考线
    for ref, ref_value in zip([r for r in refs if r.get('y') is not None], ref_values):
        color = resolve_color(c.t, ref.get('color'), 'accent')
        y = ax.py(ref_value)
        c.line(rect[0], y, rect[0] + rect[2], y, color, ref.get('width', 1.6),
               dash=ref.get('dash', '6 4'))
        if ref.get('label'):
            c.text(rect[0] + 6, y - 7, ref['label'], size=12.5, fill=color)

    # 折线
    last_label_y = None
    for item in series:
        pts = [None if value is None else (ax.px(xaxis.position(i)), ax.py(value))
               for i, value in enumerate(item['values'])]
        segments = _segments(pts)
        if cfg.get('area') and len(series) == 1:
            baseline = ax.py(max(y_domain[0], 0.0))
            for segment in segments:
                if len(segment) >= 2:
                    c.polygon(segment + [(segment[-1][0], baseline), (segment[0][0], baseline)],
                              item['color'], opacity=0.16)
        for segment in segments:
            c.polyline(segment, item['color'], width=item.get('width', 2.6), dash=item.get('dash'))
        # 线尾标系列名（用最后一段的末点，缺测时不会标到画布外）
        if len(series) > 1 and item.get('label') and segments:
            lx, ly = segments[-1][-1]
            # 两条线终点很近时把标签上下错开，避免像 "收盘/MA5" 那样叠在一起
            if last_label_y is not None and abs(ly - last_label_y) < 16:
                ly = last_label_y + (16 if ly >= last_label_y else -16)
            last_label_y = ly
            # 贴近右边界时把系列名放到点的左侧，否则文字会跑出画布
            flip = lx + 8 + text_width(item['label'], 12.5) > rect[0] + rect[2]
            c.text(lx - 8 if flip else lx + 8, ly, item['label'], size=12.5,
                   fill=item['color'], weight='bold', baseline='middle',
                   anchor='end' if flip else 'start')

    # 标记点 + 数值
    if cfg.get('marks'):
        primary = series[0]
        for mark in cfg['marks']:
            idx = _index_of_mark(xaxis, mark)
            if idx is None:
                raise ValueError(f'mark {mark!r} is not in the x column {x_col!r}; '
                                 'fix the spec instead of dropping the mark silently')
            value = primary['values'][idx]
            if value is None:
                continue
            px, py = ax.px(xaxis.position(idx)), ax.py(value)
            c.circle(px, py, 4.6, c.t['card'], stroke=primary['color'], stroke_width=2.4)
            c.text(px, py - 13, value_formatter(value), size=13, fill=primary['color'],
                   weight='bold', anchor='middle')

    # 文字标注
    for note in cfg.get('annotate') or []:
        idx = _index_of_mark(xaxis, note.get('x'))
        if idx is None:
            raise ValueError(f'annotate x {note.get("x")!r} is not in the x column {x_col!r}')
        value = series[0]['values'][idx]
        if value is None:
            continue
        px, py = ax.px(xaxis.position(idx)), ax.py(value)
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

    values = numbers(rows, value_col)
    pairs = list(zip(labels(rows, label_col), values,
                     numbers(rows, cfg['sign']) if cfg.get('sign') else [None] * len(rows),
                     labels(rows, cfg['rank']) if cfg.get('rank') else [None] * len(rows)))
    if cfg.get('sort', True):
        pairs.sort(key=lambda p: p[1], reverse=not cfg.get('ascending', False))
    top = int(cfg.get('top', 10))
    pairs = pairs[:top]
    if not pairs:
        raise ValueError('barh chart has no rows to draw')

    # 行距至少容得下字号；放不下时先缩字号、再截断并明确写出“显示前 N 条”。
    min_slot = 16.0
    plot_h = rect[3]
    max_rows = max(1, int(plot_h // min_slot))
    note = ''
    if len(pairs) > max_rows:
        note = f'共 {len(pairs)} 条，显示前 {max_rows} 条（提高 height 或调小 top）'
        pairs = pairs[:max_rows]
        plot_h = rect[3] - 20
    rows_n = len(pairs)
    slot = plot_h / rows_n
    font_size = 13.5 if slot >= 20 else max(10.0, min(13.5, slot * 0.68))
    bar_h = max(1.5, min(slot * 0.62, cfg.get('bar_max', 34), slot - 2))

    fmt_kind, dec = cfg.get('fmt', 'num'), cfg.get('dec', 0)
    formatter = _formatter(fmt_kind, dec, signed=bool(cfg.get('sign')))
    lo = min(0.0, min(value for _, value, _, _ in pairs))
    hi = max(0.0, max(value for _, value, _, _ in pairs))
    if hi == lo:
        hi = lo + 1.0

    label_pad = cfg.get('label_width', 168)
    value_pad = cfg.get('value_width', 104)
    plot_x = rect[0] + label_pad
    plot_w = max(rect[2] - label_pad - value_pad, 40)
    zero_x = plot_x + (0.0 - lo) / (hi - lo) * plot_w

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

        tip_x = zero_x + value / (hi - lo) * plot_w
        x0, width = min(zero_x, tip_x), max(abs(tip_x - zero_x), 1.5)
        c.rect(x0, cy - bar_h / 2, width, bar_h, tone,
               rx=min(3, bar_h / 2), opacity=cfg.get('bar_opacity', 0.92))

        head = f'#{rank}  {label}' if rank else label
        c.text(rect[0], cy, _ellipsis(head, font_size, label_pad - 14), size=font_size,
               fill=c.t['ink'], anchor='start', baseline='middle')
        # 数值写在条形外侧：正值在右、负值在左；外侧放不下时写进条形里
        value_text = formatter(value)
        outer_x = tip_x + (8 if tip_x >= zero_x else -8)
        overflow = (tip_x >= zero_x and outer_x + text_width(value_text, font_size)
                    > rect[0] + rect[2]) or \
                   (tip_x < zero_x and outer_x - text_width(value_text, font_size) < rect[0])
        if overflow and width > text_width(value_text, font_size) + 10:
            c.text(tip_x - (6 if tip_x >= zero_x else -6), cy, value_text, size=font_size,
                   fill=contrast_ink(tone, c.t['ink'], c.t['card']), weight='bold',
                   anchor='end' if tip_x >= zero_x else 'start', baseline='middle')
        else:
            c.text(outer_x, cy, value_text, size=font_size, fill=tone, weight='bold',
                   anchor='start' if tip_x >= zero_x else 'end', baseline='middle')

    # 有负值时画零基线：全负条形从右往左长，没有基线看起来像“全部正增长”。
    if lo < 0:
        c.line(zero_x, rect[1], zero_x, rect[1] + plot_h, c.t['line'], 1)

    if note:
        c.text(rect[0], rect[1] + rect[3] - 2, note, size=11, fill=c.t['mute'])


# ---------------------------------------------------------------- table

@chart('table')
def table(c, rect, cfg, rows):
    """表格，用于名录类数据（基金列表、成分股、接口字段）。

    字段：`columns`（必填，`[{col,label,align,dec,weight}]`）、`top`（默认 12）、
    `row_height`（默认 30）、`font_size`（默认 13）。
    列可写 `"type": "sparkline"`，该列的值必须是数字数组，表格里画迷你走势线。

    行数放不下时按可用高度截断，并在表底写明“共 N 条，显示前 k 条”，
    不让表格盖到 legend/结论行上。
    """
    columns = cfg.get('columns') or []
    if not columns:
        raise ValueError('table chart needs "columns": [{col, label}]')
    limit = int(cfg.get('top', 12))
    size = cfg.get('font_size', 13)
    row_h = float(cfg.get('row_height', 30))
    min_row_h = size + 8

    wanted = min(limit, len(rows))
    if wanted <= 0:
        raise ValueError('table chart needs at least one row')
    header_h = size + row_h * 0.55 + 6
    avail = rect[3] - header_h
    note_h = 18 if wanted < len(rows) else 0
    if row_h * wanted > avail - note_h:
        row_h = max(min_row_h, (avail - note_h) / wanted)
    fit = max(1, int((avail - note_h) // row_h))
    if fit < wanted and note_h == 0:
        # 实际是被高度截断的：补一条“显示前 N 条”的位置再重算
        note_h = 18
        row_h = max(min_row_h, (avail - note_h) / wanted)
        fit = max(1, int((avail - note_h) // row_h))
    shown = min(wanted, fit)
    truncated = shown < len(rows)
    shown_rows = rows[:shown]

    weights = [col.get('weight', 1) for col in columns]
    total = sum(weights) or 1
    widths = [rect[2] * w / total for w in weights]
    offsets, acc = [], rect[0]
    for width in widths:
        offsets.append(acc)
        acc += width

    # 表头
    y = rect[1] + size
    for col, x, width in zip(columns, offsets, widths):
        align = col.get('align', 'left')
        tx = x if align == 'left' else x + width - 6
        c.text(tx, y, col.get('label', col['col']), size=size, fill=c.t['mute'],
               weight='bold', anchor='start' if align == 'left' else 'end')
    y += row_h * 0.55
    c.line(rect[0], y, rect[0] + rect[2], y, c.t['line'], 1)

    # 数据行
    for r, row in enumerate(shown_rows):
        y += row_h
        if r % 2 == 1:
            c.rect(rect[0], y - size - 6, rect[2], row_h - 4, c.t['card'], opacity=0.7)
        for col, x, width in zip(columns, offsets, widths):
            align = col.get('align', 'left')
            tx = x if align == 'left' else x + width - 6
            if col.get('type') == 'sparkline':
                _table_sparkline(c, row, col, x + 4, y - size + 2, width - 12,
                                 max(8.0, row_h - 12))
                continue
            if col['col'] not in row:
                raise KeyError(f'table column {col["col"]!r} missing at row {r}; '
                               + 'available: ' + ', '.join(sorted(row)))
            text = _cell_text(row.get(col['col']), col)
            c.text(tx, y, _ellipsis(text, size, width - 12), size=size, fill=c.t['ink'],
                   anchor='start' if align == 'left' else 'end')

    if truncated:
        c.text(rect[0], rect[1] + rect[3] - 2,
               f'共 {len(rows)} 条，显示前 {shown} 条', size=11, fill=c.t['mute'])


def _table_sparkline(c, row, col, x, y, width, height):
    """表格里的迷你走势：一条折线，按首尾方向取涨/跌色。"""
    raw = row.get(col['col'])
    if not isinstance(raw, (list, tuple)):
        raise TypeError(f'table.sparkline column {col["col"]!r} must be an array of numbers')
    values = []
    for value in raw:
        if isinstance(value, bool) or value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            values.append(number)
    if len(values) < 2:
        return
    lo, hi = min(values), max(values)
    span = hi - lo or 1.0
    points = [(x + index / (len(values) - 1) * width,
               y + height - (value - lo) / span * height) for index, value in enumerate(values)]
    tone = c.t['up'] if values[-1] >= values[0] else c.t['down']
    c.polyline(points, tone, width=1.4)


def _cell_text(raw, col):
    """单元格取值：按 `fmt`/`dec` 格式化数值，缺失写 `—`（不写 None）。"""
    if raw is None:
        return '—'
    fmt_kind = col.get('fmt')
    dec = col.get('dec')
    if fmt_kind is None and dec is None:
        return str(raw)
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    if fmt_kind is None:
        fmt_kind = 'num'
    return _formatter(fmt_kind, int(dec) if dec is not None else 0)(number)


# ---------------------------------------------------------------- heatmap

@chart('heatmap', x_axis=True, x_axis_height=36)
def heatmap(c, rect, cfg, rows):
    """矩阵热力图：横截面 × 时间（或板块 × 指标）的数值强度。

    字段：`x`（列标签列）、`y`（行标签列）、`value`（数值列）、
    `fmt`（`num`/`pct`/`compact`）、`dec`、`diverging`（默认按数据正负自动判断）、
    `show_value`（格子里写数值，默认 false）、`label_width`（默认按行标签实测宽度）、
    `top`（最多显示多少行，默认全部；放不下会报错要求调大 height）。
    """
    for key in ('x', 'y', 'value'):
        if not cfg.get(key):
            raise ValueError(f'heatmap chart needs "{key}" column name')
    xs = labels(rows, cfg['x'])
    ys = labels(rows, cfg['y'])
    values = numbers(rows, cfg['value'])
    x_order = list(dict.fromkeys(xs))
    y_order = list(dict.fromkeys(ys))
    cell = {}
    for row_x, row_y, value in zip(xs, ys, values):
        cell[(row_y, row_x)] = value

    limit = cfg.get('top')
    if limit is not None:
        y_order = y_order[:int(limit)]
    row_min = 13.0
    max_rows = max(1, int(rect[3] // row_min))
    if len(y_order) > max_rows:
        raise ValueError(
            f'heatmap has {len(y_order)} rows but only {max_rows} fit at this height; '
            'raise spec height, lower "top", or use a table')

    label_size = 12.0
    label_width = cfg.get('label_width')
    if label_width is None:
        label_width = min(max([text_width(label, label_size) for label in y_order] + [0]) + 14,
                          rect[2] * 0.34)
    label_width = max(label_width, 32)
    plot_x = rect[0] + label_width
    plot_w = rect[2] - label_width
    plot_h = rect[3] - 22
    cell_w = plot_w / len(x_order)
    cell_h = plot_h / len(y_order)
    gap = float(cfg.get('cell_gap', 1.5))

    flat = [value for key, value in cell.items() if key[0] in set(y_order)]
    lo, hi = min(flat), max(flat)
    diverging = cfg.get('diverging')
    if diverging is None:
        diverging = lo < 0 < hi
    max_abs = max(abs(lo), abs(hi), 1e-12)
    base = c.t['card']
    positive = c.t['up'] if diverging else (c.t.get('band') or c.t['down'])
    negative = c.t['down']

    # 列标签抽稀：按可用宽度选位置，首尾必显。
    label_step = max(1, int(math.ceil(44 / max(cell_w, 1))))
    x_label_indices = set(range(0, len(x_order), label_step))
    x_label_indices.add(len(x_order) - 1)

    for row_index, row_label in enumerate(y_order):
        top = rect[1] + row_index * cell_h
        for col_index, col_label in enumerate(x_order):
            value = cell.get((row_label, col_label))
            if value is None:
                continue
            if diverging:
                strength = 0.06 + 0.82 * (abs(value) / max_abs) ** 0.7
                color = positive if value >= 0 else negative
            else:
                ratio = (value - lo) / (hi - lo) if hi > lo else 0.5
                strength = 0.06 + 0.82 * ratio
                color = positive
            fill = mix_hex(base, color, strength)
            left = plot_x + col_index * cell_w
            c.rect(left + gap / 2, top + gap / 2, max(cell_w - gap, 0.5),
                   max(cell_h - gap, 0.5), fill, rx=2)
            if cfg.get('show_value') and cell_w > 34 and cell_h > 14:
                c.text(left + cell_w / 2, top + cell_h / 2,
                       _formatter(cfg.get('fmt', 'num'), cfg.get('dec', 0))(value),
                       size=min(11.0, cell_h * 0.55), anchor='middle', baseline='middle',
                       fill=contrast_ink(fill, c.t['ink'], c.t['card']))
        c.text(plot_x - 8, rect[1] + row_index * cell_h + cell_h / 2,
               _ellipsis(row_label, label_size, label_width - 12),
               size=label_size, fill=c.t['ink'], anchor='end', baseline='middle')

    compact_dates = not has_multiple_years(x_order)
    for col_index in sorted(x_label_indices):
        label = fmt_date_label(x_order[col_index], compact=compact_dates)
        c.text(plot_x + col_index * cell_w + cell_w / 2, rect[1] + plot_h + 17,
               _ellipsis(label, 11.5, max(cell_w * label_step - 4, 28)),
               size=11.5, fill=c.t['mute'], anchor='middle')


# ---------------------------------------------------------------- treemap

@chart('treemap')
def treemap(c, rect, cfg, rows):
    """矩形树图：市值/权重构成、板块内个股占比。

    字段：`label`、`value`（必须为正数）、`group`（可选，按分组着色）、
    `fmt`、`dec`、`top`（默认全部）。
    面积算法为二分切分（squarified 的简化版），块内写名称与数值，
    标题/口径说明放进 spec 的 `legend` 与 `notes`。
    """
    label_col = cfg.get('label')
    value_col = cfg.get('value')
    if label_col is None or value_col is None:
        raise ValueError('treemap chart needs "label" and "value" column names')
    groups = labels(rows, cfg['group']) if cfg.get('group') else [''] * len(rows)
    items = list(zip(labels(rows, label_col), numbers(rows, value_col), groups))
    for index, (_, value, _) in enumerate(items):
        if value <= 0:
            raise ValueError(f'treemap needs positive values, row {index} is {value!r}')
    items.sort(key=lambda item: item[1], reverse=True)
    if cfg.get('top') is not None:
        items = items[:int(cfg['top'])]

    if not items:
        raise ValueError('treemap chart has no rows to draw')
    group_order = list(dict.fromkeys(group for _, _, group in items))
    palette = {group: (series_color(c.t, i) if len(group_order) > 1 else c.t.get('band', c.t['down']))
               for i, group in enumerate(group_order)}
    formatter = _formatter(cfg.get('fmt', 'compact'), cfg.get('dec', 1))

    for left, top, width, height, (label, value, group) in _treemap_rects(items, rect):
        tone = palette[group]
        fill = mix_hex(c.t['card'], tone, 0.20)
        c.rect(left + 1, top + 1, max(width - 2, 1), max(height - 2, 1), fill,
               rx=3, stroke=tone, stroke_width=1)
        if width < 52 or height < 20:
            continue
        name = _ellipsis(label, 12.0, width - 12)
        c.text(left + 7, top + 17, name, size=12, fill=c.t['ink'], weight='bold')
        if height >= 36:
            c.text(left + 7, top + 33, formatter(value), size=11,
                   fill=c.t['mute'])


def _treemap_rects(items, rect):
    """把 `(label, value, group)` 列表铺满矩形，返回 `(x, y, w, h, item)`。

    二分切分：每次按面积总和的一半把序列分成两组，沿较长边按比例切开。
    块的长宽比不如严格 squarified 均匀，但无递归内层排序、结果稳定，
    对 10–40 个标的的构成图足够。
    """
    out = []

    def split(subset, x, y, width, height):
        if not subset:
            return
        if len(subset) == 1:
            out.append((x, y, width, height, subset[0]))
            return
        total = sum(item[1] for item in subset)
        half = total / 2
        acc, cut = 0.0, 1
        for index in range(len(subset) - 1):
            acc += subset[index][1]
            cut = index + 1
            if acc >= half:
                break
        left, right = subset[:cut], subset[cut:]
        left_value = sum(item[1] for item in left)
        ratio = (left_value / total) if total > 0 else 0.5
        if width >= height:
            split(left, x, y, width * ratio, height)
            split(right, x + width * ratio, y, width * (1 - ratio), height)
        else:
            split(left, x, y, width, height * ratio)
            split(right, x, y + height * ratio, width, height * (1 - ratio))

    split(items, rect[0], rect[1], rect[2], rect[3])
    return out


# ---------------------------------------------------------------- waterfall

@chart('waterfall', x_axis=True)
def waterfall(c, rect, cfg, rows):
    """瀑布图：资金流、营收/利润的逐项拆解。

    字段：`label`、`value`（增量列）、`fmt`、`dec`、`type_col`（可选，默认 `type`；
    该列值为 `total` 的行表示汇总，从 0 起画整根）、`sort`（默认 false）。
    每个增量从前一根的终点起画，正增量红、负增量蓝。
    """
    label_col = cfg.get('label')
    value_col = cfg.get('value')
    if label_col is None or value_col is None:
        raise ValueError('waterfall chart needs "label" and "value" column names')
    labels_list = labels(rows, label_col)
    values = numbers(rows, value_col)
    type_col = cfg.get('type_col', 'type')
    totals = [str(row.get(type_col, '')).strip().lower() in ('total', 'sum', '合计', '汇总')
              for row in rows]
    if cfg.get('sort', False):
        order = sorted(range(len(values)), key=lambda i: values[i], reverse=True)
        labels_list = [labels_list[i] for i in order]
        values = [values[i] for i in order]
        totals = [totals[i] for i in order]
    if not values:
        raise ValueError('waterfall chart has no rows to draw')

    starts, ends, cursor = [], [], 0.0
    for value, is_total in zip(values, totals):
        if is_total:
            starts.append(0.0)
            ends.append(value)
            cursor = value
        else:
            starts.append(cursor)
            ends.append(cursor + value)
            cursor += value

    lo = min(min(starts), min(ends), 0.0)
    hi = max(max(starts), max(ends), 0.0)
    y_domain = padded_domain([lo, hi], include_zero=True, pad=0.06)
    ax = Axes(c, rect, (0, len(values)), y_domain)
    tick_target = int(cfg.get('y_ticks') or max(2, min(7, round(rect[3] / 60))))
    ticks = nice_ticks(y_domain[0], y_domain[1], tick_target)
    step = min((b - a for a, b in zip(ticks, ticks[1:]) if b > a), default=0)
    dec = max(int(cfg.get('dec', 0)), _decimals_for_step(step))
    formatter = _formatter(cfg.get('fmt', 'compact'), dec, signed=True)
    tick_formatter = _formatter(cfg.get('fmt', 'compact'), _decimals_for_step(step))
    ax.grid_y(ticks, [tick_formatter(t) for t in ticks], c.t['line'])
    zero_y = ax.py(0.0)
    c.line(rect[0], zero_y, rect[0] + rect[2], zero_y, c.t['line'], 1.5)

    slot = rect[2] / len(values)
    bar_w = max(2.0, min(slot * 0.56, 46))
    label_size = 11.5
    for index, (label, start, end) in enumerate(zip(labels_list, starts, ends)):
        cx = rect[0] + slot * (index + 0.5)
        top, bottom = ax.py(max(start, end)), ax.py(min(start, end))
        tone = c.t['up'] if end >= start else c.t['down']
        c.rect(cx - bar_w / 2, top, bar_w, max(bottom - top, 1.0), tone, rx=2,
               opacity=cfg.get('bar_opacity', 0.9))
        value_text = formatter(end - start if not totals[index] else end)
        c.text(cx, max(top - 6, rect[1] + 10), value_text, size=10.5, fill=tone,
               weight='bold', anchor='middle')
        if index > 0:
            # 连接线：从前一根终点拉到这一根的起点，读图时知道累计关系
            c.line(rect[0] + slot * (index - 0.5) + bar_w / 2, ax.py(ends[index - 1]),
                   rect[0] + slot * (index + 0.5) - bar_w / 2, ax.py(starts[index]),
                   c.t['line'], 1, dash='4 4')
        c.text(cx, rect[1] + rect[3] + 21, _ellipsis(label, label_size, max(slot - 4, 24)),
               size=label_size, fill=c.t['mute'], anchor='middle')


# ---------------------------------------------------------------- timeline

@chart('timeline', x_axis=True, x_axis_height=30)
def timeline(c, rect, cfg, rows):
    """事件时间轴：公告、政策、除权、事件驱动的时间分布。

    字段：`x`（日期列）、`label`（事件名）、`sign`（可选，正负决定颜色）、
    `detail`（可选，事件说明小字）、`color`（无 sign 时的事件色）。
    事件按日期排序（日期无法全部解析时保留行序），横向等距摆放；标签最多
    三层交错，放不下的会省略并在图内注明数量。
    """
    x_col = cfg.get('x')
    label_col = cfg.get('label')
    if x_col is None or label_col is None:
        raise ValueError('timeline chart needs "x" and "label" column names')
    raw_dates = labels(rows, x_col)
    events = labels(rows, label_col)
    detail_col = cfg.get('detail')
    details = labels(rows, detail_col) if detail_col else [None] * len(rows)
    signs = numbers(rows, cfg['sign']) if cfg.get('sign') else [None] * len(rows)

    parts = [date_parts(value) for value in raw_dates]
    order = list(range(len(rows)))
    if parts and all(part is not None for part in parts):
        order.sort(key=lambda index: (parts[index][0], parts[index][1],
                                      parts[index][2] if parts[index][2] is not None else 0))

    n = len(order)
    pad = 26.0
    left = rect[0] + pad
    right = rect[0] + rect[2] - pad
    line_y = rect[1] + rect[3] * 0.54
    step = (right - left) / (n - 1) if n > 1 else 0.0
    c.line(left - 6, line_y, right + 6, line_y, c.t['line'], 1.5)

    max_levels = min(3, max(1, int((line_y - rect[1] - 24) // 40)))
    occupied = [[] for _ in range(max_levels)]
    omitted = 0
    default_tone = resolve_color(c.t, cfg.get('color'), 'accent')
    label_size = 12.5
    for rank, index in enumerate(order):
        px = (left + right) / 2 if n == 1 else left + step * rank
        sign = signs[index]
        if sign is None:
            tone = default_tone
        elif sign > 0:
            tone = c.t['up']
        elif sign < 0:
            tone = c.t['down']
        else:
            tone = c.t['neutral']
        c.circle(px, line_y, 4.6, c.t['card'], stroke=tone, stroke_width=2.2)

        label = _ellipsis(events[index], label_size, 190)
        detail = details[index]
        width = max(text_width(label, label_size),
                    text_width(detail, 11) if detail else 0) + 10
        level = None
        for candidate in range(max_levels):
            if all(px + width / 2 < start or px - width / 2 > end + 6
                   for start, end in occupied[candidate]):
                occupied[candidate].append((px - width / 2, px + width / 2))
                level = candidate
                break
        if level is None:
            omitted += 1
            continue
        label_y = line_y - 24 - level * 40
        c.line(px, line_y - 6, px, label_y + 5, c.t['line'], 1, dash='3 3')
        c.text(px, label_y, label, size=label_size, fill=tone, weight='bold', anchor='middle')
        if detail:
            c.text(px, label_y + 16, _ellipsis(detail, 11, 190), size=11,
                   fill=c.t['mute'], anchor='middle')

    compact_dates = not has_multiple_years(raw_dates)
    capacity = max(2, int(rect[2] // 64))
    stride = max(1, math.ceil(n / capacity))
    for rank, index in enumerate(order):
        if rank % stride and rank != n - 1:
            continue
        px = (left + right) / 2 if n == 1 else left + step * rank
        c.text(px, rect[1] + rect[3] + 18,
               fmt_date_label(raw_dates[index], compact=compact_dates),
               size=11.5, fill=c.t['mute'], anchor='middle')

    if omitted:
        c.text(rect[0] + rect[2], rect[1] + 12, f'{omitted} 个标签过密未显示',
               size=10.5, fill=c.t['mute'], anchor='end')


# ---------------------------------------------------------------- chain

@chart('chain', needs_rows=False)
def chain(c, rect, cfg, rows):
    """产业链/传导链示意图：声明式分层节点 + 有向边。

    spec：
      `layers`  [{name?, nodes:[节点名...]}, ...]，层从左到右；
      `edges`   [[上游节点, 下游节点], ...]，有向边只能从靠前的层指向靠后的层；
      `highlight` 可选，高亮的节点名列表。
    节点名同时是边的引用 id；节点宽高按文本测量，层距/行距自适应；
    放不下会缩小字号，再放不下直接报错，不画出互相压字的图。
    """
    layers = cfg.get('layers')
    if not isinstance(layers, list) or not layers:
        raise ValueError('chain chart needs "layers": [{name, nodes: [label...]}, ...]')
    normalized = []
    seen = {}
    for layer_index, layer in enumerate(layers):
        if not isinstance(layer, dict) or not isinstance(layer.get('nodes'), list):
            raise ValueError(f'chain.layers[{layer_index}] must be an object with a "nodes" array')
        names = []
        for node in layer['nodes']:
            label = str(node).strip()
            if not label:
                raise ValueError(f'chain.layers[{layer_index}] has an empty node label')
            if label in seen:
                raise ValueError(f'chain node {label!r} appears twice; node labels are ids')
            seen[label] = layer_index
            names.append(label)
        if not names:
            raise ValueError(f'chain.layers[{layer_index}] has no nodes')
        normalized.append({'name': str(layer.get('name') or ''), 'nodes': names})

    highlight = [str(name) for name in (cfg.get('highlight') or [])]
    for name in highlight:
        if name not in seen:
            raise ValueError(f'chain.highlight names unknown node {name!r}')

    edges = []
    for raw in cfg.get('edges') or []:
        if not isinstance(raw, (list, tuple)) or len(raw) != 2:
            raise ValueError('chain edge must be [from, to]')
        source, target = str(raw[0]), str(raw[1])
        if source not in seen or target not in seen:
            raise ValueError(f'chain edge {source!r} -> {target!r} names an unknown node')
        if seen[target] < seen[source]:
            raise ValueError(f'chain edge {source!r} -> {target!r} cannot go backwards '
                             '(target layer is earlier than source layer)')
        edges.append((source, target))

    # 尝试逐级缩小字号/内边距，直到放得下
    layout = None
    for size, pad_x, height in ((12.5, 26, 34), (11.5, 22, 30), (10.5, 18, 27), (10.0, 16, 25)):
        widths = [max(max(text_width(name, size) for name in layer['nodes']) + pad_x, 64)
                  for layer in normalized]
        gap = 56 if size >= 12 else 36
        total_width = sum(widths) + gap * (len(normalized) - 1)
        vgap = 16 if size >= 12 else 10
        stack_height = max(len(layer['nodes']) * height + (len(layer['nodes']) - 1) * vgap
                           for layer in normalized)
        caption_h = 20
        if total_width <= rect[2] and stack_height + caption_h <= rect[3]:
            layout = (size, pad_x, height, gap, vgap, widths, stack_height)
            break
    if layout is None:
        raise ValueError('chain does not fit: reduce layers/nodes or labels, or raise the canvas size')
    size, pad_x, height, gap, vgap, widths, stack_height = layout

    c.raw(_arrow_marker('chain-arrow', c.t['mute']))
    positions = {}
    # 图整体水平居中：链短时不会贴左，链长时才铺满
    total_width = sum(widths) + gap * (len(normalized) - 1)
    cursor_x = rect[0] + max((rect[2] - total_width) / 2, 0)
    stack_top = rect[1] + (rect[3] - stack_height) / 2
    for layer_index, layer in enumerate(normalized):
        width = widths[layer_index]
        count = len(layer['nodes'])
        block_h = count * height + (count - 1) * vgap
        top = rect[1] + (rect[3] - block_h) / 2
        for node_index, name in enumerate(layer['nodes']):
            node_y = top + node_index * (height + vgap)
            positions[name] = (cursor_x, node_y, width, height, layer_index)
        if layer['name']:
            c.text(cursor_x + width / 2, stack_top - 8, layer['name'],
                   size=11.5, fill=c.t['mute'], weight='bold', anchor='middle')
        cursor_x += width + gap

    # 先画边（在节点下面），再画节点
    for source, target in edges:
        sx, sy, sw, sh, source_layer = positions[source]
        tx, ty, tw, th, target_layer = positions[target]
        if source_layer == target_layer:
            # 同层内的传导：按上下关系画竖箭头，不绕到画布外
            if ty > sy:
                start, end = (sx + sw / 2, sy + sh), (tx + tw / 2, ty)
            else:
                start, end = (sx + sw / 2, sy), (tx + tw / 2, ty + th)
            path = f'M {start[0]:.2f} {start[1]:.2f} L {end[0]:.2f} {end[1]:.2f}'
        else:
            start = (sx + sw, sy + sh / 2)
            end = (tx, ty + th / 2)
            span = max(end[0] - start[0], 1.0)
            control = span * 0.45
            path = (f'M {start[0]:.2f} {start[1]:.2f} '
                    f'C {start[0] + control:.2f} {start[1]:.2f} '
                    f'{end[0] - control:.2f} {end[1]:.2f} {end[0]:.2f} {end[1]:.2f}')
        c.path(path, stroke=c.t['mute'], width=1.4, marker_end='chain-arrow')

    for name, (x, y, width, node_height, layer_index) in positions.items():
        tone = series_color(c.t, layer_index)
        if name in highlight:
            fill = mix_hex(c.t['card'], c.t['accent'], 0.24)
            stroke, stroke_width = c.t['accent'], 2.0
        else:
            fill = mix_hex(c.t['card'], tone, 0.16)
            stroke, stroke_width = tone, 1.2
        c.rect(x, y, width, node_height, fill, rx=9, stroke=stroke, stroke_width=stroke_width)
        c.text(x + width / 2, y + node_height / 2, _ellipsis(name, size, width - 14),
               size=size, fill=c.t['ink'], weight='bold', anchor='middle', baseline='middle')


def _arrow_marker(marker_id, color):
    """有向边用的箭头定义；用 userSpaceOnUse 保证不同线宽下箭头大小一致。"""
    return (f'<defs><marker id="{marker_id}" viewBox="0 0 10 10" refX="8" refY="5" '
            f'markerWidth="10" markerHeight="10" markerUnits="userSpaceOnUse" '
            f'orient="auto-start-reverse"><path d="M 1 1.5 L 8.5 5 L 1 8.5" fill="none" '
            f'stroke="{color}" stroke-width="1.6" stroke-linecap="round" '
            f'stroke-linejoin="round"/></marker></defs>')
