import argparse, glob, os
from . import config
from .pipeline import triage
from .store import Store

def main():
    p = argparse.ArgumentParser(prog="triageiq", description="AI pipeline-failure triage with a local LLM")
    p.add_argument("--config")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="triage one failed run")
    a.add_argument("--run-id", default="local-run"); a.add_argument("--pipeline", default="unknown")
    a.add_argument("--environment", default=""); a.add_argument("--log-file", help="read logs from a file instead of the CLI")
    sub.add_parser("serve", help="start the webhook listener")
    sub.add_parser("history", help="show recent diagnoses")
    d = sub.add_parser("demo", help="run every sample log in samples/ through the real pipeline")
    d.add_argument("--dir", default=os.path.join(os.path.dirname(__file__), "..", "samples"))
    args = p.parse_args()
    cfg = config.load(args.config)

    if args.cmd == "analyze":
        text = open(args.log_file).read() if args.log_file else None
        triage(cfg, {"run_id": args.run_id, "pipeline": args.pipeline, "environment": args.environment}, text)
    elif args.cmd == "serve":
        from .server import serve; serve(cfg)
    elif args.cmd == "history":
        for row in Store(cfg.db_path).recent():
            print(" | ".join(str(x) for x in row))
    elif args.cmd == "demo":
        for i, f in enumerate(sorted(glob.glob(os.path.join(args.dir, "*.log"))), 1):
            print(f"\n=== {os.path.basename(f)} ===")
            triage(cfg, {"run_id": f"demo-{i:03d}", "pipeline": "payments-api", "environment": "UAT"}, open(f).read())

if __name__ == "__main__":
    main()
