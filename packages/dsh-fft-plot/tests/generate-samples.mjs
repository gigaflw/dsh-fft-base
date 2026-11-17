/**
 * Render every fixture into tests/tmp/samples so a reviewer can inspect the real
 * SVG output without running the whole test suite. PNG previews are intentionally
 * not generated here: rasterising needs a local browser, while SVG works anywhere.
 *
 * Usage: pnpm samples   (prints the produced file paths)
 *
 * @module @dsh-ft/dsh-fft-plot/tests/generate-samples
 */

import { execFileSync } from 'node:child_process'
import { mkdirSync, rmSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const SCRIPTS = join(ROOT, 'skills', 'dsh-fft-plot', 'scripts')
const FIXTURES = join(ROOT, 'tests', 'fixtures')
const OUT = join(ROOT, 'tests', 'tmp', 'samples')
const NAMES = ['line', 'line_timestamp', 'barh', 'table', 'heatmap', 'treemap',
  'waterfall', 'timeline', 'chain']

const python = (() => {
  for (const candidate of ['python3', 'python']) {
    try {
      execFileSync(candidate, ['-c', 'import sys'], { stdio: 'pipe' })
      return candidate
    } catch { /* try the next one */ }
  }
  throw new Error('no python interpreter found')
})()

rmSync(OUT, { recursive: true, force: true })
mkdirSync(OUT, { recursive: true })
for (const name of NAMES) {
  const stdout = execFileSync(python, [
    join(SCRIPTS, 'plot.py'),
    '--spec', join(FIXTURES, `${name}.json`),
    '--out-dir', OUT,
    '--slug', name,
  ], { encoding: 'utf8' })
  console.log(stdout.trim())
}
console.log(`\n${NAMES.length} samples in ${OUT}`)
