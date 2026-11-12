"""SVG 画布与坐标系。只用标准库，输出可被 `<img>` 直接加载的独立 SVG。

设计要点：

- **坐标**：对外一律用像素（左上角原点，y 向下），内部换算成 SVG 属性。
- **尺寸**：由 spec 决定（默认 1200x700 横版），不是模块常量，所以同一套图元能出
  聊天内联横图、竖版长图或方图。
- **文本**：用真实 `<text>` 而非路径，文字可选中、可搜索，体积也只有路径的几分之一。
  中文字体由 `font-family` 回退链解析——SVG 在 `<img>` 里是独立文档，继承不到宿主字体。
- **不依赖任何第三方包**：没有 matplotlib、没有 numpy。
"""
import math
import os

from .theme import FONT_STACK


# ---------------------------------------------------------------- 基础工具

def esc(s):
    """转义 XML 文本内容。"""
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def nice_ticks(lo, hi, target=5):
    """生成 1/2/2.5/5 x 10^n 步长的整齐刻度，落在 [lo, hi] 区间内。"""
    if hi <= lo:
        return [lo]
    raw = (hi - lo) / max(target, 1)
    mag = 10 ** math.floor(math.log10(raw))
    step = mag
    for mult in (1, 2, 2.5, 5, 10):
        step = mult * mag
        if step >= raw:
            break
    start = math.ceil(lo / step - 1e-9) * step
    out, value = [], start
    while value <= hi + step * 1e-9:
        out.append(round(value, 10))
        value += step
    return out


def fmt_date_label(raw, compact=True):
    """把返回里常见的日期写法收敛成短标签。

    上游日期有五种互不兼容形态（`20260810`、`2026-08-10`、`2026-09-30 00:00:00`、
    毫秒/纳秒时间戳、`2026年09月份`），8 位数字直接当轴标签既挤又难读。
    `compact=True` 时同一年内只留「月-日」，跨年时保留年份。
    """
    text = str(raw).strip()
    digits = ''.join(ch for ch in text if ch.isdigit())
    if len(digits) == 8 and text[:4].isdigit():
        year, month, day = digits[:4], digits[4:6], digits[6:8]
        return f'{month}-{day}' if compact else f'{year}-{month}-{day}'
    if len(digits) == 6 and len(text) <= 7:      # 202609 -> 年月
        return f'{digits[:4]}-{digits[4:6]}'
    # `2026-09-30 00:00:00` 之类：去掉时间部分
    if ' ' in text and len(text.split(' ')[0]) == 10:
        return text.split(' ')[0] if not compact else text[5:10]
    return text


def has_multiple_years(values):
    """判断一组日期标签是否跨年——跨年就不能只写月-日。"""
    years = set()
    for raw in values:
        digits = ''.join(ch for ch in str(raw) if ch.isdigit())
        if len(digits) >= 6 and str(raw).strip()[:4].isdigit():
            years.add(digits[:4])
    return len(years) > 1


def fmt_num(value, dec=0):
    """千分位数字；-0 归一成 0。"""
    if abs(value) < 10 ** (-(dec + 6)):
        value = 0.0
    return f'{value:,.{dec}f}'


def fmt_pct(value, dec=1, signed=False):
    """百分比；默认不补尾零，`signed=True` 时正数带 `+`。"""
    text = f'{value:.{dec}f}'
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    if signed and value > 0:
        text = '+' + text
    return f'{text}%'


def fmt_compact(value, dec=1):
    """紧凑数值：把 5,248,899 写成 524.9万。

    单位直接进数值，图上就不必再写一行「单位是…」的说明——那行说明正是最容易和
    结论行撞在一起的元素。热榜热度、成交额、市值这类量级都适用。
    """
    magnitude = abs(value)
    if magnitude >= 1e8:
        return f'{value / 1e8:,.{dec}f}亿'
    if magnitude >= 1e4:
        return f'{value / 1e4:,.{dec}f}万'
    if dec == 0:
        return fmt_num(value, 0)
    return f'{value:,.{dec}f}'.rstrip('0').rstrip('.')


def text_width(text, size):
    """估算文本像素宽度：全角按 1.0em，半角按 0.55em。

    仅用于溢出检查与换行决策；实际对齐交给 SVG 的 `text-anchor`，
    所以估算偏一点不会让文字错位。
    """
    width = 0.0
    for ch in str(text):
        width += size * (1.0 if _is_wide(ch) else 0.55)
    return width


def _is_wide(ch):
    """是否全角/宽字符。"""
    code = ord(ch)
    return (
        0x1100 <= code <= 0x115F
        or 0x2E80 <= code <= 0xA4CF
        or 0xAC00 <= code <= 0xD7A3
        or 0xF900 <= code <= 0xFAFF
        or 0xFE30 <= code <= 0xFE6F
        or 0xFF00 <= code <= 0xFF60
        or 0xFFE0 <= code <= 0xFFE6
        or 0x20000 <= code <= 0x3FFFD
    )


def wrap(text, size, max_width):
    """按估算宽度折行，优先在空格处断，其次逐字断。返回行列表。"""
    if text_width(text, size) <= max_width:
        return [text]
    lines, current = [], ''
    for ch in str(text):
        candidate = current + ch
        if text_width(candidate, size) > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


# ---------------------------------------------------------------- 画布

class Svg:
    """一个 SVG 文档。所有方法只追加元素，最后由 `save()` 落盘。"""

    def __init__(self, width, height, theme):
        self.w = width
        self.h = height
        self.t = theme
        self.ops = []

    # ---- 图元 ----

    def rect(self, x, y, w, h, fill, rx=0, opacity=None):
        attrs = f'x="{x:.2f}" y="{y:.2f}" width="{max(w, 0):.2f}" height="{max(h, 0):.2f}"'
        if rx:
            attrs += f' rx="{rx}"'
        if opacity is not None:
            attrs += f' opacity="{opacity}"'
        self.ops.append(f'<rect {attrs} fill="{fill}"/>')

    def line(self, x1, y1, x2, y2, stroke, width=1, dash=None, opacity=None):
        attrs = f'x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}"'
        if dash:
            attrs += f' stroke-dasharray="{dash}"'
        if opacity is not None:
            attrs += f' opacity="{opacity}"'
        self.ops.append(f'<line {attrs} stroke="{stroke}" stroke-width="{width}"/>')

    def path(self, d, fill='none', stroke=None, width=2, opacity=None, dash=None):
        attrs = f'd="{d}" fill="{fill}"'
        if stroke:
            attrs += (f' stroke="{stroke}" stroke-width="{width}"'
                      ' stroke-linejoin="round" stroke-linecap="round"')
        if opacity is not None:
            attrs += f' opacity="{opacity}"'
        if dash:
            attrs += f' stroke-dasharray="{dash}"'
        self.ops.append(f'<path {attrs}/>')

    def polyline(self, points, stroke, width=2.5, opacity=None, dash=None):
        """points: [(x, y), ...] 像素坐标。"""
        if len(points) < 2:
            return
        d = ' '.join(f'{x:.2f},{y:.2f}' for x, y in points).replace(' ', ' L ')
        self.path(f'M {d}', stroke=stroke, width=width, opacity=opacity, dash=dash)

    def polygon(self, points, fill, opacity=None):
        """闭合多边形（面积带/面积图）。"""
        if len(points) < 3:
            return
        coords = ' '.join(f'{x:.2f},{y:.2f}' for x, y in points).replace(' ', ' L ')
        self.path(f'M {coords} Z', fill=fill, opacity=opacity)

    def circle(self, cx, cy, r, fill, stroke=None, stroke_width=2):
        attrs = f'cx="{cx:.2f}" cy="{cy:.2f}" r="{r}"'
        if stroke:
            attrs += f' stroke="{stroke}" stroke-width="{stroke_width}"'
        self.ops.append(f'<circle {attrs} fill="{fill}"/>')

    def text(self, x, y, s, size=14, fill=None, weight='normal', anchor='start',
             baseline='auto', opacity=None):
        """一段文本。`anchor`: start/middle/end；`baseline`: auto/middle/hanging。"""
        attrs = (f'x="{x:.2f}" y="{y:.2f}" font-family="{FONT_STACK}" font-size="{size}"'
                 f' text-anchor="{anchor}" dominant-baseline="{baseline}"')
        if weight != 'normal':
            attrs += f' font-weight="{weight}"'
        if opacity is not None:
            attrs += f' opacity="{opacity}"'
        self.ops.append(f'<text {attrs} fill="{fill or self.t["ink"]}">{esc(s)}</text>')

    def text_block(self, x, y, lines, size=15, fill=None, weight='normal', anchor='start',
                   line_height=None):
        """多行文本，返回下一行 y。"""
        step = line_height or round(size * 1.55)
        for i, line in enumerate(lines):
            self.text(x, y + i * step, line, size=size, fill=fill, weight=weight, anchor=anchor)
        return y + len(lines) * step

    def save(self, path):
        """写出 SVG，返回字节数。目录不存在则创建。"""
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}"'
                f' viewBox="0 0 {self.w} {self.h}" role="img">')
        background = (f'<rect x="0" y="0" width="{self.w}" height="{self.h}"'
                      f' fill="{self.t["bg"]}"/>')
        doc = '\n'.join([head, background, *self.ops, '</svg>', ''])
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(doc)
        return len(doc.encode('utf-8'))


# ---------------------------------------------------------------- 坐标系

class Axes:
    """像素矩形内的数据坐标系。x 向右、y 向上（数据语义），对外换算成像素。"""

    def __init__(self, svg, rect, x_domain, y_domain):
        self.s = svg
        self.x, self.y, self.w, self.h = rect
        self.x0, self.x1 = x_domain
        self.y0, self.y1 = y_domain

    def px(self, value):
        span = self.x1 - self.x0
        return self.x + (0.0 if span == 0 else (value - self.x0) / span * self.w)

    def py(self, value):
        span = self.y1 - self.y0
        return self.y + self.h - (0.0 if span == 0 else (value - self.y0) / span * self.h)

    def points(self, xs, ys):
        return [(self.px(x), self.py(y)) for x, y in zip(xs, ys)]

    def grid_y(self, ticks, labels, color, label_size=13, dim=False):
        """横向网格线 + 左侧刻度标签。"""
        for tick, label in zip(ticks, labels):
            y = self.py(tick)
            if not dim or tick != 0:
                self.s.line(self.x, y, self.x + self.w, y, color, 1)
            self.s.text(self.x - 10, y, label, size=label_size, fill=self.s.t['mute'],
                        anchor='end', baseline='middle')

    def baseline_y(self, value, color, width=1.5):
        """零轴等强调线。"""
        y = self.py(value)
        self.s.line(self.x, y, self.x + self.w, y, color, width)

    def labels_x(self, ticks, labels, color, size=13, offset=22):
        for tick, label in zip(ticks, labels):
            self.s.text(self.px(tick), self.y + self.h + offset, label, size=size,
                        fill=color, anchor='middle')
