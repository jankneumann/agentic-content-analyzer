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


def _renderer_table(name: str) -> set[str]:
    block = re.search(rf"declare -A {name}=\((.*?)\n\)", RENDERER.read_text(), re.DOTALL)
    assert block is not None, name
    return set(re.findall(r"\[([a-z_]+)\]=", block.group(1)))


def _seed_fields(group: str) -> set[str]:
    block = re.search(
        rf"^\s*{group}\) FIELDS=\((.*?)\)", SEED.read_text(), re.DOTALL | re.MULTILINE
    )
    assert block is not None, group
    return set(block.group(1).split())


def test_seed_field_list_matches_what_the_renderer_accepts() -> None:
    # Each seed group writes exactly the fields its renderer table accepts; the
    # renderer refuses any other field, so a drift here stops the stack.
    assert _seed_fields("providers") == _renderer_table("PROVIDER_ENV")
    assert len(_seed_fields("providers")) == FIELD_COUNT
    assert _seed_fields("ingestion") == _renderer_table("INGESTION_ENV")
    assert _seed_fields("alerts") == {"ntfy_url"}
    assert '[[ "$field" == ntfy_url ]]' in RENDERER.read_text()


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
