"""Contract & security tests for .github/workflows/phase-a-release.yml and ci.yml."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "phase-a-release.yml"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _extract_run_blocks(yaml_text: str) -> list[str]:
    """Extract all inline and multiline ``run:`` shell script bodies from a workflow file."""
    lines = yaml_text.splitlines()
    blocks: list[str] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        match = re.match(r"^(\s*(?:-\s+)?)run:\s*(.*)$", line)
        if match is None:
            idx += 1
            continue
        base_indent = len(line) - len(line.lstrip(" "))
        remainder = match.group(2).strip()
        if remainder in {"|", "|-", "|+", ">", ">-", ">+"}:
            body_lines: list[str] = []
            idx += 1
            while idx < len(lines):
                sub = lines[idx]
                if sub.strip() == "":
                    body_lines.append("")
                    idx += 1
                    continue
                sub_indent = len(sub) - len(sub.lstrip(" "))
                if sub_indent <= base_indent:
                    break
                body_lines.append(sub)
                idx += 1
            blocks.append("\n".join(body_lines))
        else:
            blocks.append(remainder)
            idx += 1
    return blocks


def test_phase_a_workflow_exists_and_uses_utf8_lf_hygiene() -> None:
    assert WORKFLOW_PATH.is_file(), ".github/workflows/phase-a-release.yml must exist"
    raw = WORKFLOW_PATH.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "Workflow must not have a UTF-8 BOM"
    assert b"\r\n" not in raw, "Workflow must use LF line endings only"
    assert b"\r" not in raw, "Workflow must not contain bare CR characters"
    raw.decode("utf-8")


def test_phase_a_workflow_triggers_permissions_and_ci_isolation() -> None:
    text = WORKFLOW_PATH.read_text("utf-8")

    # Required schedule & manual dispatch triggers
    assert 'cron: "0 6 * * 5"' in text
    assert "workflow_dispatch:" in text
    assert "force_run:" in text
    assert "type: boolean" in text
    assert "default: false" in text

    # T-02-13: Forbid PR triggers on write-scoped release workflow
    assert re.search(r"^\s*pull_request\s*:", text, re.MULTILINE) is None
    assert re.search(r"^\s*pull_request_target\s*:", text, re.MULTILINE) is None

    # Least-privilege write permissions strictly scoped to release workflow
    assert "permissions:" in text
    assert "contents: write" in text
    assert "pull-requests: write" in text

    # ci.yml remains strictly read-only
    ci_text = CI_WORKFLOW_PATH.read_text("utf-8")
    assert "contents: read" in ci_text
    assert "contents: write" not in ci_text
    assert "pull-requests: write" not in ci_text


def test_phase_a_workflow_pinned_actions_commands_and_persistent_pr() -> None:
    text = WORKFLOW_PATH.read_text("utf-8")

    required_fragments = (
        "runs-on: ubuntu-latest",
        "timeout-minutes: 20",
        "group: phase-a-release",
        "cancel-in-progress: false",
        "actions/checkout@v4",
        "astral-sh/setup-uv@v5",
        "actions/upload-artifact@v4",
        "uv sync --locked",
        "ets2v2 publish release",
        "ets2v2 validate workshop",
        "ets2v2 validate local",
        "release/phase-a-weekly",
        "github-actions[bot]",
        "gh pr list",
        "gh pr edit",
        "gh pr create",
        "GH_TOKEN: ${{ github.token }}",
        '[ -f "$f" ] && git add "$f"',
        "git push --force origin HEAD:release/phase-a-weekly",
    )
    for fragment in required_fragments:
        assert fragment in text, f"Missing required workflow fragment: {fragment!r}"

    # No third-party PR actions (T-02-SC)
    assert "peter-evans/create-pull-request" not in text
    assert "create-pull-request@" not in text

    # Dedicated bot branch push must not rely on bare --force-with-lease under shallow checkout
    assert "--force-with-lease" not in text


def test_phase_a_workflow_zero_steam_secrets() -> None:
    text = WORKFLOW_PATH.read_text("utf-8")
    forbidden_tokens = (
        "STEAM_USERNAME",
        "STEAM_PASSWORD",
        "STEAM_SHARED_SECRET",
        "steamcmd",
        "secrets.STEAM",
    )
    lower_text = text.lower()
    for token in forbidden_tokens:
        assert token not in text, f"Forbidden Steam credential reference found: {token!r}"
        assert token.lower() not in lower_text, (
            f"Forbidden Steam credential reference found (case-insensitive): {token!r}"
        )


def test_phase_a_workflow_injection_safety_and_job_level_force_run() -> None:
    text = WORKFLOW_PATH.read_text("utf-8")

    # Job-level FORCE_RUN env must live under jobs.release-phase-a before steps:
    job_pos = text.index("release-phase-a:")
    steps_pos = text.index("steps:", job_pos)
    job_header = text[job_pos:steps_pos]
    assert "env:" in job_header
    assert "FORCE_RUN: ${{ inputs.force_run }}" in job_header

    # Artifact upload step must observe both env.FORCE_RUN and steps.release.outputs.force_run
    assert "env.FORCE_RUN == 'true'" in text
    assert "steps.release.outputs.force_run == 'true'" in text
    assert "steps.release.outputs.any_changed == 'true'" in text

    # T-02-12: Zero GitHub Actions expression interpolation inside run: shell bodies
    run_blocks = _extract_run_blocks(text)
    assert len(run_blocks) >= 4
    for block in run_blocks:
        assert "${{ github.event.inputs." not in block
        assert "${{ inputs." not in block
        assert "${{" not in block, f"Unsafe GitHub Actions expression inside run: block:\n{block}"
