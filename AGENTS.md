# AGENTS.md

本仓是 FT 系列 DSH 插件的**共享底座**仓：`packages/` 下的三个包对外发布到 npm（scope `@dsh-ft`），
同时也被 `dsh-fft-bundle` 与 `dsh-fft-paper-trading` 按 registry 精确版本消费。

仓名是 `dsh-fft-base`，与三个包名都不完全相同（历史来源见 §定位）。这是有意为之，不是笔误。

## 定位

| 包 | 作用 | 谁用 |
| --- | --- | --- |
| `packages/dsh-fft-settings` | 设置与凭据底座：API Key、设置页卡片、运行日志、品牌主题层 | 所有 FT 插件的共享设置面 |
| `packages/dsh-fft-ftshare` | FTShare 数据底座：全 bundle 唯一出站、四态归一、随包发布上游接口目录 | 所有需要 FTShare 取数的插件 |
| `packages/dsh-fft-plot` | 数据出图：随包分发 `dsh-fft-plot` skill，把接口返回渲染成内联 SVG（零第三方依赖） | 金融模式的取数结论 |

三个包**互不依赖**（发布层零依赖边）。运行期 `ftshare` 通过 cordis `inject: ['ftshareSettings']`
拿到设置服务，类型上只声明自己需要的最小结构；不要在源码里重新引入跨包 `import`。

## 目录

```
packages/dsh-fft-settings/   设置底座（含 client 半，tsdown 打 CJS）
packages/dsh-fft-ftshare/    数据底座（含 catalog 生成脚本）
packages/dsh-fft-plot/       数据出图（纯 JS 无构建；Python 脚本只用标准库）
scripts/publish-if-new.mjs   发版脚本：按依赖序发布版本号未变的包
.github/workflows/publish.yml   tag v* 触发，OIDC 发布到 npm
```

## 发版

- 版本号在**各包自己的** `package.json` 里独立递增；仓库根的 tag 是整仓发版号（`vX.Y.Z`），
  不是任何 npm 包的版本。
- `CHANGELOG.md` 每段写清本仓 tag 与三个包各自的版本，CI 只发布版本号没在 registry 上出现过的包。
- 发版：改版本 + CHANGELOG → `pnpm build && pnpm test` → 提交 `release: vX.Y.Z` → 打 tag → 推 tag。
- 认证走 **npm OIDC trusted publishing**（GitHub Actions `id-token: write`），不需要任何 npm token。
- **不要设 `NPM_CONFIG_PROVENANCE`**：本仓是私有仓库，私有源仓无法生成 provenance，打开会直接失败。
- 不要建 GitHub Release：本仓只做 npm 发布。

## 开发

```bash
pnpm install
pnpm build && pnpm test
```

- 宿主包（`@deepseek-ai/*`）在根 `pnpm-workspace.yaml` 的 catalog / overrides 里钉版本，两处必须同版。
  新增宿主 peer 时按报错补一行，不要在包内写死版本。
- `packages/dsh-fft-settings/tests/theme.test.mjs` 的调色板断言需要 DSH 源码：设 `DSH_HARNESS_ROOT`
  指向一个 harness checkout，否则该用例按配方跳过。
- 提交规范与工作区一致：`git commit -s`，title 用 `type: ` 前缀，用户可感知改动在正文写 `RN:` 行。
- push 前先取得用户确认；agent 只准备提交、打印命令。
