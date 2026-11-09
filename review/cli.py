"""CLI: demo, GitHub Issue + PR review, publish and CSV export."""
import argparse
import os
from pathlib import Path

from .config import required
from .connectors import GitHub, fetch_context
from .llm import DemoModel, Ollama
from .models import Context, Review
from .orchestrator import run
from .report import save, export_csv
from .publish import publish
from .ci import read_evidence


def client():
    return GitHub(
        os.getenv("GITHUB_API_URL", "https://api.github.com"),
        required("GITHUB_TOKEN"),
        os.getenv("GITHUB_API_VERSION", "2026-03-10"),
    )


def main():
    parser = argparse.ArgumentParser(description="Revue de PR GitHub par sept agents IA")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Simulation sans services externes")
    demo.add_argument("--out", type=Path, default=Path("runs"))
    review = sub.add_parser("review", help="Lire la PR et son issue GitHub puis lancer sept agents")
    review.add_argument("--issue", type=int, help="Facultatif si la PR contient 'Closes #12'")
    review.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"), help="owner/repo ; automatique dans Actions")
    review.add_argument("--pr", type=int, required=True)
    review.add_argument("--evidence", type=Path)
    review.add_argument("--standards", type=Path)
    review.add_argument("--out", type=Path, default=Path("runs"))
    review.add_argument("--publish", action="store_true", help="Publier/actualiser la synthèse sur la PR")
    pub = sub.add_parser("publish", help="Publier un rapport déjà généré sur la PR")
    pub.add_argument("report", type=Path)
    export = sub.add_parser("export", help="Exporter les indicateurs SQLite en CSV")
    export.add_argument("--runs", type=Path, default=Path("runs"))
    export.add_argument("--out", type=Path, default=Path("historique.csv"))
    args = parser.parse_args()
    try:
        if args.command == "demo":
            context = Context(
                issue_id=42, issue_subject="Division sûre",
                issue_description="CA-1 : le diviseur zéro déclenche ValueError.",
                issue_updated_at="2026-10-04T00:00:00Z",
                repository="demo/calculatrice", pr=1,
                head_sha="a" * 40, base_sha="b" * 40, pr_title="Gérer la division par zéro",
                diff="diff --git a/calculator.py b/calculator.py\n--- a/calculator.py\n+++ b/calculator.py\n@@ -1,2 +1,4 @@\n def divide(a, b):\n+    if b == 0:\n+        raise ValueError('division par zero')\n     return a / b\n",
                demo=True,
            )
            print(save(run(context, DemoModel()), args.out))
        elif args.command == "review":
            if not args.repo:
                raise ValueError("--repo est obligatoire hors GitHub Actions")
            git = client()
            evidence = read_evidence(args.evidence) if args.evidence else None
            standards = args.standards.read_text(encoding="utf-8") if args.standards else ""
            context = fetch_context(git, args.repo, args.pr, args.issue, standards, evidence)
            model = Ollama(
                os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
                os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b"),
                int(os.getenv("OLLAMA_TIMEOUT", "480")),
            )
            report = run(context, model)
            dest = save(report, args.out)
            print(f"Rapport enregistré : {dest}", flush=True)
            if args.publish:
                publish(report, git, dest / "publication.json")
                print("Synthèse publiée dans la PR GitHub.", flush=True)
            if any(r.status == "incomplete" for r in report.results):
                print("Au moins un agent a échoué ; la revue est incomplète.")
                return 2
        elif args.command == "publish":
            report = Review.model_validate_json(args.report.read_text(encoding="utf-8"))
            publish(report, client(), args.report.parent / "publication.json")
            print("Synthèse publiée dans GitHub.")
        else:
            export_csv(args.runs, args.out)
            print(args.out)
        return 0
    except Exception as exc:
        from .security import redact
        print(f"Erreur {type(exc).__name__} : {redact(str(exc))[:500]}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
