"""Log + run-context retrieval through the Agentia CLI (or a local file for demos)."""
import subprocess
from .config import Config

class LogFetchError(RuntimeError):
    pass

def fetch_logs(cfg: Config, run_id: str, timeout: int = 60) -> str:
    cmd = [part.format(run_id=run_id) for part in cfg.log_command]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise LogFetchError(f"CLI not found: {cmd[0]!r}. Install the Agentia CLI or edit 'log_command'.")
    except subprocess.TimeoutExpired:
        raise LogFetchError(f"Timed out fetching logs for run {run_id}")
    text = (out.stdout or "") + (("\n" + out.stderr) if out.stderr else "")
    if out.returncode != 0 and not text.strip():
        raise LogFetchError(f"Log command failed (exit {out.returncode})")
    return text

def suggested_command(cfg: Config, category: str, ctx: dict) -> dict:
    """Commands come from vetted templates, never from free-form LLM output."""
    fill = {"run_id": ctx.get("run_id", "<run-id>"),
            "pipeline": ctx.get("pipeline", "<pipeline>"),
            "environment": ctx.get("environment", "<env>")}
    retry = cfg.commands.get(category, cfg.commands["other"]).format(**fill)
    rollback = cfg.commands["rollback"].format(**fill)
    return {"retry": retry, "rollback": rollback}
