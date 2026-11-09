"""Rapport lisible et historique SQLite local."""
import csv
import sqlite3
from pathlib import Path
from .security import safe_markdown as safe


def markdown(review):
    lines = ["# Rapport de revue de code", "", f"Exécution : `{review.run_id}`", "",
        f"Dépôt : {safe(review.repository)} · PR {review.pr} · Issue {review.issue_id}", "",
        f"Commit analysé : `{review.head_sha}`", "",
        f"**Recommandation : {review.decision}**", "",
        "Une personne doit vérifier les preuves et prendre la décision finale. Aucune fusion automatique.", ""]
    if review.demo:
        lines += ["**DÉMONSTRATION SIMULÉE — aucun modèle ni outil d'analyse exécuté.**", ""]
    lines += ["## Motifs", ""] + ["- " + safe(r) for r in review.reasons] + [""]
    lines += ["## Contrôles déterministes", "", "| Outil | État | Nombre de constats |", "|---|---|---:|"]
    for name in ("ruff", "pytest", "bandit", "gitleaks"):
        tool = review.tools.get(name)
        lines.append(f"| {name} | {tool.status if tool else 'not_run'} | {tool.total_findings if tool else 'inconnu'} |")
    lines += ["", f"Couverture de lignes : {review.coverage_percent if review.coverage_percent is not None else 'inconnue'}", ""]
    for result in review.results:
        lines += [f"## Agent {result.agent}", "", f"État : {result.status}", "", safe(result.summary), ""]
        for f in result.findings:
            location = f"{f.file or 'emplacement non fourni'}:{f.line or '?'}"
            lines += [f"- **{f.severity} — {safe(f.title)}** ({f.source})", f"  Emplacement : {safe(location)}. Preuve : {safe(f.evidence)}", f"  Action : {safe(f.recommendation)}"]
        if result.criteria:
            lines += ["", "| Critère | État | Preuve |", "|---|---|---|"]
            for c in result.criteria:
                values = [safe(c.id + ' ' + c.text), c.status, safe(c.evidence)]
                lines.append("| " + " | ".join(x.replace("\n", " ") for x in values) + " |")
        lines += [""] + ["- Limite : " + safe(x) for x in result.limitations] + [""]
    return "\n".join(lines)


def save(review, root: Path):
    root.mkdir(parents=True, exist_ok=True)
    dest = root / review.run_id
    dest.mkdir(mode=0o700)
    (dest / "review.json").write_text(review.model_dump_json(indent=2), encoding="utf-8")
    (dest / "report.md").write_text(markdown(review), encoding="utf-8")
    with sqlite3.connect(root / "history.sqlite3") as db:
        db.execute("CREATE TABLE IF NOT EXISTS reviews (run_id TEXT PRIMARY KEY, created_at TEXT, repository TEXT, pr INTEGER, issue INTEGER, head_sha TEXT, decision TEXT, demo INTEGER)")
        db.execute("INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?)", (review.run_id, review.created_at, review.repository, review.pr, review.issue_id, review.head_sha, review.decision, int(review.demo)))
    return dest


def export_csv(root: Path, output: Path):
    database = root / "history.sqlite3"
    if not database.exists():
        raise ValueError("Aucun historique disponible. Lancez une revue d'abord.")
    with sqlite3.connect(database) as db, output.open("w", encoding="utf-8", newline="") as f:
        cursor = db.execute("SELECT * FROM reviews ORDER BY created_at DESC")
        writer = csv.writer(f)
        writer.writerow([c[0] for c in cursor.description])
        writer.writerows(cursor)


def publication_text(review):
    # Résumé borné : le rapport détaillé reste local, pas de faux lien public.
    marker = f"Revue-IA {review.run_id}"
    return "\n".join([f"## {marker}", "", f"Commit : `{review.head_sha}`", "",
        f"Recommandation : **{review.decision}**", "", "Validation humaine obligatoire.", ""]
        + ["- " + safe(x) for x in review.reasons[:20]]
        + ["", "Le rapport détaillé est disponible auprès de l'opérateur de la revue."])
