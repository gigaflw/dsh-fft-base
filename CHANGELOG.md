# Changelog

本仓所有值得记录的改动。格式基于 [Keep a Changelog](https://keepachangelog.com/)，版本遵循
[Semantic Versioning](https://semver.org/)。

版本段标题是**整仓发版号**（与 git tag 一致），不是任何 npm 包的版本；
每个版本段在 `### Packages` 里列出本次实际发布的包版本。CI 只发布版本号尚未出现在
registry 上的包，因此「没改的包不出现在本段」等价于「它没有新版本」。

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
