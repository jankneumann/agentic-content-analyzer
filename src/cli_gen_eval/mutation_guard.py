"""Refuse mutating evaluation categories unless a non-production target is declared.

The `workflow-submission` and `operation-control` categories submit and control durable
work. Everything else in this suite is a read: worst case it reports a wrong answer.
These two write, and a write against the wrong database is not recoverable by re-running
the gate.

**Two independent mechanisms must fail before durable work is submitted**, and that is
the point of this module existing separately from selection.

1. `src/cli_gen_eval/selection.py` resolves which scenarios run, and the default
   selection is the read-only categories. A mutating scenario present on disk cannot
   execute unless its category is named explicitly.
2. This guard then refuses that explicit naming unless a target policy is supplied and
   describes a non-production target that is *the same target the CLI will dial*.

Either one alone would be a single point of failure. Selection is a filter over files,
so it says nothing about where the surviving scenarios point; the guard is a statement
about the target, so it says nothing about what is on disk. The interesting failure —
mutating scenarios reaching production — has to get past both.

**Why no target classification is defined here.** `src/release_smoke/models.py` already
models exactly this problem for release verification: `TargetClass`, the
`production_target_ids` / `production_origins` deny registries, and the validators that
reject a "staging" policy whose identity or origin is a registered production one. A
second classification in this module would be a second opinion about what production is,
and the two would eventually disagree — at which point the safer answer is not
necessarily the one that wins. So `ProtectedTargetPolicy` is loaded verbatim and its
verdict is taken; the rules below add nothing about *what production is*, only about
*which classes may be mutated* and *whether the policy describes the live target*.

**Why the origin binding matters more than the class check.** A policy file saying
"staging" proves nothing on its own — it is a claim about a target the scenarios might
not be pointed at. The CLI resolves its own base URL from project settings
(`src/cli_gen_eval/target.py` reads the same source, for the same reason), so the guard
compares that resolved origin against the policy's `api_origin` and refuses a mismatch.
Without that comparison the policy is a sticky note: correct, adjacent to the work, and
attached to nothing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from src.release_smoke.models import ProtectedTargetPolicy, normalize_origin

from .contract import MUTATING_CATEGORIES

# Which target classes may be mutated. A subset of release-smoke's `TargetClass`, and
# deliberately the same subset `src/release_smoke/mutation.py::run_mutation` enforces —
# `local` is excluded there and excluded here. One consequence is worth stating plainly
# rather than discovering: `ProtectedTargetPolicy` requires HTTPS for every non-local
# class, so a loopback backend can never satisfy this guard. The mutating categories are
# for a deployed staging or ephemeral target, dispatched deliberately; they are not part
# of a local `make gen-eval`.
MUTABLE_TARGET_CLASSES: frozenset[str] = frozenset({"staging", "ephemeral"})

ENV_TARGET_POLICY = "ACA_GEN_EVAL_TARGET_POLICY"


@dataclass(frozen=True)
class GuardVerdict:
    """Whether durable work may be submitted, and every reason it may not.

    Reasons are plural on purpose. A policy pointed at the wrong target *and* classified
    `production` is two separate mistakes, and reporting only the first sends the
    operator back for a second round with the same file.
    """

    allowed: bool
    reasons: list[str] = field(default_factory=list)
    policy: ProtectedTargetPolicy | None = None
    guarded_categories: list[str] = field(default_factory=list)

    @property
    def refused(self) -> bool:
        return not self.allowed


def load_policy(path: Path) -> tuple[ProtectedTargetPolicy | None, list[str]]:
    """Load a target policy document. Returns (policy, errors); never raises.

    Validation is `ProtectedTargetPolicy`'s, unmodified. It is what rejects a
    non-production target carrying a registered production identity or origin, and a
    mutation-capable target with empty deny registries — the cases this guard is
    ultimately for.
    """
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, [f"target policy {path} could not be read ({exc.strerror or exc})"]
    except ValueError as exc:
        return None, [f"target policy {path} is not valid JSON ({exc})"]

    try:
        return ProtectedTargetPolicy.model_validate(document), []
    except ValidationError as exc:
        return None, [
            f"target policy {path} is invalid: "
            + "; ".join(
                f"{'.'.join(str(part) for part in error['loc']) or '<root>'}: {error['msg']}"
                for error in exc.errors()
            )
        ]


def evaluate(
    categories: list[str] | set[str],
    policy_path: Path | None,
    base_url: str | None,
) -> GuardVerdict:
    """Decide whether the selected categories may submit durable work.

    `base_url` is the target the CLI itself will dial, resolved from project settings by
    the caller. Passing `None` means it could not be resolved, which is a refusal rather
    than a pass: an unbound policy cannot be shown to describe the right target.
    """
    guarded = sorted(set(categories) & MUTATING_CATEGORIES)
    if not guarded:
        return GuardVerdict(allowed=True, reasons=["no mutating category is selected"])

    if policy_path is None:
        return GuardVerdict(
            allowed=False,
            guarded_categories=guarded,
            reasons=[
                f"mutating categories {guarded} require an explicitly declared "
                f"non-production target, and none was supplied — pass "
                f"--target-policy PATH or set {ENV_TARGET_POLICY}"
            ],
        )

    policy, errors = load_policy(policy_path)
    if policy is None:
        return GuardVerdict(allowed=False, reasons=errors, guarded_categories=guarded)

    reasons: list[str] = []
    if policy.target not in MUTABLE_TARGET_CLASSES:
        reasons.append(
            f"target {policy.target_id!r} is classified {policy.target!r}; mutating "
            f"categories require {sorted(MUTABLE_TARGET_CLASSES)}"
        )

    reasons.extend(_origin_reasons(policy, base_url))

    if reasons:
        return GuardVerdict(
            allowed=False, reasons=reasons, policy=policy, guarded_categories=guarded
        )
    return GuardVerdict(
        allowed=True,
        policy=policy,
        guarded_categories=guarded,
        reasons=[
            f"target {policy.target_id!r} is {policy.target} at {policy.api_origin}, "
            f"which is the origin the CLI resolves, and is absent from the "
            f"{len(policy.production_origins)}-entry production origin registry"
        ],
    )


def _origin_reasons(policy: ProtectedTargetPolicy, base_url: str | None) -> list[str]:
    """Bind the policy to the origin the scenarios will actually submit to."""
    if base_url is None:
        return [
            "the CLI's api_base_url could not be resolved, so the policy cannot be shown "
            "to describe the target the scenarios will submit to"
        ]
    try:
        actual = normalize_origin(base_url)
    except ValueError as exc:
        return [f"the CLI's api_base_url {base_url!r} is not a bare origin ({exc})"]

    reasons: list[str] = []
    if actual != policy.api_origin:
        reasons.append(
            f"the CLI will submit to {actual}, but the policy describes "
            f"{policy.api_origin} — the policy is not about this target"
        )
    # Redundant while ProtectedTargetPolicy's own validator holds, and kept anyway: this
    # is the deny registry applied to the *live* resolved value rather than to the
    # policy's declaration of it. If the model is ever loosened, this is the check that
    # still refuses.
    if actual in set(policy.production_origins):
        reasons.append(f"{actual} is a registered production origin")
    return reasons
