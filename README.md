# dsh-fft-base

FT 系列 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) 插件的共享底座：
两个独立发布到 npm 的包，加一个把它们一起发出去的私有仓。

> 仓名与包名不完全相同，是历史原因：本仓由早先的 `dsh-ftshare-settings` 仓改名的。
> 包名以 npm 上名为准——`@dsh-ft/dsh-fft-settings`、`@dsh-ft/dsh-fft-ftshare`。

## 包

| 包 | 说明 | 安装 |
| --- | --- | --- |
| [`@dsh-ft/dsh-fft-settings`](packages/dsh-fft-settings/README.md) | 设置与凭据底座：FTShare API Key、设置页卡片、运行日志、品牌主题层 | `dsh plugin --profile <name> add @dsh-ft/dsh-fft-settings` |
| [`@dsh-ft/dsh-fft-ftshare`](packages/dsh-fft-ftshare/README.md) | FTShare 数据底座：唯一出站、四态归一、随包发布上游接口目录 | `dsh plugin --profile <name> add @dsh-ft/dsh-fft-ftshare` |

两个包互不依赖，各自独立发版，版本号不必相同。

安装整套 FT 工作台请用聚合包 [`@ft/dsh-fft-bundle`](https://github.com/gigaflw/dsh-fft-bundle)，
它会按精确版本带入这里两个包；单独装这里的包只拿到对应的一层能力。

## 开发

```bash
pnpm install
pnpm build && pnpm test
```

宿主包（`@deepseek-ai/*`）的版本在根 `pnpm-workspace.yaml` 的 catalog 与 overrides 两处钉定，
必须同版。调色板断言需要 DSH 源码：把 `DSH_HARNESS_ROOT` 指向一个 harness checkout，否则该用例跳过。

## 发版

```bash
# 1. 改 packages/*/package.json 的版本与 CHANGELOG.md
pnpm build && pnpm test
git commit -s -m 'release: vX.Y.Z'
git tag -a vX.Y.Z -m vX.Y.Z
git push github vX.Y.Z        # 触发 .github/workflows/publish.yml
```

tag 是整仓发版号；CI 只发布版本号尚未出现在 registry 上的包，重跑同一个 tag 安全。
认证走 npm trusted publishing（OIDC），不依赖任何 token；本仓为私有仓库，不生成 provenance，
也不建 GitHub Release。
