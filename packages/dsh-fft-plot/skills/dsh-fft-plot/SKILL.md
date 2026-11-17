---
name: dsh-fft-plot
description: 把 FTShare 接口返回的数据渲染成图，图直接显示在聊天流里（内联 SVG，无需点开侧栏）。用于热榜、板块、资金流、估值、财报、宏观、指数等结果的趋势、排名、分布、对比，也支持热力图、构成图、瀑布图、事件时间轴与产业链示意图。用户要画图/出图/可视化时默认用本技能，直接在对话里出图。
---

# dsh-fft-plot：数据 → 内联图

## 默认直接出图

用户要图时，默认直接在对话里出内联 SVG，不要打开侧栏，也不要先问“要不要出图”。

## 一句话流程

```
取到 rows（已经是扁平行数组）
  → 写一个 spec.json（选图型 + 映射列名）
  → plot.py --spec spec.json --out-dir "$(pwd)/.dsh/plots" --slug 图名
  → 把 stdout 打印的绝对路径写进 ![说明](/abs/path.svg)
```

`--out-dir` 会按 spec + 数据内容生成 `<slug>-<hash>.svg`：同一张图重复生成不会改名，
旧消息里的引用不会被后一次渲染覆盖。**产物路径以 stdout 为准**，不要自己猜文件名。

图会直接出现在聊天流中间。**不要**调用 `present`，也不要点开侧栏。

## 必守的八条

1. **产物路径必须是绝对路径**（`/` 开头）。Markdown 图片语法里的相对路径不会渲染。
2. **图直接内联，不要 present**。产物写进 `![](/abs/path.svg)`，图会出现在回复中间；
   不要调用 `present` 让用户另外点开侧栏——那多一次点击，而这里要的就是一眼看到。
3. **图前后要有文字**。图是论点的配图，不是答复本身——图前一句交代看什么，图后一句给结论。
   但**不要在正文复述图上每个数字**，图已经显示了。
4. **同一回复不要重复画同一张图**。要改就重新生成一张并替换引用，不要叠加两张近似图。
5. **不适用的情形不画**：数据为空、只有一条记录、纯名录字段、或用户只要一个数字。
   这时直接说结论，不要为了出图而出图。
6. **不编造数字**。图上每个数字都必须来自 `rows`。
7. **产物必须是带完整根属性的独立 SVG**：`xmlns`、`width`、`height`、`viewBox` 四者齐全。
   `viewBox` 只定义坐标系，**不提供内在尺寸**；缺 `width`/`height` 时，`![](x.svg)` 在多数
   Markdown 渲染器里会塌成 0 高——对方只看到空白，而你自己用浏览器直接打开文件却是正常的，
   所以这个错误**自测发现不了**。`plot.py` 会自动写全这四个属性；手写或二次加工 SVG 时
   必须自己补，并且跑一次 `scripts/check_svg.py`。
8. **不要为了验证或显示把 SVG 转成 PNG**。`qlmanage`、`sips`、浏览器截图都不是必需步骤：
   图由 Markdown 直接内联，渲染器会显示 SVG。需要校验产物时只用 `scripts/check_svg.py`；
   不要启动系统看图/转换服务，也不要把临时 PNG 当成交付物。

## 四步

### 1. 判断该不该画

| 该画 | 不该画 |
|---|---|
| 有时间趋势（净值、热度、估值序列、宏观） | 纯名录/字典（基金列表、成分股清单） |
| 有横截面排名（热榜、板块涨幅、龙虎榜） | 只有 1 条记录 |
| 有多项构成/拆解（市值构成、资金流拆解） | 字段含义不明（不知道单位是元还是万元） |
| 有事件驱动的时点（政策、公告、数据） | 用户只要一个数字或一句话结论 |
| 用户明确说画图 | |

### 2. 选图型

| type | 用在哪 | 必填字段 |
|---|---|---|
| `line` | 时序趋势：热度衰减、净值曲线、估值分位、宏观指标 | `x`、`series` |
| `barh` | 横截面排名：热榜、板块涨幅、个股贡献 | `label`、`value` |
| `table` | 名录类数据，或作为图的补充（可带 sparkline 列） | `columns` |
| `heatmap` | 相关性矩阵、板块×时间热力、事件日历 | `x`、`y`、`value` |
| `treemap` | 市值/权重/板块构成，面积即占比 | `label`、`value`（必须为正） |
| `waterfall` | 资金流、营收/利润的逐项拆解与合计 | `label`、`value` |
| `timeline` | 政策/公告/数据等事件时点 | `x`、`label` |
| `chain` | 产业链、传导链等声明式分层示意图 | `layers`（+ `edges`） |

### 3. 写 spec 并渲染

```bash
python3 <skill目录>/scripts/plot.py --spec /abs/spec.json --out-dir "$(pwd)/.dsh/plots" --slug 热榜
```

spec 是 **JSON**（不是 YAML）。数据少就内联 `rows`，多就写 `data` 指向 json 文件。
`chain` 不需要数据行，可以不写 `rows`/`data`。

需要具体色值/字号时先跑 `plot.py --tokens`（可加 `--theme ashare`），
打印当前主题的配色、分类色、字号与版心尺寸；**不要凭记忆写颜色**。

### 4. 校验产物

```bash
python3 <skill目录>/scripts/check_svg.py /abs/输出.svg
```

必须 PASS。它查：根元素四个属性是否齐全且为正、`viewBox` 与 `width`/`height` 宽高比是否一致、
是否为合法 XML、是否含 NaN/Infinity、是否含 `<script>`/内联事件/`<foreignObject>`/外部引用。
体积超过 200KB 会给告警。

## spec 结构

```json
{
  "theme": "paper",
  "width": 1200,
  "height": 560,
  "data": "rows.json",
  "chart": { "type": "barh", "...": "见下文" },
  "legend": "条形长度=热度值；颜色=当日涨跌（红涨蓝跌）",
  "notes": ["**主结论一行", "!强调色结论", "*小字口径说明"],
  "sources": ["ft_v1_ths_hot_list"],
  "sample": "样本：20260810 当日榜单前 10 条"
}
```

**页头全部可选**（`chip` / `title` / `subtitle`）。图在聊天流中间时，前后已有文字说明，
**默认不写标题**，绘图区会占满。`legend`/`notes`/`sources`/`sample` 会自动按画布宽度折行。

`notes` 前缀：`**` 加粗主结论、`!` 红字强调、`*` 小字注释、无前缀为普通灰字。

## 各图型字段

### line

```json
{"type":"line","x":"trade_date","x_kind":"category",
 "series":[{"col":"hotValue","label":"热度","color":"down"}],
 "area":true,
 "marks":["20260810","20261110"],
 "annotate":[{"x":"20261110","text":"名次 #3","dy":16}],
 "refs":[{"y":50,"label":"五五开"}],
 "band":{"lo":"p25","hi":"p75","label":"中间一半分布"},
 "y_fmt":"num","y_dec":0}
```

- `x_kind`：**日期列必须写 `"category"`**。日期若写成 `20260810` 这类可解析整数，
  按数值画会导致交易日间距忽宽忽窄（跨周末的间隔是 3 而不是 1）。
  纯数值轴（天数、比率）才用 `"auto"`。
- `series[].color`：主题键 `up`/`down`/`neutral`/`accent`/`band`，或 `#RRGGBB`；
  多序列不写 color 时按主题的 6 色分类板自动分配。
- `series`/`band` 的值允许 `null`：该点画成断开的间隙，不会连成假线。
- `include_zero`：**默认 false**。价格、指数、净值这类不应从 0 起画；
  数量/资金/占比类图才显式写 `"include_zero": true`。
- `y_fmt`：`num` / `pct` / `compact`；`y_dec` 不够时会按刻度步长自动补足小数位。
- `band`：分布带，用于给出离散度而不是只有均值。
- `refs`：参考线（50%、0、基准值）。
- `marks`：要打点的 x 值，会标出数值；**写了一个数据里不存在的 x 会直接报错**。

### barh

```json
{"type":"barh","label":"name","value":"hotValue","sign":"riseAndFall",
 "rank":"rank","top":10,"fmt":"compact","dec":1}
```

- `sign`：决定颜色的列（红色=正、蓝色=负；没有 sign 时整组同色）。
- 有负值时条形以 0 为基线向两侧展开；放不下时自动截断并在图内写“共 N 条，显示前 k 条”。
- `fmt`：`compact`（524.9万，**推荐**）、`num`（5,248,899）、`pct`（+4.2%）。
  用 `compact` 时把单位写进数值，就不必再单独加一行“单位是…”的说明。

### table

```json
{"type":"table","top":12,"font_size":13,"row_height":32,
 "columns":[
   {"col":"rank","label":"名次","weight":0.5,"align":"right"},
   {"col":"name","label":"名称","weight":1.1},
   {"col":"hotValue","label":"热度值","weight":1.0,"align":"right","fmt":"compact","dec":0},
   {"col":"trend","label":"近 5 日","type":"sparkline","weight":1.0}]}
```

- `weight`：列宽比例；`align`：`left`/`right`；`dec`：小数位；`fmt`：`num`/`pct`/`compact`。
- `type: "sparkline"` 的列，值必须是数字数组（如 `[1,2,1.5,3]`），画迷你走势线。
- 行数放不下时自动截断并写“共 N 条，显示前 k 条”；缺列会直接报错，不静默写 `—`。

### heatmap

```json
{"type":"heatmap","x":"trade_date","y":"name","value":"pct",
 "fmt":"pct","dec":1,"show_value":true,"diverging":true,"top":20}
```

- 行是 `y` 的取值、列是 `x` 的取值，按行序/首次出现顺序排列；同一格重复取最后一行。
- `diverging` 默认按数据正负自动判断：红=正、蓝=负；全正/全负时用单色深浅。
- `show_value` 在格子里写数值；格子太小时不写。
- 行数按高度放不下会直接报错（提示调大 height、调小 top 或改用 table）。

### treemap

```json
{"type":"treemap","label":"name","value":"mktcap","group":"sector","fmt":"num","dec":0}
```

- 面积=数值；`group` 决定颜色（同一分组同色），不写则按顺序取分类色。
- 值必须为正数；块太小时只画色块不写标签。
- 数据单位不是元时用 `fmt: "num"`，把单位（亿元/万元）写进 `legend`，不要用 compact 误缩放。

### waterfall

```json
{"type":"waterfall","label":"item","value":"amount","fmt":"num","dec":1,
 "type_col":"type","sort":false}
```

- 每行是一个增量，从前一根终点起画；正增量红、负增量蓝。
- `type_col` 指向的列值为 `total`/`合计`/`汇总` 时，该行从 0 起画整根（用于合计）。
- 默认不排序（保持业务顺序）；`sort: true` 按数值重排。

### timeline

```json
{"type":"timeline","x":"date","label":"event","sign":"impact","detail":"detail"}
```

- 按日期定位事件点；日期无法全部识别时保留行序。x 轴标签自动收敛与抽稀。
- `sign` 正负决定颜色（红=利多、蓝=利空）；不给则用 `color`（默认 accent）。
- `detail` 是可选的事件说明小字。
- 事件标签最多三层交错；仍放不下的会省略，并在图内写明“N 个标签过密未显示”。

### chain

```json
{"type":"chain",
 "layers":[{"name":"上游","nodes":["锂矿","正极材料"]},
           {"name":"中游","nodes":["动力电池"]},
           {"name":"下游","nodes":["新能源车","储能"]}],
 "edges":[["锂矿","正极材料"],["正极材料","动力电池"],["动力电池","新能源车"]],
 "highlight":["动力电池"]}
```

- 节点名同时是边的引用 id，必须全局唯一；`layers` 从左到右，层名可选。
- 边只能从靠前层指向靠后层，或同层节点之间（同层画竖箭头）；反向边直接报错。
- `highlight` 的节点用强调色描边；放不下会先缩字号、再报错，不会画出压字的图。
- 更自由的架构图/泳道图用下面的“手写 SVG”。

## 数据形状的坑

上游返回的字段与单位不统一，映射前先确认：

- **比率二义**：`turnover_rate=0.0123` 是小数，`riseAndFall=15.07` 是百分数。
  图上的 `y_fmt: "pct"` 只负责加 `%`，**不负责乘 100**——先看清原始量纲。
- **时间有五种写法**：毫秒/秒/纳秒时间戳、`20260810`、`2026-08-10`、`2026-09-30 00:00:00`、
  `2026年09月份`；`plot.py` 统一按上海时区解析，认不出的日期原样当标签。
- **列集可能随行变化**：`y_30y` 这类列只在部分行出现。数值列缺键或出现 `NaN/Infinity`
  会直接报错（不会静默丢行）；要表示“没有数据”的间隙，用 JSON `null`（仅 line 的 series/band 支持）。
- **分页**：很多接口默认只返回第一页。横截面分布用第一页画会系统性失真，
  要么按全量取，要么在图里写明样本范围。

## 配色

`paper`（米白+朱红墨蓝，默认）、`ashare`（米白+红涨绿跌，给 A 股读者看涨跌时用）、
`poster`（纯白+亮橙）、`slate`（冷灰+青红）。
所有主题都是浅色底：SVG 内联进聊天时读不到宿主的深色模式，浅色底保证永不错色。
具体色值/分类色/字号用 `plot.py --tokens` 取，不凭记忆写。

## 手写 SVG：允许，但必须补齐根属性

`plot.py` 覆盖不到的复合图——双 panel 对照、自定义标注层、非链式的架构/泳道图——
可以直接生成 SVG。根元素必须是：

```
<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540"
     viewBox="0 0 960 540" role="img" aria-label="一句话把这张图读出来">
```

- **四个属性一个都不能少**：缺 `xmlns` → 独立文档解析失败；缺 `width`/`height` →
  作为 `<img>` 引用塌成空白。两种症状不同，都只能靠校验抓。
- `width`/`height` 用纯数字，且与 `viewBox` 同比例，否则 `<img>` 里会被拉伸。
- 自绘也要用浅色底打底（`<rect fill>`），颜色用 `--tokens` 里的语义键值，不写随机色。
- 生成后**必须**过 `check_svg.py`；不要用“浏览器打开看着正常”代替校验。
- 图上每个数字同样受第 6 条约束：来自数据，不来自手写常量。

### 示意图几何速查

- 画布四边至少留 `24px`；节点圆角 `rx≈10`、描边 `1.25–1.5`。
- 节点宽度：ASCII 约 `字数×9+36`，中文约 `字数×15+36`；单行高 `≥44`，标题+副标题 `≥64`。
- 有连接的层之间至少留 `48px` 走线；连线绕开节点，标签压在线上时给文字加一块浅色底衬。
- 箭头用 `<marker>` 定义一次，`refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"`。
- 泳道/分组用 `fill` 浅底 + 虚线描边 + 左上角 12px 分组名，不要用纯色块压过节点。

## 新增图型

`scripts/ftplot/charts.py` 里写一个函数并加装饰器，签名固定 `(c, rect, cfg, rows)`：

- `@chart('名字')`：普通数据图；
- `@chart('名字', x_axis=True)`：图型自己画横轴标签，`plot.py` 会自动预留横轴高度；
- `@chart('名字', needs_rows=False)`：示意图类，spec 可以不写 `rows`/`data`。

然后在本文的图型表里补一行字段说明。**不需要**改 `plot.py` 或任何布局代码。
