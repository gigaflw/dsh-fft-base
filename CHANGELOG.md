# Changelog

本仓所有值得记录的改动。格式基于 [Keep a Changelog](https://keepachangelog.com/)，版本遵循
[Semantic Versioning](https://semver.org/)。

版本段标题是**整仓发版号**（与 git tag 一致），不是任何 npm 包的版本；
每个版本段在 `### Packages` 里列出本次实际发布的包版本。CI 只发布版本号尚未出现在
registry 上的包，因此「没改的包不出现在本段」等价于「它没有新版本」。

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

[0.1.0]: https://github.com/gigaflw/dsh-fft-base/releases/tag/v0.1.0
