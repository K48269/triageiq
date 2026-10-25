"""End-to-end flow: failure event -> logs -> LLM -> store -> chat."""
from . import agentia, classify, notify
from .redact import redact
from .store import Store

def triage(cfg, ctx: dict, log_text: str = None, quiet: bool = False) -> dict:
    if log_text is None:
        log_text = agentia.fetch_logs(cfg, ctx["run_id"])
    log_text = redact(log_text)
    diag = classify.classify(cfg, log_text, ctx)
    cmds = agentia.suggested_command(cfg, diag.category, ctx)
    history = Store(cfg.db_path).record(ctx, diag)
    message = notify.render_text(ctx, diag, cmds, history)
    sent = notify.notify(cfg, ctx, diag, cmds, history)
    if not quiet and not sent:
        print(message)
    return {"diagnosis": diag.to_dict(), "commands": cmds, "history": history, "notified": sent, "message": message}
