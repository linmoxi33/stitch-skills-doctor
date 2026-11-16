# stitch-skills-doctor

Audit an Agent Skills pack the way an agent actually uses it: every path and flag written in
`SKILL.md` must exist and be accepted by the scripts shipped next to it — and this tool *executes*
those scripts instead of trusting the prose. Why now: Agent Skills packs are shipped as prompt
payload plus helper scripts, and a stale `resources/...` path or a flag the script never parses
costs an agent a whole turn before it can fall back.

Upstream: https://github.com/google-labs-code/stitch-skills

## What the upstream is, and what it leaves unchecked

`google-labs-code/stitch-skills` (9.6k stars, Apache-2.0) is a library of 16 Agent Skills packaged
as three plugins (`stitch-design`, `stitch-build`, `stitch-utilities`), each skill being
`SKILL.md` + optional `scripts/`, `resources/`, `examples/`, `references/`.

Its own CI (`.github/workflows/validate-skills.yml`) validates exactly **two** skills, and only by
running `node scripts/validate.js examples/gold-standard-card.tsx` inside `react-components` and
`react-native`. Nothing checks that the paths and flags *documented in the other 14 skills* point
at files that exist and are accepted by the shipped scripts. That is the gap this tool fills:

- `remotion/SKILL.md` refers to `assets/screens/home.png` and `assets/screens/history.png`, and to
  `resources/composition-checklist.md` / `resources/screen-slide-template.tsx` (evidence:
  <https://github.com/google-labs-code/stitch-skills/blob/main/plugins/stitch-build/skills/remotion/SKILL.md>).
- `generate-design/SKILL.md` refers to `examples/metadata.json`, which exists only inside the
  *sibling* skill `manage-design-system` (evidence:
  <https://github.com/google-labs-code/stitch-skills/blob/main/plugins/stitch-design/skills/generate-design/SKILL.md>).
- `manage-design-system/SKILL.md` documents `python3 stitch-skills/plugins/.../upload_to_stitch.py`,
  a path that only resolves when the current directory is the parent of a checkout literally named
  `stitch-skills` (evidence:
  <https://github.com/google-labs-code/stitch-skills/blob/main/plugins/stitch-design/skills/manage-design-system/SKILL.md>).

## What this tool does / does not do

Does: walk a pack, find every `SKILL.md`, extract documented artifact paths and the fenced blocks
that invoke local scripts, then

1. resolve every documented `scripts|resources|references|examples|assets/...` path against the
   skill directory (and report where it *does* exist, if anywhere else in the pack);
2. flag repository-relative paths that depend on the checkout's directory name;
3. flag scripts that ship but are never referenced (directly or through a documented `npm run`);
4. **execute** real syntax checks with the file's own interpreter — `python3 -m py_compile`,
   `node --check`, `bash -n` — in a scrubbed temporary HOME with no network;
5. **execute** `python3 <script> --help` and read the accepted long options from the real output,
   then compare them with the flags in the documented invocation of that same script;
6. import-probe Python dependencies and scan JS/TS imports, reporting third-party modules the skill
   documentation never names.

Does not: run the *functional* commands (they need the Stitch MCP server, a browser, or npm
packages), execute TypeScript, resolve `$ref`-style indirection, or judge whether a skill's prompt
is any good.

## Install / usage

Requires Python 3.8+. No dependencies, no network, no build step.

```bash
git clone <this-repo> && cd stitch-skills-doctor

# human-readable report (exit 1 because the upstream pack has errors)
python3 bin/stitch-skills-doctor --pack /path/to/stitch-skills

# machine-readable
python3 bin/stitch-skills-doctor --pack /path/to/stitch-skills --json

# reproduce the committed example outputs
python3 bin/stitch-skills-doctor --pack examples/in/broken-pack --json
python3 bin/stitch-skills-doctor --pack examples/in/clean-pack
```

Flags: `--pack DIR` (required), `--json`, `--fail-on error|warning|never` (default `error`),
`--no-exec` (skip all executable probes), `--version`.

### `--json` shape

```json
{
  "tool": "stitch-skills-doctor",
  "version": "1.0.0",
  "pack": "/path/to/stitch-skills",
  "summary": {
    "skills": 16, "scripts": 10, "findings": 10,
    "by_severity": {"error": 4, "warning": 6, "info": 0},
    "by_rule": {"DOC_PATH_CLONE_DEPENDENT": 1, "DOC_PATH_MISSING": 3,
                "SCRIPT_ORPHAN": 1, "SCRIPT_UNDECLARED_DEP": 5},
    "executed_probes": 10
  },
  "findings": [
    {"rule": "DOC_PATH_MISSING", "severity": "error", "skill": "plugins/.../remotion",
     "path": "assets/screens/home.png", "message": "...", "witness": "..."}
  ],
  "deterministic_sha256": "85901b367444d13b772314f9951768831107fbf887a04f6e4c636b6f12d94f0e",
  "verdict": "fail"
}
```

### Exit codes

| code | meaning |
| --- | --- |
| 0 | no finding at or above `--fail-on` |
| 1 | findings at or above `--fail-on` (default: any `error`) |
| 2 | usage error, missing directory, or no `SKILL.md` under `--pack` |

## Measured on the real upstream (not estimated)

Command: `python3 bin/stitch-skills-doctor --pack <checkout of google-labs-code/stitch-skills> --json`

| metric | value |
| --- | --- |
| skills found | 16 |
| scripts found | 10 |
| executed probes (syntax + `--help` + imports) | 10 |
| findings | **10** (4 error, 6 warning) |
| wall clock | 0.526 s |
| report sha256 | `85901b367444d13b772314f9951768831107fbf887a04f6e4c636b6f12d94f0e` |

The four errors are the two missing `remotion` screenshot paths, the `generate-design` →
`manage-design-system` `examples/metadata.json` drift, and the clone-directory-dependent
`upload_to_stitch.py` command. The six warnings are one orphan script (`remotion`) and five
undocumented third-party imports (`@swc/core`, `@babel/{generator,parser,traverse,types}`).
Full outputs: `examples/out/upstream-stitch-skills.report.{json,txt}`.

## 与同类项目的差异

Searched before building (`gh search repos`): `agent skills linter`, `skill.md validator`,
`SKILL.md checker`, `agent skills doctor`. The largest hit was 15 stars (`rajesh-gsn/skill-lint`);
no project above 500 stars covers this. Those tools validate frontmatter and description style.
This one differs in method, not in scope: it **executes the pack's own scripts** (`py_compile`,
`node --check`, `bash -n`, `--help`, import probes) and cross-checks the documented invocation
against the flags the script actually parses, which is where the real breakage is.

## 本轮创新

Upstream's CI proves two skills work by running them; this tool turns the *other fourteen* skills'
documented contract into an executable verdict — real interpreter runs plus `--help`-derived
accepted-flag sets, attributed per invocation block, so "documented `--mode` that `report.py`
never parses" is a machine-decidable finding rather than a style opinion. No trend audit in this
cluster has previously derived a contract by executing the artifact rather than parsing it.

## Limits

- Path and flag extraction is regex-based over fenced blocks; a path written in prose tables is
  still caught, but a path assembled at runtime by a script is not.
- Only Python scripts get a real `--help` probe; JS/TS/Shell accepted flags come from a source scan,
  so a flag built by string concatenation can be missed.
- TypeScript scripts are never executed (they would need a bundler/runtime).
- `SCRIPT_UNDECLARED_DEP` only says the docs never name the module — it does not claim the module is
  unnecessary.
- The committed upstream finding list is tied to the `main` snapshot audited on 2026-11-16; re-run
  the command after the upstream changes.

## License

MIT for this tool. Upstream `stitch-skills` is Apache-2.0 and is only read, never vendored.
