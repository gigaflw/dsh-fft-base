/**
 * Bundled `ft-plot` skill provider for DeepSeek Harness.
 *
 * Registers the packaged plotting skill on the `ctx.skills` registry so every
 * session sees it in the model-facing catalog and the `/` menu, without anyone
 * copying files into `$DSH_HOME/skills`.
 *
 * The host half deliberately owns no runtime state and imports no
 * `@deepseek-ai/*` package: the plotting scripts are standard-library Python, so
 * the plugin installs with no build step and cannot split a Cordis module
 * instance when a profile links it from a source directory.
 *
 * @module @dsh-ft/dsh-fft-plot
 */

import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

/** Provider name in the `ctx.skills` registry. */
export const PROVIDER_NAME = 'dsh-fft-plot'

/** Skill name the model loads and the `/` menu lists. */
export const SKILL_NAME = 'dsh-fft-plot'

const SKILL_DIR_URL = new URL('../skills/dsh-fft-plot/', import.meta.url)

/**
 * Relative paths inside SKILL.md resolve against the bundled skill directory.
 * `fileURLToPath` keeps a trailing separator for directory URLs, which would
 * double up in the paths this provider renders, so normalize it away.
 */
const RESOURCE_BASE = { kind: 'directory', path: resolve(fileURLToPath(SKILL_DIR_URL)) }

/**
 * Precedence rank for a packaged skill provider. Matches `BUNDLED_SKILL_RANK`
 * from `@deepseek-ai/dsh-skill`; the literal keeps this package dependency-free.
 */
const PACKAGED_SKILL_RANK = 600

/**
 * Description rendered in the model-facing skill catalog (truncated at 500
 * characters by `@deepseek-ai/dsh-skill`). It has to carry every trigger
 * phrase the model might match against, because the skill body is loaded only
 * after the model decides to call `skill`. Keep it in sync with the
 * `description` frontmatter in SKILL.md.
 */
const DESCRIPTION = '把 FTShare 接口返回的数据渲染成图，图直接显示在聊天流里（内联 SVG，无需点开侧栏）。'
  + '用于热榜、板块、资金流、估值、财报、宏观、指数等结果的趋势、排名、分布、对比。'
  + '当用户说画图/出图/可视化/来张图，或在分析金融数据后需要更直观呈现时使用。'

const CANDIDATE = {
  name: SKILL_NAME,
  description: DESCRIPTION,
  invocation: { modelInvocable: true, userInvocable: true },
  provider: PROVIDER_NAME,
  source: 'bundled',
  resourceBase: RESOURCE_BASE,
  rank: PACKAGED_SKILL_RANK,
  locator: new URL('SKILL.md', SKILL_DIR_URL),
}

/**
 * Skill content, with the facts a model cannot derive appended as an
 * installed-runtime note: the absolute skill directory, the output directory
 * convention, and how to reach a Python interpreter.
 */
function installedRuntime() {
  const directory = RESOURCE_BASE.path
  return [
    '',
    '## Installed runtime',
    '',
    `本 Skill 的绝对目录是 \`${directory}\`。脚本一律用这个目录拼绝对路径调用，不要依赖当前工作目录。`,
    '',
    '脚本只用 Python 标准库，**不需要 uv、不需要 venv、不需要 pip 安装**。优先用 `python3`：',
    '',
    '```bash',
    `python3 ${directory}/scripts/plot.py --spec /绝对路径/spec.json --out /绝对路径/chart.svg`,
    '```',
    '',
    '若 `python3` 不可用，用 `load_workspace_dependencies` 返回的 `python` 绝对路径替代。',
    '',
    '**产物路径必须写成绝对路径**，并在回复里用 Markdown 图片语法引用，图才会内联显示。',
    '',
  ].join('\n')
}

const provider = {
  name: PROVIDER_NAME,
  list() {
    return Promise.resolve([CANDIDATE])
  },
  async get(candidate) {
    const body = await readFile(candidate.locator, 'utf8')
    return {
      name: CANDIDATE.name,
      description: CANDIDATE.description,
      invocation: CANDIDATE.invocation,
      provider: CANDIDATE.provider,
      source: CANDIDATE.source,
      resourceBase: RESOURCE_BASE,
      content: stripFrontmatter(body) + installedRuntime(),
    }
  },
}

/**
 * The skill registry renders the body, so the YAML frontmatter belongs to the
 * on-disk copy only; leaving it in would show up verbatim in the model's
 * `<skill_content>` block.
 */
function stripFrontmatter(text) {
  const normalized = text.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n')
  if (!normalized.startsWith('---\n')) return normalized
  const end = normalized.indexOf('\n---', 3)
  if (end === -1) return normalized
  const afterFence = normalized.indexOf('\n', end + 1)
  return afterFence === -1 ? '' : normalized.slice(afterFence + 1).replace(/^\n+/, '')
}

/** Cordis plugin name. */
export const name = '@dsh-ft/dsh-fft-plot'

/** The bundled provider is only useful next to the skill registry. */
export const inject = ['skills']

/** Register the bundled plotting skill provider on `ctx.skills`. */
export function apply(ctx) {
  if (typeof ctx.skills?.registerProvider !== 'function') {
    throw new Error(
      '@dsh-ft/dsh-fft-plot requires the skill registry (@deepseek-ai/dsh-skill, service `skills`) in this composition',
    )
  }
  ctx.skills.registerProvider(() => provider)
}

export { provider, CANDIDATE, RESOURCE_BASE, installedRuntime, stripFrontmatter }
