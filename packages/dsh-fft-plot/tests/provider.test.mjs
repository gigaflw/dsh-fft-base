/**
 * The plot package ships no compiled half, so these tests guard the two things
 * that can silently break without a type checker: the skill provider contract
 * the host expects, and the plotting scripts' behaviour on the shapes FTShare
 * actually returns.
 *
 * @module @dsh-ft/dsh-fft-plot/tests
 */

import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'

const { CANDIDATE, RESOURCE_BASE, SKILL_NAME, installedRuntime, provider, stripFrontmatter } =
  await import('../src/index.js')

test('candidate satisfies the skill registry contract', () => {
  // An invalid candidate makes the registry skip the provider entirely, which
  // shows up as "the skill is missing" with no error anywhere.
  assert.match(SKILL_NAME, /^[a-z0-9]+(?:-[a-z0-9]+)*$/u)
  assert.equal(CANDIDATE.name, SKILL_NAME)
  assert.equal(CANDIDATE.provider, 'dsh-fft-plot')
  assert.equal(CANDIDATE.source, 'bundled')
  assert.equal(CANDIDATE.rank, 600)
  assert.equal(CANDIDATE.invocation.modelInvocable, true)
  assert.equal(CANDIDATE.invocation.userInvocable, true)
  // The catalog truncates at 500 characters; a longer description would be cut
  // mid-sentence in the model-facing list.
  assert.ok(CANDIDATE.description.length <= 500, 'description must fit the catalog budget')
  // The catalog has to make inline drawing the default before the body loads.
  assert.match(CANDIDATE.description, /默认用本技能/u)
  assert.match(CANDIDATE.description, /直接在对话里出图/u)
})

test('resourceBase points at the bundled skill directory', () => {
  assert.equal(RESOURCE_BASE.kind, 'directory')
  assert.ok(RESOURCE_BASE.path.endsWith('/skills/dsh-fft-plot'))
  // Both files the skill needs at runtime have to travel with the package.
  assert.ok(readFileSync(join(RESOURCE_BASE.path, 'SKILL.md'), 'utf8').includes('# dsh-fft-plot'))
  assert.ok(readFileSync(join(RESOURCE_BASE.path, 'scripts/plot.py'), 'utf8').includes('def main('))
  // The body keeps the same inline-by-default rule after the skill loads.
  assert.match(readFileSync(join(RESOURCE_BASE.path, 'SKILL.md'), 'utf8'), /默认直接出图/u)
})

test('frontmatter is stripped and the runtime note names no external toolchain', async () => {
  const skill = await provider.get(CANDIDATE)
  assert.ok(!skill.content.startsWith('---'), 'frontmatter must not reach the model')
  assert.ok(skill.content.includes('Installed runtime'))
  assert.ok(skill.content.includes(RESOURCE_BASE.path), 'scripts must be callable by absolute path')
  // The scripts are standard-library only; a uv/pip instruction would send the
  // model looking for a toolchain this package does not need.
  const note = installedRuntime()
  assert.ok(!/uv run|\bpip install\b/.test(note))
})

test('stripFrontmatter leaves a body without frontmatter untouched', () => {
  assert.equal(stripFrontmatter('# Title\n'), '# Title\n')
  assert.equal(stripFrontmatter('---\nname: x\n---\n\n# Title\n'), '# Title\n')
})

test('renders every chart type into a self-contained SVG', () => {
  const python = findPython()
  const shapes = {
    'line': {
      chart: { type: 'line', x: 'd', x_kind: 'category',
        series: [{ col: 'v', label: '热度' }], marks: ['20260810'] },
      rows: [
        { d: '20260810', v: 10 }, { d: '20260811', v: 30 }, { d: '20260814', v: 20 },
      ],
    },
    'barh': {
      chart: { type: 'barh', label: 'n', value: 'v', sign: 'chg', top: 3, fmt: 'compact' },
      rows: [
        { n: '甲', v: 3000000, chg: 1.2 }, { n: '乙', v: 2000000, chg: -0.8 },
        { n: '丙', v: 1000000, chg: 0 },
      ],
    },
    'table': {
      chart: { type: 'table', columns: [{ col: 'n', label: '名称' }, { col: 'v', label: '值' }] },
      rows: [{ n: '甲', v: 1 }, { n: '乙', v: 2 }],
    },
  }

  const dir = mkdtempSync(join(tmpdir(), 'ft-plot-'))
  for (const [name, shape] of Object.entries(shapes)) {
    const specPath = join(dir, `${name}.json`)
    const outPath = join(dir, `${name}.svg`)
    writeFileSync(specPath, JSON.stringify(shape))
    execFileSync(python, [join(RESOURCE_BASE.path, 'scripts/plot.py'),
      '--spec', specPath, '--out', outPath], { stdio: 'pipe' })

    const svg = readFileSync(outPath, 'utf8')
    assert.ok(svg.startsWith('<svg'), `${name}: must be a standalone SVG document`)
    assert.ok(svg.includes('</svg>'), `${name}: document must be closed`)
    // Inlined as <img>, a script or external reference would be dead weight at
    // best and a sandbox escape at worst.
    assert.ok(!/<script|href="https?:/u.test(svg), `${name}: must carry no script or remote reference`)
    // Real <text> keeps labels selectable and searchable; paths would not be.
    assert.ok(svg.includes('<text'), `${name}: labels must be text elements`)
  }
})

test('a shape that cannot be drawn fails loudly instead of drawing nothing', () => {
  const python = findPython()
  const dir = mkdtempSync(join(tmpdir(), 'ft-plot-bad-'))
  const specPath = join(dir, 'bad.json')
  // `v` is missing on the second row: a chart that silently dropped it would
  // understate the series without any signal to the reader.
  writeFileSync(specPath, JSON.stringify({
    chart: { type: 'barh', label: 'n', value: 'v' },
    rows: [{ n: 'a', v: 1 }, { n: 'b' }],
  }))
  assert.throws(() => execFileSync(python, [
    join(RESOURCE_BASE.path, 'scripts/plot.py'), '--spec', specPath, '--out', join(dir, 'x.svg'),
  ], { stdio: 'pipe' }))
})

/** The DSH bundled Python, falling back to whatever `python3` is on PATH. */
function findPython() {
  for (const candidate of ['python3', 'python']) {
    try {
      execFileSync(candidate, ['-c', 'import sys'], { stdio: 'pipe' })
      return candidate
    } catch { /* try the next one */ }
  }
  throw new Error('no python interpreter found; the plotting scripts need one')
}
