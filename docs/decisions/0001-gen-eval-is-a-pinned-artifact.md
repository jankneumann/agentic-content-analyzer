# ADR-0001: gen-eval is a pinned artifact, not a dependency and not an adjacent checkout

## Status

ACCEPTED — decided 2026-07-25 as part of roadmap item `ri-06`
(`openspec/changes/establish-cli-gen-eval-coverage/`). Supersedes an unlanded
sibling-checkout design from the same change.

## Date

2026-07-25

## Context

`ri-06` adds generator-evaluator coverage for the `aca` CLI. The gen-eval framework
lives in a sibling repository, `agentic-coding-tools`, at `packages/gen-eval`. The
question is how this repository reaches it.

The sibling `agentic-assistant` repository answered this twice. First with a
`[tool.uv.sources]` path dependency, which broke `uv lock` and `uv sync` on any
standalone clone and was removed under its ADR-0006. Then with a "thin runner": no
declared dependency, resolve the framework from `../agentic-coding-tools/...` at run
time, and skip advisorily when it is not there.

The first revision of `ri-06` copied that thin runner. That was wrong, and the reasoning
matters more than the conclusion.

Removing the `[tool.uv.sources]` entry removes the **resolver-visible** dependency. That
part is necessary — `uv lock` and `uv sync` must succeed for CI, Railway, and Docker
builds with no sibling repository present. But it does not remove the dependency. It
converts a *declared, versioned* dependency into an *undeclared, unversioned filesystem
adjacency*: not pinnable, not reproducible, invisible to tooling, and unsatisfiable in a
cloud harness, a sandbox, a VM, or a container.

The advisory-skip mode is the tell. It exists because the dependency cannot be reliably
satisfied. **A design that needs a skip mode to tolerate a missing dependency has an
unsolved dependency, not a managed one** — and the skip is where the failure hides.

The consequence is observable. `agentic-assistant`'s gate reports success against a
complete gen-eval checkout:

```
$ EVAL_GATE_REQUIRE=0 bash evaluation/run-gate.sh
eval-gate: SKIP — gen-eval at .../packages/gen-eval is not runnable (stub checkout?)
$ echo $?
0
```

Its probe invoked gen-eval's console script, which was broken upstream at the time —
`pyproject.toml` mapped `gen-eval` to `gen_eval.__main__:main`, but `main` was
`async def main(args)`, so the launcher raised `TypeError`. The crash was classified as an
absent checkout. It also passes `--scenario`, which is not a gen-eval argument. That gate
reported success without ever evaluating anything.

The console-script defect has since been fixed (this repository's `UPSTREAM.md` UP-1), and
that changes nothing about the design conclusion. A two-state gate returns to reporting
green on the next breakage. The state model is the fix; the bug was only the evidence.

## Decision

Split the problem by distribution requirement, because the two halves have opposite ones.

**1. The contract is repository-local.** The descriptor, scenario suites, report schema,
threshold policy, and validators live here and pin a gen-eval contract version
(`evaluation/contract/pin.json`). Schemas are vendored under
`openspec/contracts/cli-gen-eval/`. Nothing in this layer imports `gen_eval`; it validates
with `jsonschema` alone and always reaches a verdict.

Cross-repository consistency is a **contract** problem, not a runtime problem. Trying to
solve it by sharing a runtime is what kept producing a path dependency. Another repository
achieves consistency by pinning the same contract version, not by sharing a process.

**2. The runner is acquired as a pinned artifact.** Resolution precedence:

1. `ACA_GEN_EVAL_BIN` — explicit operator override.
2. The pinned artifact, executed from `evaluation/runner/` with
   `uv run --locked --exact`; its direct ref is drift-bound to `pin.json` and its full
   runtime and build dependency closure is committed in that isolated project's lock.
3. An adjacent checkout — developer convenience only, removed from the precedence list
   entirely under `ACA_GEN_EVAL_REQUIRE`.

The dedicated uv project is what makes this a tool rather than an application dependency:
the root `pyproject.toml` and `uv.lock` stay untouched, its dependencies cannot collide
with ours, and `--locked --exact` fails instead of resolving new transitive code in a
credential-bearing job.

**3. Three runner states, and `broken` is fatal everywhere.** `available` / `absent` /
`broken`. An exit code, crash, timeout, rejected argument, or contract-version mismatch is
`broken`. The only route to `absent` is that no candidate exists. Under
`ACA_GEN_EVAL_REQUIRE`, `absent` is also fatal and an unverifiable runner is refused.

## Alternatives rejected

**Package or path dependency.** Breaks standalone resolution; already demonstrated in
`agentic-assistant`.

**Vendoring gen-eval into this repository.** Duplicates an externally owned, actively
changing framework.

**A central shared evaluation service.** Cannot drive a CLI transport at all. gen-eval
spawns the command under test with `asyncio.create_subprocess_exec`, so the runner must be
co-located with the binary. A central service remains plausible for HTTP or MCP surfaces
and for result aggregation, but it can never own this one.

**A container image runner.** The mirror problem: gen-eval in a container cannot spawn the
host's `aca`. Containerizing both is a heavier, different gate than this item.

**A standalone compiled runner.** Attractive end-state, poor next step. gen-eval is Python
with optional `mcp`, `sdk`, and `db` extras, so bundling means a platform matrix and
dynamic-import fragility.

## Consequences

- `uv.lock` gains one optional extra (`gen-eval`, jsonschema-only) and no new package.
  `tests/cli_gen_eval/test_contract.py` asserts gen-eval appears in no dependency, extra,
  or source, and not in the lockfile.
- The contract layer enforces in CI whether or not a runner resolves, so a failed
  acquisition reduces coverage visibly instead of turning the gate green.
- Runner acquisition requires network and repository access. An environment without them
  gets `absent`, which is fatal under enforcement. That is correct and intentional.
- Pointing `runner_source` at an artifact index later — for example
  `artifactory.rotkohl.ai` — updates the pin and the dedicated runner project's direct
  requirement, then regenerates its lock; the gate and CI invocation stay unchanged.
- Pinned distribution makes the runner's published entry point load-bearing: there is no
  routing around a broken one, as there is with a source checkout. This surfaced the
  upstream console-script defect as a blocker (`UPSTREAM.md` UP-1, since fixed).
  `pin.json`'s `entry_point` remains the single declared location for the invocation form,
  so a future regression is one edit to work around and a `BROKEN` verdict in the
  meantime.

## References

- `openspec/changes/establish-cli-gen-eval-coverage/proposal.md` — D1, D2, D3
- `openspec/changes/establish-cli-gen-eval-coverage/UPSTREAM.md` — UP-1 through UP-4
- `agentic-assistant` ADR-0006 — cross-repo reuse policy, and the path-dependency removal
- `evaluation/README.md` — operational guide
