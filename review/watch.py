"""Surveillance facultative d'une seule association issue/PR, par interrogation API."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from .cli import clients
from .config import required
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
    p.add_argument("--issue", type=int, required=True)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", type=int, required=True)
    p.add_argument("--evidence", type=Path)
    p.add_argument("--standards", type=Path)
    p.add_argument("--interval", type=int, default=60)
    p.add_argument("--out", type=Path, default=Path("runs"))
    p.add_argument("--publish", action="store_true", help="Publier automatiquement la synthèse, sans approuver la PR")
    p.add_argument("--once", action="store_true")
    args = p.parse_args()
    if args.interval < 30:
        p.error("L'intervalle minimal est de 30 secondes")
    git = clients()
    model = Ollama(required("OLLAMA_URL"), required("OLLAMA_MODEL"), int(os.getenv("OLLAMA_TIMEOUT", "300")))
    args.out.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{args.repo}:{args.pr}:{args.issue}".encode()).hexdigest()[:16]
    state_path = args.out / f"watch-{key}.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    try:
        while True:
            try:
                standards = args.standards.read_text() if args.standards else ""
                ctx = fetch_context(git, args.issue, args.repo, args.pr, standards)
                if args.evidence and args.evidence.exists():
                    evidence = read_evidence(args.evidence)
                    if evidence.head_sha == ctx.head_sha:
                        ctx.evidence = evidence
                    else:
                        ctx.warnings.append("Les preuves locales portent sur un ancien commit et sont exclues.")
                digest = fingerprint(ctx, model.name)
                if state.get("digest") != digest:
                    report = run(ctx, model)
                    dest = save(report, args.out)
                    print(f"Rapport créé : {dest}", flush=True)
                    if all(r.status == "complete" for r in report.results):
                        # Enregistrer avant la publication pour ne pas multiplier les envois en cas de panne.
                        state = {"digest": digest, "run_id": report.run_id}
                        state_path.write_text(json.dumps(state), encoding="utf-8")
                        if args.publish:
                            publish(report, git, dest / "publication.json")
                    else:
                        print("Analyse incomplète ; une nouvelle tentative aura lieu au prochain cycle.", flush=True)
                        if args.once:
                            return 2
            except Exception as exc:
                print(f"Cycle interrompu : {redact(str(exc))[:300]}. Vérifier le rapport et le journal avant une publication manuelle.", flush=True)
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
