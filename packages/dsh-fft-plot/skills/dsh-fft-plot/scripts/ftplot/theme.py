"""配色主题。每套主题是一个 dict，键名固定。

**加主题**：复制一个 dict、改颜色即可，不需要改任何渲染代码。
**加颜色语义**：在 `_REQUIRED` 里加键名，所有主题同步补上——漏一个会在加载时立刻报错，
而不是在图上画出一块黑色。

所有主题都是浅色底（`bg` 不透明填充），这是刻意的：SVG 以 `<img>` 内联进聊天时读不到
宿主的 `body[data-ds-dark-theme]`，深色模式下它就是一张浅色图表卡片，永不会黑底黑字。
"""

#: 模板与图型只认这些键名。
_REQUIRED = (
    'bg', 'card', 'ink', 'mute', 'line',
    'up', 'down', 'neutral', 'accent', 'band',
    'title_font',
)

THEMES = {
    # 米白纸底 + 朱红/墨蓝：默认。像财经杂志内页，截图与打印都清楚。
    'paper': dict(
        bg='#FBF9F4', card='#FFFFFF', ink='#1B1B1F', mute='#6F6B66', line='#E2DCD0',
        up='#D93A3A', down='#1F5FA8', neutral='#A9A39A', accent='#C98A00', band='#1F5FA8',
    ),
    # 纯白 + 单一亮橙：极简，字更大，适合只看结论的场合。
    'poster': dict(
        bg='#FFFFFF', card='#F7F7F7', ink='#111111', mute='#7A7A7A', line='#E6E6E6',
        up='#FF5A1F', down='#111111', neutral='#C8C8C8', accent='#FF5A1F', band='#FF5A1F',
    ),
    # 冷灰底 + 青红：数据密度高的图更耐看。
    'slate': dict(
        bg='#F7F8FA', card='#FFFFFF', ink='#16181D', mute='#6B7280', line='#E1E4EA',
        up='#E5484D', down='#0A7EA4', neutral='#9AA1AE', accent='#B7791F', band='#0A7EA4',
    ),
}


def load(name='paper'):
    """取一套主题；未知名字报错并列出可选值，缺键立刻失败。"""
    if name not in THEMES:
        raise KeyError(f'unknown theme {name!r}; available: {", ".join(sorted(THEMES))}')
    theme = dict(THEMES[name])
    theme['name'] = name
    missing = [k for k in _REQUIRED if k not in theme]
    if missing:
        raise KeyError(f'theme {name!r} is missing keys: {", ".join(missing)}')
    theme.setdefault('title_font', theme.get('body_font', _FONT_STACK))
    return theme


#: 中文字体回退链。SVG 作为独立文档渲染，字体必须由自身声明，不能继承宿主。
_FONT_STACK = (
    'PingFang SC, Hiragino Sans GB, Microsoft YaHei, Noto Sans CJK SC, '
    'Source Han Sans SC, sans-serif'
)

for _t in THEMES.values():
    _t.setdefault('body_font', _FONT_STACK)
    _t.setdefault('title_font', _t['body_font'])

FONT_STACK = _FONT_STACK
