"""Contract & security tests for .github/workflows/phase-a-release.yml and ci.yml."""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "phase-a-release.yml"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
OSM_AUDIT_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "osm-speed-audit.yml"


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
        "ets2-realism publish release",
        "ets2-realism validate workshop",
        "ets2-realism validate local",
        "release/phase-a-weekly",
        "github-actions[bot]",
        "gh pr list",
        "gh pr edit",
        "gh pr create",
        "GH_TOKEN: ${{ github.token }}",
        'if [ -f "$f" ]; then git add "$f"; fi',
        "(github.event_name == 'schedule' || github.ref == 'refs/heads/master')",
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


def _extract_embedded_python_snippets(run_blocks: list[str]) -> list[str]:
    """Extract embedded heredoc and ``python -c '...'`` snippets from workflow ``run:`` blocks."""
    snippets: list[str] = []
    heredoc_re = re.compile(
        r"python(?:3)?\s+-\s+<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*\n"
        r"(.*?)\n[ \t]*\1(?:\s|$)",
        re.DOTALL,
    )
    inline_c_re = re.compile(r"python(?:3)?\s+-c\s+'(.*?)'", re.DOTALL)
    for block in run_blocks:
        dedented = textwrap.dedent(block)
        for match in heredoc_re.finditer(dedented):
            snippets.append(textwrap.dedent(match.group(2)))
        for match in inline_c_re.finditer(dedented):
            snippets.append(textwrap.dedent(match.group(1)))
    return snippets


def test_phase_a_workflow_embedded_python_snippets_compile_cleanly() -> None:
    text = WORKFLOW_PATH.read_text("utf-8")
    run_blocks = _extract_run_blocks(text)
    snippets = _extract_embedded_python_snippets(run_blocks)
    assert len(snippets) >= 2, "Expected embedded Python snippets for outputs and PR alerts"
    for idx, snippet in enumerate(snippets):
        compile(snippet, f"phase-a-release.yml:snippet-{idx}", "exec")


def test_phase_a_workflow_d03_d05_d08_fetch_step_and_prices_lock_pr_staging() -> None:
    text = WORKFLOW_PATH.read_text("utf-8")

    # Online fetch step runs BEFORE offline publish release (D-05)
    fetch_cmd = (
        "ets2-realism fetch --lock-path state/prices.lock.json --json > dist/fetch_summary.json"
    )
    release_cmd = "ets2-realism publish release"
    assert fetch_cmd in text
    assert release_cmd in text
    assert text.index(fetch_cmd) < text.index(release_cmd)

    # Optional Tankerkönig secret passed strictly via step-level env: (D-03 / T-03-16)
    assert "TANKERKOENIG_API_KEY: ${{ secrets.TANKERKOENIG_API_KEY }}" in text
    assert "--prices-lock state/prices.lock.json" in text
    assert "dist/fetch_summary.json" in text

    # Persistent Release PR stages state/prices.lock.json alongside published ledger & changelogs
    assert (
        "for f in state/published.json state/prices.lock.json "
        "CHANGELOG_SUMMER.md CHANGELOG_WINTER.md; do" in text
    )
    assert "Circuit-Breaker & Staleness Alerts" in text
    # IN-03 + MD-05: Unconditional GITHUB_STEP_SUMMARY alert reporting & Markdown sanitization
    assert "GITHUB_STEP_SUMMARY" in text
    assert "def _sanitize(" in text
    assert text.count("def _sanitize(") >= 2
    assert 'replace("<", "&lt;")' in text

    # ci.yml remains read-only and never runs ets2-realism fetch or reads live API secrets
    ci_text = CI_WORKFLOW_PATH.read_text("utf-8")
    assert "ets2-realism fetch" not in ci_text
    assert "TANKERKOENIG_API_KEY" not in ci_text
    assert "uv run pytest" in ci_text


def test_phase_a_workflow_verifies_and_publishes_rolling_snapshots_latest_release() -> None:
    text = WORKFLOW_PATH.read_text("utf-8")

    # Verify v1 snapshots against SHA256SUMS.txt before upload/publish
    verify_summer = (
        "uv run --offline ets2-realism registry snapshot-verify "
        "dist/snapshots/realism-snapshot-summer.json "
        "--checksums dist/snapshots/SHA256SUMS.txt --expected-edition summer"
    )
    verify_winter = (
        "uv run --offline ets2-realism registry snapshot-verify "
        "dist/snapshots/realism-snapshot-winter.json "
        "--checksums dist/snapshots/SHA256SUMS.txt --expected-edition winter"
    )
    assert verify_summer in text
    assert verify_winter in text

    # Rolling public snapshots-latest GitHub Release publishing step (D-03, T-04-02, MD-06, LO-02)
    required_release_fragments = (
        'TAG="snapshots-latest"',
        "dist/snapshots/realism-snapshot-summer.json",
        "dist/snapshots/realism-snapshot-winter.json",
        "dist/snapshots/SHA256SUMS.txt",
        'gh api "repos/${GITHUB_REPOSITORY}/releases/tags/${TAG}" --silent',
        'elif grep -q "HTTP 404" "$API_ERR"; then',
        'gh release upload "$TAG" "${ASSETS[@]}" --clobber',
        'gh release create "$TAG" "${ASSETS[@]}"',
        "GH_TOKEN: ${{ github.token }}",
        "snapshots_changed={str(summary['snapshots_changed']).lower()}",
        "(steps.release.outputs.any_changed == 'true' "
        "|| steps.release.outputs.snapshots_changed == 'true' "
        "|| env.FORCE_RUN == 'true' "
        "|| steps.release.outputs.force_run == 'true') && "
        "(github.event_name == 'schedule' || github.ref == 'refs/heads/master')",
        "(steps.release.outputs.any_changed == 'true' "
        "|| steps.release.outputs.snapshots_changed == 'true') && "
        "(github.event_name == 'schedule' || github.ref == 'refs/heads/master')",
    )
    for fragment in required_release_fragments:
        assert fragment in text, f"Missing rolling snapshots-latest fragment: {fragment!r}"

    # LO-02: must NOT mask 401/403/5xx API errors via bare `if gh release view`
    assert 'if gh release view "$TAG"' not in text

    # Verify snapshot-verify runs BEFORE snapshots-latest GitHub Release upload
    assert text.index(verify_summer) < text.index('TAG="snapshots-latest"')
    assert text.index(verify_winter) < text.index('TAG="snapshots-latest"')


def test_phase_a_workflow_wires_optional_global_tier1_secrets_and_eu_vs_global_counters() -> None:
    text = WORKFLOW_PATH.read_text("utf-8")

    # Optional non-EU Tier 1 secrets passed strictly via step-level env: (D-01)
    assert "EIA_API_KEY: ${{ secrets.EIA_API_KEY }}" in text
    assert "OPINET_API_KEY: ${{ secrets.OPINET_API_KEY }}" in text
    assert "CNE_API_TOKEN: ${{ secrets.CNE_API_TOKEN }}" in text

    # Step summary reports separated EU Core Tier 1 vs Global Tier 1 counters (D-02)
    assert "eu_tier1_feeds_succeeded" in text
    assert "eu_tier1_feeds_failed" in text
    assert "global_tier1_feeds_succeeded" in text
    assert "global_tier1_feeds_failed" in text

    # ci.yml remains strictly free of global API secrets
    ci_text = CI_WORKFLOW_PATH.read_text("utf-8")
    assert "EIA_API_KEY" not in ci_text
    assert "OPINET_API_KEY" not in ci_text
    assert "CNE_API_TOKEN" not in ci_text


def test_phase_a_workflow_reports_tier2_counters_and_rolls_up_tier3_staleness() -> None:
    text = WORKFLOW_PATH.read_text("utf-8")
    assert "tier2_feeds_succeeded" in text
    assert "tier2_feeds_failed" in text
    assert text.count("stale_tier3_curated") >= 2
    assert text.count("extended_fx_alerts") >= 2
    assert text.count("EXTENDED_GLOBAL_CURRENCIES") >= 2
    assert text.count("def _sanitize(") >= 2

    # Compile every embedded Python snippet and confirm zero ${{ inside run: blocks
    run_blocks = _extract_run_blocks(text)
    for block in run_blocks:
        assert "${{" not in block
    snippets = _extract_embedded_python_snippets(run_blocks)
    assert len(snippets) >= 3
    for idx, snippet in enumerate(snippets):
        compile(snippet, f"phase-a-release.yml:tier2-snippet-{idx}", "exec")


def test_osm_speed_audit_workflow_exists_utf8_lf_and_zero_git_writes() -> None:
    """Verify .github/workflows/osm-speed-audit.yml hygiene, permissions, and zero Git writes."""
    assert OSM_AUDIT_WORKFLOW_PATH.is_file(), ".github/workflows/osm-speed-audit.yml must exist"
    raw = OSM_AUDIT_WORKFLOW_PATH.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "Workflow must not have a UTF-8 BOM"
    assert b"\r\n" not in raw, "Workflow must use LF line endings only"
    assert b"\r" not in raw, "Workflow must not contain bare CR characters"
    text = raw.decode("utf-8")

    # Monthly 1st-Monday 07:00 UTC schedule + manual workflow_dispatch (iso2, overpass)
    assert 'cron: "0 7 1-7 * 1"' in text
    assert "workflow_dispatch:" in text
    assert "iso2:" in text
    assert "overpass:" in text

    # Strictly forbid PR triggers on issue-writing workflow (T-05-15)
    assert re.search(r"^\s*pull_request\s*:", text, re.MULTILINE) is None
    assert re.search(r"^\s*pull_request_target\s*:", text, re.MULTILINE) is None

    # Least-privilege permissions: contents: read + issues: write (NEVER contents: write!)
    assert "permissions:" in text
    assert "contents: read" in text
    assert "issues: write" in text
    assert "contents: write" not in text

    # Physically zero Git write commands anywhere in the workflow (D-14)
    for forbidden_git_cmd in ("git add", "git commit", "git push"):
        assert forbidden_git_cmd not in text, (
            f"Forbidden Git write command {forbidden_git_cmd!r} in osm-speed-audit.yml"
        )


def test_osm_speed_audit_workflow_injection_safety_actions_and_rolling_issue() -> None:
    """Verify env-only inputs, zero ${{ in run:, pinned actions, artifacts, and rolling issue."""
    text = OSM_AUDIT_WORKFLOW_PATH.read_text("utf-8")

    required_fragments = (
        "runs-on: ubuntu-latest",
        "actions/checkout@v4",
        "astral-sh/setup-uv@v5",
        "actions/upload-artifact@v4",
        "uv sync --locked",
        "AUDIT_ISO2: ${{ inputs.iso2 }}",
        "AUDIT_OVERPASS: ${{ inputs.overpass }}",
        "GH_TOKEN: ${{ github.token }}",
        "ets2-realism audit osm-speeds",
        "dist/audit/osm_speed_drift_report.md",
        "dist/audit/osm_speed_drift_report.json",
        "dist/audit/osm_issue_body.md",
        "truncate_markdown_for_github_issue",
        "osm-speed-drift-report",
        "GITHUB_STEP_SUMMARY",
        "osm-audit",
        "gh issue list",
        "gh issue edit",
        "gh issue create",
        "gh issue close",
        "unacknowledged_drift_count",
        "def _sanitize(",
    )
    for fragment in required_fragments:
        assert fragment in text, f"Missing required osm-speed-audit.yml fragment: {fragment!r}"

    # Zero third-party GitHub Issue actions (T-05-SC)
    assert "actions/github-script" not in text
    assert "JasonEtco/create-an-issue" not in text

    # Zero GitHub Actions expression interpolation inside any run: block (T-05-15)
    run_blocks = _extract_run_blocks(text)
    assert len(run_blocks) >= 3
    for block in run_blocks:
        assert "${{" not in block, f"Unsafe GitHub Actions expression inside run: block:\n{block}"

    # Every embedded Python snippet compiles cleanly
    snippets = _extract_embedded_python_snippets(run_blocks)
    assert len(snippets) >= 1
    for idx, snippet in enumerate(snippets):
        compile(snippet, f"osm-speed-audit.yml:snippet-{idx}", "exec")
