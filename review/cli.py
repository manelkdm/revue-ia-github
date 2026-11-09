"""Interface de démonstration, revue réelle, publication et export."""
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


def clients():
    return GitHub(os.getenv("GITHUB_API_URL", "https://api.github.com"), required("GITHUB_TOKEN"),
                  os.getenv("GITHUB_API_VERSION", "2026-03-10"))


def main():
    parser = argparse.ArgumentParser(description="Revue assistée par sept agents locaux")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Simulation sans services externes")
    demo.add_argument("--out", type=Path, default=Path("runs"))
    review = sub.add_parser("review", help="Lire une issue et une PR GitHub puis appeler Ollama")
    review.add_argument("--issue", type=int, required=True)
    review.add_argument("--repo", required=True)
    review.add_argument("--pr", type=int, required=True)
    review.add_argument("--evidence", type=Path)
    review.add_argument("--standards", type=Path)
    review.add_argument("--out", type=Path, default=Path("runs"))
    pub = sub.add_parser("publish", help="Publier explicitement un commentaire dans GitHub")
    pub.add_argument("report", type=Path, help="Chemin vers review.json")
    export = sub.add_parser("export", help="Exporter les indicateurs SQLite en CSV")
    export.add_argument("--runs", type=Path, default=Path("runs"))
    export.add_argument("--out", type=Path, default=Path("historique.csv"))
    args = parser.parse_args()
    try:
        if args.command == "demo":
            context = Context(issue_id=42, issue_subject="Division sûre", issue_description="CA-1 : le diviseur zéro déclenche ValueError.", issue_updated_at="2026-10-04T00:00:00Z", repository="demo/calculatrice", pr=1, head_sha="a" * 40, base_sha="b" * 40, pr_title="Gérer la division par zéro", diff="diff --git a/calculator.py b/calculator.py\n--- a/calculator.py\n+++ b/calculator.py\n@@ -1,2 +1,4 @@\n def divide(a, b):\n+    if b == 0:\n+        raise ValueError('division par zero')\n     return a / b\n", demo=True)
            report = run(context, DemoModel())
            print(save(report, args.out))
        elif args.command == "review":
            git = clients()
            evidence = read_evidence(args.evidence) if args.evidence else None
            standards = args.standards.read_text(encoding="utf-8") if args.standards else ""
            context = fetch_context(git, args.issue, args.repo, args.pr, standards, evidence)
            model = Ollama(required("OLLAMA_URL"), required("OLLAMA_MODEL"), int(os.environ.get("OLLAMA_TIMEOUT", "300")))
            report = run(context, model)
            print(save(report, args.out))
            if any(r.status == "incomplete" for r in report.results):
                print("Rapport enregistré mais au moins un agent a échoué.")
                return 2
        elif args.command == "publish":
            report = Review.model_validate_json(args.report.read_text())
            git = clients()
            publish(report, git, args.report.parent / "publication.json")
            print("Commentaire de synthèse publié dans GitHub.")
        else:
            export_csv(args.runs, args.out)
            print(args.out)
        return 0
    except Exception as exc:
        # Les réponses et jetons des services ne sont pas imprimés.
        from .security import redact
        print(f"Erreur {type(exc).__name__} : {redact(str(exc))[:500]}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
