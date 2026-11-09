"""The operator seed step for third-party provider keys on gx-10."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SEED = ROOT / "deploy/gx10/openbao/seed-providers-secret.sh"
RENDERER = ROOT / "deploy/gx10/openbao/render-secrets.sh"
FIELD_COUNT = 12


def _seed(
    tmp_path: Path, answers: list[str], *, status: str = "404", current: dict | None = None
) -> tuple[subprocess.CompletedProcess[str], list[tuple[str, dict]]]:
    token = tmp_path / "token"
    token.write_text("root")
    tools = tmp_path / "bin"
    tools.mkdir()
    log = tmp_path / "calls"
    # The read is the only call with -o: answer it with the fixture status and body.
    # Every write is recorded as its URL plus the JSON body curl reads from @file.
    (tools / "curl").write_text(
        "#!/usr/bin/env bash\n"
        'out=""; prev=""\n'
        'for a in "$@"; do\n'
        '  [[ "$prev" == -o ]] && out="$a"\n'
        '  case "$a" in @*) body="${a#@}";; http*) url="$a";; esac; prev="$a"\n'
        "done\n"
        'if [[ -n "$out" ]]; then printf %s "$FIXTURE_CURRENT" >"$out"; printf %s "$FIXTURE_STATUS"; exit 0; fi\n'
        f'printf "%s %s\\n" "$url" "$(jq -c . "$body")" >> {log}\n'
    )
    (tools / "curl").chmod(0o700)
    result = subprocess.run(
        [SEED],
        input="".join(f"{answer}\n" for answer in answers),
        env=os.environ
        | {
            "PATH": f"{tools}:{os.environ['PATH']}",
            "GX10_BAO_TOKEN_FILE": str(token),
            "GX10_BAO_ADDR": "http://openbao.test/v1",
            "FIXTURE_STATUS": status,
            "FIXTURE_CURRENT": json.dumps({"data": {"data": current or {}}}),
        },
        capture_output=True,
        text=True,
    )
    calls = []
    if log.exists():
        for line in log.read_text().splitlines():
            url, body = line.split(" ", 1)
            calls.append((url, json.loads(body)))
    return result, calls


def test_seed_field_list_matches_what_the_renderer_accepts() -> None:
    renderer_fields = set(re.findall(r"\[([a-z_]+_api_key)\]=", RENDERER.read_text()))
    seed_block = re.search(r"FIELDS=\((.*?)\)", SEED.read_text(), re.DOTALL)
    assert seed_block is not None
    assert set(seed_block.group(1).split()) == renderer_fields
    assert len(renderer_fields) == FIELD_COUNT


def test_first_seed_stores_typed_keys_and_reuploads_the_policy(tmp_path: Path) -> None:
    # gemini, anthropic, then blanks for the remaining fields.
    answers = ["GEMINI-SEKRET", "ANTHROPIC-SEKRET"] + [""] * (FIELD_COUNT - 2)
    result, calls = _seed(tmp_path, answers)

    assert result.returncode == 0, result.stderr
    secret_url, secret_body = calls[0]
    assert secret_url.endswith("/secret/data/newsletter/gx10/providers")
    assert secret_body == {
        "data": {"gemini_api_key": "GEMINI-SEKRET", "anthropic_api_key": "ANTHROPIC-SEKRET"}
    }
    policy_url, policy_body = calls[1]
    assert policy_url.endswith("/sys/policies/acl/aca-gx10")
    assert "gx10/providers" in policy_body["policy"]
    assert "SEKRET" not in result.stdout + result.stderr


def test_rotation_keeps_blank_answers_and_removes_dashes(tmp_path: Path) -> None:
    current = {"gemini_api_key": "old-gemini", "anthropic_api_key": "keep", "openai_api_key": "x"}
    answers = ["new-gemini", "", "-"] + [""] * (FIELD_COUNT - 3)
    result, calls = _seed(tmp_path, answers, status="200", current=current)

    assert result.returncode == 0, result.stderr
    assert calls[0][1]["data"] == {"gemini_api_key": "new-gemini", "anthropic_api_key": "keep"}


def test_a_failed_read_never_overwrites_the_stored_keys(tmp_path: Path) -> None:
    result, calls = _seed(tmp_path, ["new-gemini"] + [""] * (FIELD_COUNT - 1), status="503")

    assert result.returncode != 0
    assert "HTTP 503" in result.stderr
    assert calls == []


def test_refuses_to_store_a_state_without_any_llm_key(tmp_path: Path) -> None:
    answers = ["", "", "", "youtube-key"] + [""] * (FIELD_COUNT - 4)
    result, calls = _seed(tmp_path, answers)

    assert result.returncode != 0
    assert "without anthropic_api_key" in result.stderr
    assert calls == []
