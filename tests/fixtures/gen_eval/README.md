# gen-eval report fixtures

Real output from the pinned runner (`600744a55418`), captured by
`./evaluation/run-gate.sh` against this repository's checked-in suite. Not hand-authored:
the point of a fixture here is to prove the validator accepts what the runner *actually*
emits, and a hand-built report is only ever a restatement of what we already believe it
emits.

| File | Run | Scenarios |
|---|---|---|
| `report-full-pass.json` / `expectation-full-pass.json` | `run-gate.sh` with a backend on `localhost:8000` | 16, all pass |
| `report-offline-pass.json` / `expectation-offline-pass.json` | `run-gate.sh --offline` | 11, all pass |

Reports and expectations are paired. A report on its own cannot say whether it is
complete — completeness is a fact about what the run was *asked* to do — so
`tests/cli_gen_eval/test_report.py` always loads both.

**The only edit made to the captured reports** is that captured stdout bodies
(`verdicts[].steps[].actual.body.raw`) longer than 120 characters are truncated with a
`… [N chars trimmed for fixture]` marker. Those hold whole `aca --help` screens and
accounted for most of the original 167 KB. Nothing structural is touched, and
`test_the_recorded_reports_are_schema_valid` would fail if the truncation had corrupted
the documents. The remaining bulk is genuine structured payload — `aca capabilities`
alone is about 15 KB of JSON — and is left intact.

**One structural edit, recorded so it is not mistaken for capture.** The `aca backup`
command group (`add-gx10-backup-scheme`) was added to the help sweep after these
reports were captured, so `cli:backup` was inserted by hand into
`plumbing-help-batch-01`: one passing step, one credited interface, identical in
shape to the `cli:batch` entry beside it. It was added to the existing batch rather
than by reflowing the sweep alphabetically, precisely to keep this edit to the one
interface that changed instead of moving commands between scenarios.

Regenerate these fixtures at the next pin bump and this note can go. Until then,
treat `cli:backup`'s entries as derived rather than observed.

The negative cases are **not** checked in. Every one is derived in the test by mutating a
loaded fixture, so the mutation sits next to the assertion it is supposed to trip. A
checked-in `report-truncated.json` would state that eighteen scenarios went missing; a
`report["verdicts"] = report["verdicts"][:8]` in the test *demonstrates* it, and cannot
drift out of agreement with the fixture it was derived from.

## Regenerating

```bash
make dev-bg                                   # the discovery scenarios need a backend
./evaluation/run-gate.sh                      # writes evaluation/reports/
./evaluation/run-gate.sh --offline --output-dir /tmp/offline
```

Then copy `gen-eval-report.json` and `gen-eval-expectation.json` from each, applying the
truncation rule above. Expect the pass counts and interface lists to change whenever the
suite does — that is the fixture tracking reality, not rot.
