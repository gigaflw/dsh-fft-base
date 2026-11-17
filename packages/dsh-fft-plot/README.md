# @dsh-ft/dsh-fft-plot

FTShare 数据出图。随包分发一个 skill `dsh-fft-plot`：把 FTShare 接口返回的数据渲染成
SVG，图直接内联在对话里显示。

## 形态

大幅改动一般不需要。要换数据字段只改 spec；要加图型只改 `charts.py`。

```
dsh-fft-plot/
├── src/index.js                         skill provider（纯 JS，无构建）
├── cordis.patch.yml                     一行 insert
├── tests/
│   ├── fixtures/                        可重复渲染的 spec（含错误样例）
│   ├── plot.test.mjs                    渲染/报错/哈希命名/check_svg 测试
│   └── generate-samples.mjs             把所有 fixture 渲染成 SVG 供人工查看
└── skills/dsh-fft-plot/
    ├── SKILL.md                         给模型看：何时画、画哪种、字段怎么填
    └── scripts/
        ├── plot.py                      CLI：spec(JSON) → SVG；--tokens 打配色/字号
        ├── check_svg.py                 独立 SVG 校验
        └── ftplot/
            ├── theme.py                 配色主题（含 6 色分类板、ashare）
            ├── canvas.py                SVG 画布、坐标系、日期/数值格式
            ├── charts.py                图型注册表 @chart('名字')
            └── spec.py                  spec 与数据加载
```

图型：`line`、`barh`、`table`（含 sparkline 列）、`heatmap`、`treemap`、`waterfall`、
`timeline`、`chain`。`chain` 是声明式产业链/传导链示意图，不消费数据行。

## 为什么不用 matplotlib

matplotlib 约 200MB，而 DSH 自带 Python 里没有它，装一个 skill 要拉这么大一坨不划算。
这里手写 SVG，只用标准库：

| | matplotlib | 本包 |
| --- | --- | --- |
| 依赖 | ~200MB | 0 |
| 单图体积 | 58KB | 3–20KB（热力图约 50KB） |
| 文字 | 转成路径，不可搜索 | 真 `<text>`，可选中可搜索 |

代价是图元要自己维护（`canvas.py` + `charts.py` 共约 2100 行），换来零依赖与样式完全可控。

## 加一种图

`charts.py` 里写一个函数加装饰器即可：

```python
@chart('curve')                    # 普通数据图
@chart('curve', x_axis=True)       # 自己画横轴，plot.py 会预留高度
@chart('curve', needs_rows=False)  # 示意图，spec 可以不写 rows
def curve(c, rect, cfg, rows):
    """期限结构曲线。字段：x, series"""
    ...
```

签名固定 `(c, rect, cfg, rows)`；颜色一律走 `resolve_color(c.t, ...)`，不写死。
然后在 `SKILL.md` 的图型表补一行字段说明——那是模型选图的依据。

**不需要**改 `plot.py` 或任何布局代码。

## 本地验证

```bash
# 跑测试（渲染全部 fixture + 错误路径 + check_svg + 哈希命名）
pnpm test

# 把 fixture 渲染到 tests/tmp/samples/，用于人工看效果
pnpm samples

# 单张图
python3 skills/dsh-fft-plot/scripts/plot.py \
  --spec tests/fixtures/heatmap.json --out-dir tests/tmp/samples --slug heatmap
```

产物是自包含 SVG（浅色底、无外链、无脚本），可直接写进 Markdown 图片语法。
`--out-dir` 按 spec + 数据内容哈希命名，同一张图重复生成会覆盖同一个文件；
需要具体色值/字号时用 `plot.py --tokens`。

## 三条设计约束

- **浅色底不透明**：SVG 作为 `<img>` 内联时是独立文档，读不到宿主的
  `body[data-ds-dark-theme]`，深色模式下只有自带底色才不会黑底黑字。
- **先量后排**：头部、绘图区、说明、结论、页脚都先按画布宽度折行、算出真实高度，
  再由 `plot.py` 倒推绘图区；图型通过 `x_axis` 元数据声明自己要不要横轴高度。
  图型不得自己贴底边写字——那样必然和结论行重叠（已踩过）。
- **缺数据就失败**：NaN/Infinity、缺列、marks 指不到 x、示意图放不下都直接报错；
  要表达“没有数据”的间隙，用 `null` 并在图型里显式支持。
