"""Slack / Microsoft Teams incoming-webhook notifications."""
import json, urllib.request

LABELS = {"test_failure": "Test failure", "missing_permission": "Missing permission",
          "missing_dependency": "Missing dependency", "merge_conflict": "Merge conflict", "other": "Unclassified"}

def render_text(ctx, d, cmds, history) -> str:
    lines = [f"Pipeline failed: {ctx.get('pipeline','?')}" + (f" ({ctx['environment']})" if ctx.get("environment") else "")
             + (f" - run {ctx['run_id']}" if ctx.get("run_id") else ""),
             f"Cause: {LABELS[d.category]} (confidence {d.confidence:.0%})",
             f"Why: {d.reason}"]
    if d.evidence:
        lines.append(f"Evidence: {d.evidence}")
    lines.append(f"Retry:    {cmds['retry']}")
    lines.append(f"Rollback: {cmds['rollback']}")
    if history["seen_before"]:
        lines.append(f"Seen {history['seen_before']} time(s) before on this pipeline.")
    if d.confidence < 0.5:
        lines.append("Low confidence - please check the raw log.")
    return "\n".join(lines)

def _post(url: str, payload: dict):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status

def send_slack(url, ctx, d, cmds, history):
    text = render_text(ctx, d, cmds, history)
    head, *rest = text.split("\n")
    return _post(url, {"text": head, "blocks": [
        {"type": "header", "text": {"type": "plain_text", "text": f"Pipeline failed: {ctx.get('pipeline','?')}"[:150]}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "```" + "\n".join(rest) + "```"}}]})

def send_teams(url, ctx, d, cmds, history):
    text = render_text(ctx, d, cmds, history)
    card = {"type": "AdaptiveCard", "version": "1.4", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "body": [{"type": "TextBlock", "text": text.split("\n")[0], "weight": "Bolder", "size": "Medium", "wrap": True},
                     {"type": "TextBlock", "text": "\n\n".join(text.split("\n")[1:]), "wrap": True, "fontType": "Monospace"}]}
    return _post(url, {"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": card}]})

def notify(cfg, ctx, d, cmds, history) -> list:
    sent = []
    for name, url, fn in (("slack", cfg.slack_webhook, send_slack), ("teams", cfg.teams_webhook, send_teams)):
        if url:
            try:
                fn(url, ctx, d, cmds, history); sent.append(name)
            except Exception as e:
                print(f"[triageiq] {name} notification failed: {e}")
    return sent
