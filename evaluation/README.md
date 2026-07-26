# CLI gen-eval evaluation suite

Generator-evaluator coverage for the `aca` CLI. Two layers with deliberately different
distribution models:

| Layer | What it is | Where it comes from |
|---|---|---|
| **Contract** | descriptor, scenarios, schemas, validators, thresholds | this repository |
| **Runner** | the process that spawns `aca` and evaluates it | a pinned external artifact |

The contract layer never imports gen-eval and always reaches a verdict. The runner is
acquired, never depended on. See
`docs/decisions/0001-gen-eval-is-a-pinned-artifact.md` for why.

## Running it

```bash
make gen-eval-contract     # contract only — no runner needed, always conclusive
make gen-eval              # contract, then the suite (read-only categories)
./evaluation/run-gate.sh --resolve-only   # report runner state and stop
./evaluation/run-gate.sh --categories plumbing discovery
```

## Runner resolution

Precedence, highest first:

1. **`ACA_GEN_EVAL_BIN`** — explicit command line. Use when you have a checkout or build
   you want to test against.
2. **The pinned artifact** — installed by `uvx` from the ref in
   `evaluation/contract/pin.json`, into an isolated environment. This is what CI uses.
3. **An adjacent checkout** — `ACA_GEN_EVAL_PROJECT`, defaulting to
   `../agentic-coding-tools/packages/gen-eval`. **Developer convenience only.** It is
   removed from the precedence list entirely whenever `ACA_GEN_EVAL_REQUIRE` is set, so
   CI can never evaluate against an unpinned working tree.

gen-eval is not a dependency of this project. It appears in no `dependencies`, no extra,
and no `[tool.uv.sources]` entry, and `uv.lock` contains no `gen-eval` package.
`tests/cli_gen_eval/test_contract.py` enforces that.

## The three runner states

| State | Meaning | Local | `ACA_GEN_EVAL_REQUIRE=1` |
|---|---|---|---|
| `available` | resolved, probed, contract version accepted | run | run |
| `absent` | no candidate exists at all | advisory skip, exit 0 | **fail (3)** |
| `broken` | a candidate exists but does not work | **fail (3)** | **fail (3)** |

`broken` is fatal everywhere, and this is the most important rule in the suite.

The sibling `agentic-assistant` repository has an evaluation gate with only two states.
Its runnability probe invoked gen-eval's console script, which was broken upstream at the
time (`UPSTREAM.md` UP-1), so every run crashed, the crash was interpreted as "stub
checkout", and the gate exited 0. It reported success without ever evaluating anything.
A gate whose failure mode is indistinguishable from its absence mode is not a gate.

That the specific defect has since been fixed is not the lesson. The two-state design
means the *next* breakage — a renamed flag, a schema bump, a network failure — returns it
to reporting green. Three states is a property of the gate, not a workaround for one bug.

So: an exit code, a crash, a timeout, a rejected argument, or a contract-version mismatch
all mean `broken`. The *only* route to `absent` is that no candidate exists.

Verify it yourself — point the override at anything that fails:

```bash
$ ACA_GEN_EVAL_BIN=/bin/false ./evaluation/run-gate.sh --resolve-only
gen-eval gate: BROKEN — ACA_GEN_EVAL_BIN override is present but unusable —
  probe exited 1: <no output>
$ echo $?
3
```

Historically this was demonstrable against gen-eval's own console script, which was
broken upstream and crashed on every invocation. That defect is fixed
(`UPSTREAM.md` UP-1), which is why the pin now invokes the console script directly.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | contract valid, and the suite passed or the runner is absent locally |
| 1 | contract invalid, or the suite failed |
| 2 | usage error |
| 3 | runner broken, or absent under `ACA_GEN_EVAL_REQUIRE` |

## Contract version and the pin

`evaluation/contract/pin.json` is the single source for the runner artifact and the
contract version. `entry_point` there is the **only** place that decides how the runner is
invoked; it is `console-script` as of runner ref `600744a5`.

The vendored schemas under `openspec/contracts/cli-gen-eval/` are **verbatim copies** of
the schemas gen-eval publishes in `gen_eval.contracts`, plus provenance annotations. The
generator derives nothing and refuses to write when upstream's `CONTRACT_VERSION`
disagrees with the pin, so bumping `runner_ref` cannot silently swap the contract
underneath artifacts validated against the old one.

Before running the suite the gate performs a contract-version handshake against
`gen-eval --print-contract-version`. A runner reporting a version other than the pin is
`broken`:

```bash
gen-eval gate: BROKEN — runner reports contract version '1' but the pin is '2'
```

A runner that does not support the flag at all is `unverifiable` — tolerated locally,
refused under `ACA_GEN_EVAL_REQUIRE`, so CI never evaluates against a runner of unknown
provenance.

To bump the pin: edit `runner_ref` in `pin.json`, run `make gen-eval-contract-schemas`,
and bump `contract_version` plus the changelog in
`openspec/contracts/cli-gen-eval/README.md` if any schema changed shape.

## Migrating to an artifact index

`runner_source` is a git URL as an interim measure. Pointing it at an index — for example
a future `artifactory.rotkohl.ai` — is a change to `pin.json` alone. No code, no CI, no
redesign; the `uvx --from <requirement>` shape is identical either way.

## Categories

| Category | Mutating | Runs on PRs |
|---|---|---|
| `plumbing` | no | yes |
| `discovery` | no | yes |
| `validation` | no | yes |
| `workflow-submission` | **yes** | no — explicit dispatch only |
| `operation-control` | **yes** | no — explicit dispatch only |

Mutating categories submit or control durable work and require an explicit staging or
ephemeral target, reusing the release-smoke target policy. They are refused outright until
that guard lands (Phase 5).

## Known limits

The published report schema is generated from pydantic models that declare no numeric
bounds, so `pass_rate: 1.5` or a negative scenario count are schema-valid. We vendor the
published schema verbatim rather than tightening our copy, so range sanity belongs to the
report validator. Raised upstream as `UPSTREAM.md` UP-5.

## Status

Phases 1 and 2 are complete: the contract layer and runner acquisition. The descriptor is
still a skeleton with no scenarios — Phase 3 populates it — so `make gen-eval` currently
validates the contract, resolves a runner, and evaluates an empty suite.
