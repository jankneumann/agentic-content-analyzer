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
./evaluation/run-gate.sh --offline        # only the scenarios needing no backend
```

`make gen-eval` needs a backend running: about a quarter of the suite exercises the
canonical workflow surface, which is HTTP-only. `make dev-bg` first, or use `--offline`.

## What needs a backend, and what happens when there isn't one

`src/cli/workflow_commands.py` is "backed exclusively by the HTTP API" — there is no
`--direct` path for `capabilities`, `configured-sources`, or `operations list`, so they
exit 1 with "Workflow API unavailable" when nothing is listening.

The gate resolves a target with the same three states it uses for the runner, and the
same rule: a missing prerequisite is never reported as success.

| State | Meaning | Result |
|---|---|---|
| `reachable` | `/health` answered 2xx | run |
| `absent` | settings could not name a target at all | **fail (4)** |
| `unreachable` | target named but not answering, or answering non-2xx | **fail (4)** |

The URL comes from the same `api_base_url` the CLI reads, so the probe cannot pass while
the scenarios dial somewhere else. `/health` is probed rather than `aca capabilities`
deliberately: putting a command under test inside the gate's own precondition check would
classify a genuine `capabilities` bug as "unreachable" and refuse, instead of reporting
the failing scenario.

`--offline` runs only the scenarios tagged `no-target`, prints the coverage being given
up, and is refused under `ACA_GEN_EVAL_REQUIRE`. It is an explicit, named reduction — not
a skip, which is why it announces what it dropped.

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
| 1 | contract invalid, the suite failed, or the selection matched no scenarios |
| 2 | usage error, or a flag refused under `ACA_GEN_EVAL_REQUIRE` |
| 3 | runner broken, or absent under `ACA_GEN_EVAL_REQUIRE` |
| 4 | the backend target the selection needs is absent or unreachable |

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

| Category | Scenarios | Needs a backend | Mutating | Runs on PRs |
|---|---|---|---|---|
| `plumbing` | 9 | no | no | yes |
| `discovery` | 3 | yes | no | yes |
| `validation` | 4 | 2 of 4 | no | yes |
| `workflow-submission` | — | yes | **yes** | no — explicit dispatch only |
| `operation-control` | — | yes | **yes** | no — explicit dispatch only |

Mutating categories submit or control durable work and require an explicit staging or
ephemeral target, reusing the release-smoke target policy. They are refused outright until
that guard lands (Phase 5), and no such scenarios are checked in yet.

## Selection is done by the gate, not the runner

The runner's `--categories` flag does nothing. `args.categories` reaches its config and is
never read again; the only path into its scenario filter is a feedback-driven focus list
that is empty on the first iteration, and iterations default to 1. Confirmed rather than
inferred — `--categories discovery` against this suite evaluates all sixteen scenarios.

That matters beyond tidiness. The mutating categories are meant to be held back by
selection, so trusting the flag would mean every `make gen-eval` submitted real durable
work once Phase 5 lands. So the gate resolves the selection itself, copies the chosen
scenarios into `evaluation/reports/.selection/`, and hands the runner a descriptor
pointing there with the declared command list carried over intact. Reported upstream as
`UPSTREAM.md` UP-6.

## Known limits

**The runner evaluates at most 30 scenarios per invocation, and at most 13 of them may be
non-critical.** Its generator truncates to `max_scenarios_per_iteration` (50, not settable
from its CLI), and its orchestrator then splits that budget three ways: 40% reserved for
interfaces matching `--changed-features-ref`, 35% for `priority <= 1`, and the remainder
for everything else. The reserved share does not reflow when unused.

This is why `evaluation/scenarios/plumbing/group-help.yaml` groups four commands per
scenario instead of one. The first version used one scenario per command, and the run
reported `total_scenarios: 21` against an expected 39 with `PASS (100.0%)` and exit 0. The
cost of the workaround is real: a failing command masks the rest of its batch. The pinned
limits live in `evaluation/contract/pin.json` under `runner_limits`, the arithmetic is
modelled in `src/cli_gen_eval/suite.py`, and
`tests/cli_gen_eval/test_descriptor_drift.py` fails when the suite stops fitting.

**Dropped work is logged, not reported.** Unparseable YAML, a Jinja2 render error, and a
model-validation failure each produce a `logger.warning` and are absent from the JSON
report. `scripts/validate_gen_eval_contract.py` therefore publishes
`scenarios_expected`, which Phase 4 compares against the report's `total_scenarios`.

**The published report schema has no numeric bounds**, so `pass_rate: 1.5` or a negative
scenario count are schema-valid. We vendor the published schema verbatim rather than
tightening our copy, so range sanity belongs to the report validator (`UPSTREAM.md` UP-5).

**Interface coverage is attempted, not passed.** `interfaces_tested` is derived from a
scenario's declared steps regardless of which ones ran, so a batch that fails early still
credits every interface it named. Coverage percentage answers "was this addressed", not
"does this work" — the pass rate answers the second question.

## Status

Phases 1–3 are complete: the contract layer, runner acquisition, and the read-only suite.
`make gen-eval` validates the contract, resolves a runner and a target, and evaluates 16
scenarios covering all 31 declared command interfaces. Phase 4 adds report validation and
the vacuous-run check; Phase 5 the mutation guard; Phase 6 CI wiring.
