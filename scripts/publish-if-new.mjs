#!/usr/bin/env node
/**
 * Publish every workspace package whose exact version is not on the registry yet.
 *
 * A release tag names the repository, not a package: `packages/*` each carry
 * their own version, and one release usually moves only some of them. This
 * script is the publish step of `.github/workflows/publish.yml` — it reads the
 * workspace, publishes in dependency order, and treats an already published
 * `name@version` as done, so re-running a tag is safe.
 *
 * Authentication is the caller's: in CI that is npm trusted publishing over OIDC
 * (`id-token: write`), locally it is an `npm login`. The script never handles a
 * token, and it deliberately does not enable provenance — this repository is
 * private and npm cannot attest a private source repository, so
 * `NPM_CONFIG_PROVENANCE=true` would fail the publish.
 *
 * Usage:
 *   node scripts/publish-if-new.mjs [options]
 *
 * Options:
 *   --dry-run     Print the plan without publishing.
 *   --registry <url>  Registry to check and publish to (default: registry.npmjs.org).
 *   -h, --help    Print this help.
 *
 * @module dsh-fft-base/publish-if-new
 */
import { spawnSync } from 'node:child_process'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const repoRoot = resolve(fileURLToPath(new URL('..', import.meta.url)))
const PACKAGES_DIR = join(repoRoot, 'packages')
const DEFAULT_REGISTRY = 'https://registry.npmjs.org/'
const NPM = 'npm'

const HELP = `publish-if-new — publish the workspace packages that are not on npm yet

USAGE
  node scripts/publish-if-new.mjs [options]

OPTIONS
  --dry-run         Print the plan without publishing
  --registry <url>  Registry (default: ${DEFAULT_REGISTRY})
  -h, --help        Print this help

Publishes each packages/* member whose own version is absent from the registry,
in dependency order. An already published name@version is skipped, so the same
release tag can be published again.
`

/** Read `--flag value` style options. */
function parseArgs(argv) {
  const options = { dryRun: false, registry: DEFAULT_REGISTRY }
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    if (arg === '-h' || arg === '--help') return { help: true }
    if (arg === '--dry-run') {
      options.dryRun = true
      continue
    }
    if (arg === '--registry') {
      const value = argv[index + 1]
      if (value === undefined || value.startsWith('-')) throw new Error('--registry needs a value')
      options.registry = value
      index += 1
      continue
    }
    throw new Error(`unknown option ${arg} (try --help)`)
  }
  return options
}

/** Every workspace package, keyed by name. */
function readWorkspace() {
  const packages = new Map()
  for (const entry of readdirSync(PACKAGES_DIR, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue
    const manifestPath = join(PACKAGES_DIR, entry.name, 'package.json')
    if (!existsSync(manifestPath)) continue
    const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'))
    if (typeof manifest.name !== 'string' || typeof manifest.version !== 'string') {
      throw new Error(`${entry.name}/package.json needs a name and a version`)
    }
    if (manifest.private === true) continue
    packages.set(manifest.name, { dir: join(PACKAGES_DIR, entry.name), manifest })
  }
  return packages
}

/**
 * Order the packages so a dependency is published before its dependents.
 *
 * Only workspace edges matter: anything else is already on a registry. Cycles are
 * a hard error — a workspace that cannot be ordered cannot be published safely.
 *
 * @param {Map<string, {manifest: object}>} packages - Workspace members.
 * @returns {string[]} Package names in publish order.
 */
export function publishOrder(packages) {
  const order = []
  const state = new Map()
  const visit = (name, trail) => {
    const mark = state.get(name)
    if (mark === 'done') return
    if (mark === 'visiting') throw new Error(`dependency cycle: ${[...trail, name].join(' -> ')}`)
    state.set(name, 'visiting')
    const dependencies = Object.keys(packages.get(name).manifest.dependencies ?? {})
    for (const dependency of dependencies) {
      if (packages.has(dependency)) visit(dependency, [...trail, name])
    }
    state.set(name, 'done')
    order.push(name)
  }
  for (const name of packages.keys()) visit(name, [])
  return order
}

/** Run npm, returning trimmed stdout and the exit status. */
function npm(args) {
  const result = spawnSync(NPM, args, { cwd: repoRoot, encoding: 'utf8' })
  return { status: result.status ?? 1, stdout: (result.stdout ?? '').trim(), stderr: (result.stderr ?? '').trim() }
}

/** The version on the registry for one package, or undefined when absent. */
function publishedVersion(name, version, registry) {
  const view = npm(['view', `${name}@${version}`, 'version', '--registry', registry])
  return view.status === 0 && view.stdout !== '' ? view.stdout : undefined
}

/** Print the help text scraped from this file's header comment. */
function printHelp() {
  console.log(HELP.trimEnd())
}

function main() {
  const options = parseArgs(process.argv.slice(2))
  if (options.help === true) {
    printHelp()
    process.exit(0)
  }

  const packages = readWorkspace()
  const order = publishOrder(packages)
  let published = 0
  let skipped = 0

  for (const name of order) {
    const { dir, manifest } = packages.get(name)
    const { version } = manifest
    const existing = publishedVersion(name, version, options.registry)
    if (existing !== undefined) {
      console.log(`[npm] skip ${name}@${version} (already published)`)
      skipped += 1
      continue
    }
    if (options.dryRun) {
      console.log(`[npm] would publish ${name}@${version} from ${dir}`)
      continue
    }
    console.log(`[npm] publishing ${name}@${version}`)
    const result = spawnSync(
      NPM,
      ['publish', '--access', 'public', '--registry', options.registry],
      { cwd: dir, stdio: 'inherit' },
    )
    if ((result.status ?? 1) !== 0) {
      throw new Error(`npm publish ${name}@${version} failed with status ${result.status}`)
    }
    published += 1
  }

  if (options.dryRun) {
    console.log(`[npm] dry run: ${order.length} package(s) checked`)
    return
  }
  console.log(`[npm] done: ${published} published, ${skipped} skipped`)
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    main()
  } catch (error) {
    console.error(`publish-if-new: ${error instanceof Error ? error.message : String(error)}`)
    process.exit(1)
  }
}
