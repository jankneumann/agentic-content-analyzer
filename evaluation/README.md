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
make gen-eval              # contract, then the suite, then report validation
make gen-eval-report       # re-check a retained report; REPORT=… EXPECTATION=…
make gen-eval-mutating TARGET_POLICY=…    # the mutating dispatch — see below
./evaluation/run-gate.sh --resolve-only   # report runner state and stop
./evaluation/run-gate.sh --categories plumbing discovery
./evaluation/run-gate.sh --offline        # only the scenarios needing no backend
```

`make gen-eval` needs a backend running: about a quarter of the suite exercises the
canonical workflow surface, which is HTTP-only. `make dev-bg` first, or use `--offline`.

`make gen-eval` never runs the mutating categories, whatever is on disk. They are a
separate dispatch against a separate target — see "Mutating categories" below.

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
2. **The pinned artifact** — executed from the fully locked isolated project under
   `evaluation/runner/`. Its direct Git SHA must match
   `evaluation/contract/pin.json`; `uv run --locked --exact` refuses lock drift. This
   is what CI uses.
3. **An adjacent checkout** — `ACA_GEN_EVAL_PROJECT`, defaulting to
   `../agentic-coding-tools/packages/gen-eval`. **Developer convenience only.** It is
   removed from the precedence list entirely whenever `ACA_GEN_EVAL_REQUIRE` is set, so
   CI can never evaluate against an unpinned working tree.

gen-eval is not a dependency of the application project. It appears in no root
dependency, extra, source entry, or root `uv.lock`; its complete dependency graph lives
only in `evaluation/runner/uv.lock`. `tests/cli_gen_eval/` enforces both boundaries.

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
| 5 | the report is not credible, or the selection could not have produced a credible one |
| 6 | a mutating category was selected without a usable non-production target |

**These codes only survive `./evaluation/run-gate.sh`.** GNU make reports its own failure
code — 2 — for any failing recipe, so `make gen-eval-mutating` returns 2 whether the guard
refused, the target was unreachable, or a scenario failed. The Make targets are for
humans; anything that needs to tell 4, 5, and 6 apart must call the script directly. This
is the same reason report validation lives inside the gate rather than as a third Make
step.

## Is the report believable?

A pass rate is a statement about whatever ran. It says nothing about whether *what ran*
was what you asked for, and the pinned runner drops work without saying so. So the gate
validates the report before believing it, and keeps that verdict separate from the
threshold:

| Exit | Verdict | Who acts |
|---|---|---|
| 1 | credible, below threshold | whoever broke `aca` — a scenario genuinely failed |
| 5 | not credible | whoever owns the harness — nobody can tell whether `aca` broke |

Before the runner is invoked the gate writes `gen-eval-expectation.json` next to the
report: the scenario ids it selected, per-category counts, and the interfaces those
scenarios will credit. A report on its own cannot say whether it is complete, because
completeness is a fact about the *request*. The two are published together as evidence
for that reason, and `scripts/validate_gen_eval_report.py` takes both.

What gets checked, beyond schema conformance:

- **Every selected scenario ran, and nothing else did.** Set comparison, not a count, so
  a failure names which scenarios went missing rather than just how many.
- **Per-category counts match the selection** — a shortfall can hide inside a correct total.
- **Every interface the selection addresses appears in `per_interface`**, and none of them
  is listed as unevaluated.
- **No interface appears that the descriptor does not declare.** A mistyped `command`
  credits a phantom interface and leaves the real one uncovered, with no runner error.
- **The report agrees with itself** — counts sum to the total, verdicts match the total,
  `pass_rate` equals `passed/total`.
- **Numbers are in range**, which the published schema does not enforce (UP-5).

Demonstrated rather than asserted. Adding 25 low-priority scenarios pushes the suite past
the runner's tier-3 bucket:

```
gen-eval: PASS (100.0% >= 95.0%)
gen-eval gate: report: the selection held 36 scenarios but the report evaluated 16 —
  the runner drops work without a non-zero exit (UPSTREAM.md UP-6)
gen-eval gate: report: scenario 'plumbing-overflow-05' was selected but not run
  … 19 more
gen-eval gate: report REJECTED — 22 credibility findings
$ echo $?
5
```

That is the Phase 3 failure reproduced against the real runner: it reports 100% and exits
0, and the gate does not.

**Coverage is scoped to the selection, not to the descriptor.** The runner computes
`coverage_pct` against every declared interface, so a partial run legitimately reports
most of them unevaluated — measured, `--categories validation --offline` evaluates 2
scenarios, passes 100%, and leaves 29 of 31 unevaluated. A rule of "unevaluated must be
empty" would reject every category-scoped run, so the check is scoped to the interfaces
the selection actually addresses.

## Contract version and the pin

`evaluation/contract/pin.json` declares runner and contract provenance.
`evaluation/runner/pyproject.toml` repeats the direct runner requirement so uv can lock
its complete runtime and build closure; a drift test requires it to match the pin
exactly. `entry_point` in the pin is the **only** place that decides how the runner is
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

To bump the pin: edit `runner_ref` in `pin.json` and the matching direct requirement in
`evaluation/runner/pyproject.toml`, run
`uv lock --project evaluation/runner --python 3.12` and
`make gen-eval-contract-schemas`, then bump `contract_version` plus the changelog in
`openspec/contracts/cli-gen-eval/README.md` if any schema changed shape.

## Migrating to an artifact index

`runner_source` is a git URL as an interim measure. Pointing it at an index — for example
a future `artifactory.rotkohl.ai` — changes the pin plus the locked runner project's
direct requirement, but not the gate or CI design.

## Categories

| Category | Scenarios | Needs a backend | Mutating | Runs on PRs |
|---|---|---|---|---|
| `plumbing` | 9 | no | no | yes |
| `discovery` | 3 | yes | no | yes |
| `validation` | 4 | 2 of 4 | no | yes |
| `workflow-submission` | 8 | yes | **yes** | no — explicit dispatch only |
| `operation-control` | 2 | yes | **yes** | no — explicit dispatch only |

The read-only categories and the mutating ones are two dispatches, not one run with a
wider selection. They fit the runner's tier budget separately (16 and 10 scenarios) and
overflow it together by one, which the gate refuses up front rather than discovering
afterwards — see "Known limits". `tests/cli_gen_eval/test_selection.py` pins all three
numbers, so if `UPSTREAM.md` UP-6 lands and the combined run starts fitting, a test says
so.

## Mutating categories

`workflow-submission` and `operation-control` submit and control durable work. Everything
else here is a read: at worst it reports a wrong answer. These two write, and a write
against the wrong database is not undone by re-running the gate.

**Two independent mechanisms must both fail before anything is submitted.**

1. Selection defaults to the read-only categories, so a mutating scenario present on disk
   cannot execute unless its category is named explicitly.
2. The guard (`src/cli_gen_eval/mutation_guard.py`) then refuses that explicit naming
   unless a target policy is supplied *and* describes a non-production target that is the
   same target the CLI will dial.

Neither alone is sufficient. Selection filters files, so it says nothing about where the
surviving scenarios point; the guard describes a target, so it says nothing about what is
on disk.

```bash
make gen-eval-mutating TARGET_POLICY=~/secrets/aca-staging-policy.json
```

The policy is a `src/release_smoke/models.py::ProtectedTargetPolicy` document — the same
model release verification uses, loaded verbatim. The guard defines no target
classification of its own (proposal D6), so exactly one place in this repository decides
what production is. `evaluation/target-policy.example.json` is a working copy of the
shape; it carries no explanatory keys because the model forbids extra fields, and a
`_comment` would make it fail the moment you copied it.

What will refuse it, roughly in the order you will hit it:

| Refusal | Owned by |
|---|---|
| `target` is not `staging` or `ephemeral` | the guard |
| a non-local target that is not HTTPS — so **localhost can never be mutated** | the policy model |
| empty `production_target_ids` / `production_origins` | the policy model |
| `target_id` appears in `production_target_ids` | the policy model |
| an origin appears in `production_origins` | the policy model |
| `api_origin` is not the origin the CLI resolves from settings | the guard |

That last one is the check that makes the rest mean anything. A file saying "staging"
is a claim about a target the scenarios might not be pointed at; without comparing it to
the CLI's own resolved base URL, the policy is a sticky note — correct, adjacent to the
work, and attached to nothing.

A refusal exits 6, distinct from the argparse code 2. Both mean "the run did not start",
but only one of them means something asked to write to a target it was not allowed to
write to, and that is worth alerting on differently from a typo.

**Local runs are not possible, by construction.** The policy model requires HTTPS for
every non-local class, and `local` is not a mutable class — so these categories need a
deployed staging or ephemeral target. Verifying a change to them locally means invoking
the pinned runner directly against a materialized selection, outside the gate; that is
how the checked-in scenarios were verified, against a local backend with the embedded
queue worker both enabled and disabled.

## Selection is done by the gate, not the runner

The runner's `--categories` flag does nothing. `args.categories` reaches its config and is
never read again; the only path into its scenario filter is a feedback-driven focus list
that is empty on the first iteration, and iterations default to 1. Confirmed rather than
inferred — `--categories discovery` against this suite evaluates all sixteen scenarios.

That matters beyond tidiness. The mutating categories are held back by selection, so
trusting the flag would mean every `make gen-eval` submitted real durable work. So the
gate resolves the selection itself, copies the chosen
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
report. `scripts/validate_gen_eval_contract.py` therefore publishes `scenarios_expected`,
and the gate compares the expectation against the report's `total_scenarios` — see "Is
the report believable?" above.

**The published report schema has no numeric bounds**, so `pass_rate: 1.5` or a negative
scenario count are schema-valid. We vendor the published schema verbatim rather than
tightening our copy, so range sanity belongs to the report validator (`UPSTREAM.md` UP-5).

**A scenario's `interfaces:` field is inert to the runner.** Coverage is derived from
step commands alone, so the declaration is documentation — which is why
`tests/cli_gen_eval/test_report.py` holds it to the steps. Both drifts that test was
written to catch were already present: one scenario claimed `cli:operations` while
crediting nothing (its steps all spell the command as the root-level `--json` flag,
which credits no interface), and another declared nothing while crediting three.

**`{{ name }}` means two different things, and only one other field says which.** With a
`parameters` block the generator renders the template through Jinja2 at generation time
with `StrictUndefined`, and an undeclared name drops the expansion with a log warning.
Without one, `_expand_parameters` returns the template untouched and the same braces reach
the evaluator, which interpolates them from values earlier steps captured. So a template
cannot both parameterize and capture — generation consumes the braces before the evaluator
sees them. `src/cli_gen_eval/suite.py` checks both readings and the capture ordering, which
is what lets the operation-control scenarios chain steps at all.

**Whether the target drains its own queue is invisible to the gate.** `src/api/app.py`
starts an embedded worker when `worker_enabled` is set, and neither `/health` nor
`capabilities` reports it. A submitted operation therefore reaches a terminal state on its
own on one target and sits queued indefinitely on another, from identical steps. The
mutating scenarios are written to hold under both, which costs two things: the cancel step
asserts only that the command returned a parseable document (its exit code is 0 from a
queued operation and 1 from an already-failed one), and **`operations retry`'s success
path is not covered** — retry requeues from `failed` only, so the identical prior steps
yield 200 against a drained queue and 409 against an idle one. Retry's error contract is
covered unconditionally.

**Interface coverage is attempted, not passed.** `interfaces_tested` is derived from a
scenario's declared steps regardless of which ones ran, so a batch that fails early still
credits every interface it named. Coverage percentage answers "was this addressed", not
"does this work" — the pass rate answers the second question.

## CI

`.github/workflows/cli-gen-eval.yml` has two deliberately separate jobs:

- Pull requests cold-start Postgres plus the API, enforce the pinned runner, and
  execute only `plumbing`, `discovery`, and `validation`. The job has no model
  credentials or repository secrets.
- Manual dispatch runs `workflow-submission` and `operation-control` through the
  approval-protected `release-smoke-staging` environment. `TARGET_ID`,
  `FRONTEND_ORIGIN`, `API_ORIGIN`, both `EXPECTED_*_REVISION` values,
  `PRODUCTION_TARGET_IDS_JSON`, and `PRODUCTION_ORIGINS_JSON` are protected
  environment variables; `ADMIN_API_KEY` is the only environment secret. The job
  additionally refuses every ref except `main`, verifies the target's protected API
  revision without redirects before any subprocess, and runs the CLI with redirects
  disabled.

The environment protection is provisioned fail closed: administrator bypass is
disabled, self-review is prevented, and the only deployment branch policy is `main`.
Its target variables, admin secret, and independent reviewer activation are deliberately
not guessed by this change and remain tracked in
[issue #478](https://github.com/jankneumann/agentic-content-analyzer/issues/478);
the staging tier is non-operational until that checklist is complete.

Both jobs validate the repository-owned contract before acquiring the runner
from the checked-in pin. The gate writes the expectation before the run and
validates the report at the 95% threshold. A separate threshold-zero check
validates credibility for retention, so a credible failing report is still
uploaded for diagnosis while the original gate outcome remains failed. Raw step bodies,
captures, diffs, and free-form failure text are removed first; only the minimized JSON
report and its expectation are retained, for 14 days.

## Status

Phases 1–6 are complete: the contract layer, runner acquisition, read-only and
mutating suites, report validation, mutation guard, and CI wiring.
`make gen-eval` validates the contract,
resolves a runner and a target, evaluates 16 scenarios covering all 31 declared command
interfaces, and refuses to report success over a run it cannot show was complete.
`make gen-eval-mutating` evaluates 10 more against a declared non-production target,
covering all eight canonical operation types and the implemented operation-control
surface.
