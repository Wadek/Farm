from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_verify_workflow_runs_pytest_on_pull_requests():
    text = (ROOT / ".github" / "workflows" / "verify.yml").read_text(encoding="utf-8")
    assert "pytest tests/" in text
    assert "pull_request" in text
    assert "python-version" in text


def test_pr_template_requires_frontier_and_forbids_agent_merge():
    text = (ROOT / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
    assert "frontier plan" in text
    assert "frontier apply" in text
    assert "Agents do not merge to `main`" in text
    assert "--no-verify" in text


def test_main_ruleset_blocks_direct_push_shape():
    text = (ROOT / ".github" / "rulesets" / "protect-main.json").read_text(encoding="utf-8")
    assert '"name": "Protect main"' in text
    assert "refs/heads/main" in text
    assert "pull_request" in text
    assert "non_fast_forward" in text
