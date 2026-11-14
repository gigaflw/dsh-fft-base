# Changelog

本仓所有值得记录的改动。格式基于 [Keep a Changelog](https://keepachangelog.com/)，版本遵循
[Semantic Versioning](https://semver.org/)。

版本段标题是**整仓发版号**（与 git tag 一致），不是任何 npm 包的版本；
每个版本段在 `### Packages` 里列出本次实际发布的包版本。CI 只发布版本号尚未出现在
registry 上的包，因此「没改的包不出现在本段」等价于「它没有新版本」。

## [1.4.1] - 2026-11-14

`plot` 发布 0.1.1：补上显示元数据（中文「FT 绘图」/英文「FT Plot」）与 npm 仓库链接，插件管理与
组合包工作台卡据此显示可读名称。仓库自本版起转为公开，发布产物带 npm provenance。

### Packages

- `@dsh-ft/dsh-fft-plot` 0.1.1

### Added

- `plot` 的 locale 元数据：`locale/zh.json` / `locale/en.json`，并加入 `exports` 与 `files`，
  宿主可在不执行插件代码的情况下读取标题与一句话说明。
- npm 元数据补齐 `author` / `homepage` / `repository` / `bugs`，npm 页面与 DSH 插件页可以指回本仓。

### Note

- 纯元数据改动：不新增依赖、不改运行代码，旧版本安装行为不变。

## [1.4.0] - 2026-11-13

`settings` 的浏览器半开始向 K 线发布可选宿主契约 `klineHost`：bundle 自己提供图表入口和首启体验，
图表据此不再画浮动 K、不再弹首启/界面升级提示。`ftshare` 与 `plot` 本次没有改动，不出现在本节。

### Packages

- `@dsh-ft/dsh-fft-settings` 0.7.1

### Added

- `settings` 客户端发布 `klineHost` 服务（`{ entry: 'tab', onboarding: 'off' }`），落地 K 线 0.6.11
  新增的可选宿主契约：只在 bundle 环境生效；单独安装 K 线时没有提供方，行为与上游默认一致。

### Note

- 纯客户端服务：不新增依赖、不改 `engines.dsh` 下限；旧版 K 线不读该服务，行为不变。

## [1.3.0] - 2026-11-13

`settings` 的设置页分区现在有自己的图标（FT 徽标），不再落到宿主的通用齿轮；分区名改为跟随
界面语言。`ftshare` 与 `plot` 本次没有改动，不出现在本节。

### Packages

- `@dsh-ft/dsh-fft-settings` 0.7.0

### Added

- `settings` 设置页「金融终端」分区显示 FT 徽标图标：注册进宿主 0.2.2 新增的
  `settings.section.icon` 槽位，与其余导航图标同笔画（1.3）、同色（继承行文字色），
  实心尺寸 13.3×13.3 与宿主图标的 12.4–14.5 区间一致。图标是矢量路径（含显式圆角弧），
  在任何 DPR 下都精确落像素。

### Changed

- `settings` 设置页分区名按界面语言解析：中文「金融终端」、其它「FT Terminal」。之前是固定
  中文，英文界面下也不变。

### Note

- 兼容 DSH 0.2.1：旧宿主不声明该槽位，`inject` 的回调不执行，分区保留宿主原齿轮，不报错。
  因此 `engines.dsh` 下限不变，无需抬版本。

## [1.2.1] - 2026-11-13

`ftshare` 刷新随包接口目录：上游新增 6 条接口，无删除、无改名。`settings` 与 `plot` 本次没有改动，
不出现在本节。

### Packages

- `@dsh-ft/dsh-fft-ftshare` 0.4.2

### Changed

- `ftshare` 随包目录 250 → 256 条：新增全市场公告列表与文件下载、定期报告列表与文件下载、
  股指期货与指数深度、上金所现货品种主档。目录是 `ftshare_call` 的准入依据，这六条在刷新前
  只能被 `ftshare_status` 报告为「与随包不一致」，无法直调。

## [1.2.0] - 2026-11-12

`settings` 增加首次启动的一次性提示，并把两个外链页面标上来源参数；`settings` 的
`ft:services` 提示词不再点名已下线的能力。`plot` 本次没有改动，不出现在本节。

### Packages

- `@dsh-ft/dsh-fft-settings` 0.6.0
- `@dsh-ft/dsh-fft-ftshare` 0.4.1

### Added

- `settings` 在首次启动时于左下角提示获取免费的 FTShare API Key：不盖遮罩、不抢焦点，
  12 秒后自动淡出（鼠标悬停时暂停），设备级只出现一次；只在确认未配置 Key 且主会话为空时
  出现，配置好 Key 后立即收起。

### Changed

- `settings` 的「获取 API Key」与 `ftshare` 的升级订阅入口都带上 `utm_source=dsh-fft`，
  站点点位据此区分来自插件的访问。申请页地址收敛为契约常量，卡片与提示共用一份。

### Fixed

- `settings` 的 `ft:services` 提示词不再点名 `cockpit_*` 工具与 `factor-intake-standard`
  技能：两者已从组合包下线，点名它们会让模型去找装不上的工具。改为点名真正挂载的
  dsh-kline 与 `ftshare_*`。测试同时改为断言「不得包含」这两个名字，避免再次回流。

## [1.1.0] - 2026-11-12

新增第三个包 `@dsh-ft/dsh-fft-plot`：把 FTShare 接口返回的数据画成图，直接内联显示在
对话里。`settings` 与 `ftshare` 本次没有改动，不出现在本节。

### Packages

- `@dsh-ft/dsh-fft-plot` 0.1.0

### Added

- `dsh-fft-plot` 随包分发一个同名 skill：模型取到 FTShare 数据后，按 `SKILL.md` 选择图型、
  写一份 JSON spec，脚本把它渲染成自包含 SVG，再由模型用 Markdown 图片语法内联进回复。
  首个版本覆盖 `line`（时序趋势）、`barh`（横截面排名）、`table`（名录与原始字段）。
- 渲染只用 Python 标准库，手写 SVG：单图 3–20KB，字符是真 `<text>`（可选中、可搜索）。
  相比 matplotlib（约 200MB 依赖、单图 58KB、文字转路径）省掉了一整套工具链。
- 配色三套（`paper`/`poster`/`slate`），全部不透明浅色底——SVG 作为 `<img>` 内联时读不到
  宿主的深色模式属性，自带底色才不会黑底黑字。
- `charts.py` 的 `@chart('名字')` 是唯一扩展点：新增图型只加一个函数并在 `SKILL.md`
  补一行字段说明，不改布局代码。

## [0.1.0] - 2026-11-05

首个版本：`@dsh-ft/dsh-fft-settings` 与 `@dsh-ft/dsh-fft-ftshare` 从
`dsh-fft-bundle` 拆出为独立仓库，各自独立发版。

### Packages

- `@dsh-ft/dsh-fft-settings` 0.5.1
- `@dsh-ft/dsh-fft-ftshare` 0.4.0

### Changed

- `ftshare` 不再依赖 `settings`：源码里原有的 `import type {}` 换成对 `ctx.ftshareSettings`
  的最小结构声明，两个包在发布层零依赖边，发布顺序不再互相约束。
- 两个包通过 GitHub Actions 以 npm trusted publishing（OIDC）发布，替代原先在
  `dsh-fft-bundle` 里手工 `pnpm pack:npm` + `upload.mjs --tag next/--promote` 的流程。

### Removed

- `settings` 的品牌 token 守护不再扫描兄弟包源码（那些消费者已不在本仓），只校验本包自身。

[1.2.0]: https://github.com/gigaflw/dsh-fft-base/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/gigaflw/dsh-fft-base/compare/v0.1.0...v1.1.0
[0.1.0]: https://github.com/gigaflw/dsh-fft-base/releases/tag/v0.1.0
