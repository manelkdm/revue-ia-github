"""Démonstration, revue locale et publication manuelle sur GitHub."""
import argparse
import os
from pathlib import Path
from .config import load_env, required
from .connectors import GitHub, fetch_context
from .llm import DemoModel, Ollama
from .models import Context, Issue, Review
from .orchestrator import run
from .report import save
from .publish import publish
from .ci import read_evidence


def github_client():
    return GitHub(os.getenv("GITHUB_API_URL", "https://api.github.com"), required("GITHUB_TOKEN"),
                  os.getenv("GITHUB_API_VERSION", "2026-03-10"))


def demo_context():
    return Context(
        repository="demo/calculator", pr=1, head_sha="a" * 40, base_sha="b" * 40,
        pr_title="Gérer la division par zéro", pr_body="Issue liée : #42",
        issue=Issue(number=42, title="Division sûre", body="CA-1 : le diviseur zéro déclenche ValueError."),
        diff="diff --git a/calculator.py b/calculator.py\n--- a/calculator.py\n+++ b/calculator.py\n"
             "@@ -1,2 +1,4 @@\n def divide(a, b):\n+    if b == 0:\n"
             "+        raise ValueError('division par zero')\n     return a / b\n",
        demo=True,
    )


def main():
    parser = argparse.ArgumentParser(description="Revue consultative avec sept agents locaux")
    parser.add_argument("--env", type=Path, default=Path(".env"))
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Simulation sans services externes")
    demo.add_argument("--out", type=Path, default=Path("runs"))
    review = sub.add_parser("review", help="Lire une PR GitHub et analyser son diff avec Ollama")
    review.add_argument("--repo", required=True)
    review.add_argument("--pr", type=int, required=True)
    review.add_argument("--evidence", type=Path)
    review.add_argument("--standards", type=Path)
    review.add_argument("--out", type=Path, default=Path("runs"))
    pub = sub.add_parser("publish", help="Ajouter manuellement un commentaire de synthèse GitHub")
    pub.add_argument("report", type=Path, help="Chemin vers un review.json au format 3")
    args = parser.parse_args()
    try:
        # La démonstration ne nécessite ni jeton ni configuration locale.
        if args.command == "demo":
            report = run(demo_context(), DemoModel())
            print(save(report, args.out))
        else:
            load_env(args.env)
            git = github_client()
            if args.command == "review":
                evidence = read_evidence(args.evidence) if args.evidence else None
                standards = args.standards.read_text(encoding="utf-8") if args.standards else ""
                context = fetch_context(git, args.repo, args.pr, standards, evidence)
                model = Ollama(os.getenv("OLLAMA_URL", "http://localhost:11434"),
                               os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b"),
                               int(os.getenv("OLLAMA_TIMEOUT", "300")))
                report = run(context, model)
                print(save(report, args.out))
                if any(result.status == "incomplete" for result in report.results):
                    print("Rapport enregistré ; au moins un agent est incomplet.")
                    return 2
            else:
                report = Review.model_validate_json(args.report.read_text(encoding="utf-8"))
                publish(report, git, args.report.parent / "publication.json")
                print("Synthèse publiée sur GitHub.")
        return 0
    except Exception as exc:
        from .security import redact
        print(f"Erreur {type(exc).__name__} : {redact(str(exc))[:500]}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
