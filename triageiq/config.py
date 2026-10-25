"""Configuration: JSON file (triageiq.json) overridden by environment variables."""
import json, os
from dataclasses import dataclass, field

DEFAULT_COMMANDS = {
    # Templates for the *suggested* next step. Adjust to your Agentia CLI syntax.
    # {run_id} / {pipeline} / {environment} are filled from the run context.
    "test_failure": "agentia cicd run retry --run {run_id}",
    "missing_permission": "agentia cicd run retry --run {run_id}   # after granting the missing permission",
    "missing_dependency": "agentia cicd run retry --run {run_id}   # after adding the missing dependency",
    "merge_conflict": "git fetch && git merge origin/main   # resolve conflicts, push, then retry",
    "other": "agentia cicd run retry --run {run_id}",
    "rollback": "agentia cicd run rollback --run {run_id}",
}

@dataclass
class Config:
    ollama_url: str = "http://localhost:11434"
    model: str = "qwen2.5:7b-instruct"
    llm_timeout: int = 120
    # Command used to fetch logs. {run_id} is substituted. Output = raw log text on stdout.
    log_command: list = field(default_factory=lambda: ["agentia", "cicd", "run", "logs", "--run", "{run_id}"])
    slack_webhook: str = ""
    teams_webhook: str = ""
    db_path: str = "triageiq.db"
    max_log_chars: int = 6000
    commands: dict = field(default_factory=lambda: dict(DEFAULT_COMMANDS))
    listen_host: str = "127.0.0.1"
    listen_port: int = 8080
    shared_secret: str = ""  # if set, webhook callers must send X-TriageIQ-Token

def load(path: str = None) -> Config:
    cfg = Config()
    path = path or os.environ.get("TRIAGEIQ_CONFIG", "triageiq.json")
    if os.path.exists(path):
        data = json.load(open(path))
        for k, v in data.items():
            if k == "commands":
                cfg.commands.update(v)
            elif hasattr(cfg, k):
                setattr(cfg, k, v)
    env = {
        "TRIAGEIQ_OLLAMA_URL": "ollama_url", "TRIAGEIQ_MODEL": "model",
        "TRIAGEIQ_SLACK_WEBHOOK": "slack_webhook", "TRIAGEIQ_TEAMS_WEBHOOK": "teams_webhook",
        "TRIAGEIQ_DB": "db_path", "TRIAGEIQ_SECRET": "shared_secret",
    }
    for e, attr in env.items():
        if os.environ.get(e):
            setattr(cfg, attr, os.environ[e])
    return cfg
