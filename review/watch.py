"""Optional local watcher for one GitHub PR; GitHub Actions needs no watcher."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from .cli import client
from .connectors import fetch_context
from .llm import Ollama
from .ci import read_evidence
from .orchestrator import run
from .report import save
from .publish import publish
from .security import redact


def fingerprint(context, model_name):
    return hashlib.sha256((model_name + context.model_dump_json()).encode()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--issue", type=int, help="Détectée depuis la description de la PR par défaut")
    p.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    p.add_argument("--pr", type=int, required=True)
    p.add_argument("--evidence", type=Path)
    p.add_argument("--standards", type=Path)
    p.add_argument("--interval", type=int, default=60)
    p.add_argument("--out", type=Path, default=Path("runs"))
    p.add_argument("--publish", action="store_true")
    p.add_argument("--once", action="store_true")
    args = p.parse_args()
    if args.interval < 30:
        p.error("L'intervalle minimal est de 30 secondes")
    if not args.repo:
        p.error("--repo est obligatoire hors GitHub Actions")
    git = client()
    model = Ollama(os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
                   os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b"),
                   int(os.getenv("OLLAMA_TIMEOUT", "480")))
    args.out.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{args.repo}:{args.pr}:{args.issue}".encode()).hexdigest()[:16]
    state_path = args.out / f"watch-{key}.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    try:
        while True:
            try:
                standards = args.standards.read_text(encoding="utf-8") if args.standards else ""
                ctx = fetch_context(git, args.repo, args.pr, args.issue, standards)
                if args.evidence and args.evidence.exists():
                    evidence = read_evidence(args.evidence)
                    if evidence.head_sha == ctx.head_sha:
                        ctx.evidence = evidence
                    else:
                        ctx.warnings.append("Les preuves portent sur un ancien commit et sont exclues.")
                digest = fingerprint(ctx, model.name)
                if state.get("digest") != digest:
                    report = run(ctx, model)
                    dest = save(report, args.out)
                    print(f"Rapport créé : {dest}", flush=True)
                    if all(r.status == "complete" for r in report.results):
                        state = {"digest": digest, "run_id": report.run_id}
                        state_path.write_text(json.dumps(state), encoding="utf-8")
                        if args.publish:
                            publish(report, git, dest / "publication.json")
                    else:
                        print("Analyse incomplète ; réessayer après correction.", flush=True)
                        if args.once:
                            return 2
            except Exception as exc:
                print(f"Cycle interrompu : {redact(str(exc))[:300]}", flush=True)
                if args.once:
                    return 2
            if args.once:
                return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Surveillance arrêtée.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
