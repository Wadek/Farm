import subprocess
import shutil

CLAUDE_BIN = shutil.which("claude") or "/home/waka/.local/bin/claude"
TIMEOUT_SECONDS = 60


def ask(question: str) -> tuple[str, str]:
    """
    Fire a single scoped question to the Claude CLI.
    Returns (response_text, status) where status is 'completed' or 'failed'.
    Each call is fully isolated — no shared context between questions.
    """
    try:
        result = subprocess.run(
            [CLAUDE_BIN, "-p", question],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip(), "completed"
        return result.stderr.strip() or "no response", "failed"
    except subprocess.TimeoutExpired:
        return "timed out", "failed"
    except Exception as e:
        return str(e), "failed"
