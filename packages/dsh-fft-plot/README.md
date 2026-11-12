# @dsh-ft/dsh-fft-plot

FTShare 数据出图。随包分发一个 skill `dsh-fft-plot`：把 FTShare 接口返回的数据渲染成
SVG，图直接内联在对话里显示。

## 形态

大幅改动一般不需要。要换数据字段只改 spec；要加图型只改 `charts.py`。

```
dsh-fft-plot/
├── src/index.js                         skill provider（纯 JS，无构建）
├── cordis.patch.yml                     一行 insert
└── skills/dsh-fft-plot/
    ├── SKILL.md                         给模型看：何时画、画哪种、字段怎么填
    └── scripts/
        ├── plot.py                      CLI：spec(JSON) → SVG
        └── ftplot/
            ├── theme.py                 配色主题（键名固定）
            ├── canvas.py                SVG 画布、坐标系、日期/数值格式
            ├── charts.py                图型注册表 @chart('名字')
            └── spec.py                  spec 与数据加载
```

## 为什么不用 matplotlib

matplotlib 约 200MB，而 DSH 自带 Python 里没有它，装一个 skill 要拉这么大一坨不划算。
这里手写 SVG，只用标准库：

| | matplotlib | 本包 |
| --- | --- | --- |
| 依赖 | ~200MB | 0 |
| 单图体积 | 58KB | 3–20KB |
| 文字 | 转成路径，不可搜索 | 真 `<text>`，可选中可搜索 |

代价是图元要自己维护（`canvas.py` 283 行 + `charts.py` 454 行），换来零依赖与样式完全可控。

## 加一种图

`charts.py` 里写一个函数加装饰器即可：

```python
@chart('curve')
def curve(c, rect, cfg, rows):
    """期限结构曲线。字段：x, series"""
    ...
```

签名固定 `(c, rect, cfg, rows)`；颜色一律走 `resolve_color(c.t, ...)`，不写死。
然后在 `SKILL.md` 的图型表补一行字段说明——那是模型选图的依据。

**不需要**改 `plot.py` 或任何布局代码。

## 本地验证

```bash
python3 skills/dsh-fft-plot/scripts/plot.py --spec spec.json --out /abs/chart.svg
```

产物是自包含 SVG（浅色底、无外链、无脚本），可直接写进 Markdown 图片语法。

## 两条设计约束

- **浅色底不透明**：SVG 作为 `<img>` 内联时是独立文档，读不到宿主的
  `body[data-ds-dark-theme]`，深色模式下只有自带底色才不会黑底黑字。
- **布局单游标**：头部、绘图区、说明、结论、页脚全部由 `plot.py` 一个游标顺序排，
  图型不得自己贴底边写字——那样必然和结论行重叠（已踩过）。
