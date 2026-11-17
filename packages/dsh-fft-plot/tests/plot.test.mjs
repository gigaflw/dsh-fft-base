/**
 * Reproducible rendering tests for the plotting skill.
 *
 * Every case goes through the same path the model uses: a fixture spec on disk →
 * `plot.py` → standalone SVG → `check_svg.py`. That keeps the fixtures useful as
 * visual samples (`pnpm samples`) instead of test-only throwaways.
 *
 * @module @dsh-ft/dsh-fft-plot/tests/plot
 */

import assert from 'node:assert/strict'
import { execFileSync, spawnSync } from 'node:child_process'
import { mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const SCRIPTS = join(ROOT, 'skills', 'dsh-fft-plot', 'scripts')
const FIXTURES = join(ROOT, 'tests', 'fixtures')
const RENDER_FIXTURES = ['line', 'line_timestamp', 'barh', 'table', 'heatmap', 'treemap',
  'waterfall', 'timeline', 'chain']

const python = findPython()

/** Run plot.py/check_svg.py without throwing; tests assert on the result. */
function run(script, args) {
  return spawnSync(python, [join(SCRIPTS, script), ...args], { encoding: 'utf8' })
}

/** Render one fixture into `dir` and return the SVG text and the printed output path. */
function render(name, dir) {
  const result = run('plot.py', [
    '--spec', join(FIXTURES, `${name}.json`),
    '--out-dir', dir,
    '--slug', name,
  ])
  assert.equal(result.status, 0, `${name} failed:\n${result.stderr}`)
  const path = result.stdout.trim().split(/\s+/u)[0]
  return { svg: readFileSync(path, 'utf8'), path, stdout: result.stdout }
}

test('every render fixture produces a checkable standalone SVG', () => {
  const dir = mkdtempSync(join(tmpdir(), 'ft-plot-render-'))
  for (const name of RENDER_FIXTURES) {
    const { svg } = render(name, dir)
    assert.ok(svg.startsWith('<svg'), `${name}: must start with <svg`)
    assert.ok(svg.includes('width="') && svg.includes('height="') && svg.includes('viewBox="'),
      `${name}: root must carry width/height/viewBox`)
    assert.ok(!/<script\b|href="https?:/u.test(svg), `${name}: no scripts or remote refs`)
    const file = readdirSync(dir).find((entry) => entry.startsWith(`${name}-`))
    assert.ok(file, `${name}: output file missing`)
    const checked = run('check_svg.py', [join(dir, file)])
    assert.equal(checked.status, 0, `${name} check_svg:\n${checked.stdout}${checked.stderr}`)
  }
  assert.ok(RENDER_FIXTURES.length >= 9)
  rmSync(dir, { recursive: true, force: true })
})

test('fixtures carry the visual elements their chart type promises', () => {
  const dir = mkdtempSync(join(tmpdir(), 'ft-plot-elements-'))
  const cases = {
    line: (svg) => svg.includes('MA5') && svg.includes('<circle'),
    line_timestamp: (svg) => !/>\d{13}</u.test(svg) && /-\d{2}</u.test(svg),
    barh: (svg) => svg.includes('0%') && svg.includes('+4.5%'),
    table: (svg) => svg.includes('<path'),
    heatmap: (svg) => (svg.match(/<rect/gu) ?? []).length > 100,
    treemap: (svg) => svg.includes('贵州茅台') && (svg.match(/<rect/gu) ?? []).length > 10,
    waterfall: (svg) => svg.includes('合计') && (svg.match(/stroke-dasharray/u) ?? []).length > 0,
    timeline: (svg) => (svg.match(/<circle/gu) ?? []).length >= 6,
    chain: (svg) => svg.includes('<marker') && svg.includes('动力电池'),
  }
  for (const [name, predicate] of Object.entries(cases)) {
    const { svg } = render(name, dir)
    assert.ok(predicate(svg), `${name}: expected visual elements missing`)
  }
  rmSync(dir, { recursive: true, force: true })
})

test('invalid shapes fail loudly with a message that points at the fix', () => {
  const dir = mkdtempSync(join(tmpdir(), 'ft-plot-errors-'))
  const expected = {
    nan: /not finite/u,
    missing_column: /missing at row/u,
    unknown_type: /unknown chart\.type/u,
    tiny_width: /too small/u,
    missing_mark: /not in the x column/u,
    treemap_negative: /positive values/u,
    heatmap_dense: /rows but only/u,
    timeline_missing_label: /needs "x" and "label"/u,
    chain_bad_edge: /unknown node/u,
  }
  for (const [name, pattern] of Object.entries(expected)) {
    const result = run('plot.py', [
      '--spec', join(FIXTURES, 'errors', `${name}.json`),
      '--out', join(dir, `${name}.svg`),
    ])
    assert.notEqual(result.status, 0, `${name}: must fail`)
    assert.match(result.stderr, pattern, `${name}: message when wrong:\n${result.stderr}`)
  }
  rmSync(dir, { recursive: true, force: true })
})

test('--out-dir names identical content identically and changed content differently', () => {
  const dir = mkdtempSync(join(tmpdir(), 'ft-plot-hash-'))
  const first = render('barh', dir).path
  const second = render('barh', dir).path
  assert.equal(first, second, 'same spec/data must keep the same file name')

  const changed = JSON.parse(readFileSync(join(FIXTURES, 'barh.json'), 'utf8'))
  changed.rows[0].chg = -9.9
  const tempSpec = join(dir, 'changed.json')
  writeFileSync(tempSpec, JSON.stringify(changed))
  const result = run('plot.py', ['--spec', tempSpec, '--out-dir', dir, '--slug', 'barh'])
  assert.equal(result.status, 0)
  const changedPath = result.stdout.trim().split(/\s+/u)[0]
  assert.notEqual(changedPath, first, 'changed data must get a different file name')
  rmSync(dir, { recursive: true, force: true })
})

test('--tokens prints the palette and chart catalog the model is told to trust', () => {
  const result = run('plot.py', ['--tokens', '--theme', 'ashare'])
  assert.equal(result.status, 0, result.stderr)
  const tokens = JSON.parse(result.stdout)
  assert.equal(tokens.theme, 'ashare')
  assert.equal(tokens.colors.down, '#14805E')
  assert.equal(tokens.series.length, 6)
  assert.ok(tokens.charts.includes('heatmap') && tokens.charts.includes('timeline')
    && tokens.charts.includes('chain'))
  assert.ok(tokens.chart_types.chain.x_axis === false)
})

test('check_svg rejects documents that would break as <img>', () => {
  const dir = mkdtempSync(join(tmpdir(), 'ft-plot-check-'))
  const cases = {
    script: '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10"><script>1</script></svg>',
    nan: '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10"><path d="M 1 nan"/></svg>',
    control: '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10"><text>\u0000</text></svg>',
    remote: '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10"><image href="https://x.test/a.png"/></svg>',
  }
  for (const [name, content] of Object.entries(cases)) {
    const path = join(dir, `${name}.svg`)
    writeFileSync(path, content)
    const result = run('check_svg.py', [path])
    assert.equal(result.status, 1, `${name}: must be rejected`)
    assert.match(result.stdout, /FAIL/u)
  }
  rmSync(dir, { recursive: true, force: true })
})

/** The DSH bundled Python, falling back to whatever `python3`/`python` is on PATH. */
function findPython() {
  for (const candidate of ['python3', 'python']) {
    try {
      execFileSync(candidate, ['-c', 'import sys'], { stdio: 'pipe' })
      return candidate
    } catch { /* try the next one */ }
  }
  throw new Error('no python interpreter found; the plotting scripts need one')
}
