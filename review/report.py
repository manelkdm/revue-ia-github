"""Rapports français : une seule liste de constats regroupés, sans base de données."""
from pathlib import Path
from .findings import catalog, SEVERITY
from .security import safe_markdown as safe

STATUS = {
    "complete": "terminé", "incomplete": "incomplet", "passed": "réussi",
    "failed": "échec", "error": "erreur", "not_run": "non exécuté",
    "supported": "étayé", "not_met": "non satisfait", "unknown": "inconnu",
}
SEVERITY_LABELS = {"critical": "critique", "high": "élevée", "medium": "moyenne", "low": "faible", "info": "information"}
DECISIONS = {
    "corrections_recommandees": "Corrections recommandées",
    "revue_humaine_requise": "Revue humaine requise",
    "pret_pour_validation_humaine": "Prêt pour validation humaine",
}


def unique(values):
    seen = set()
    result = []
    for value in values:
        if value.strip() and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def finding_lines(group, entries):
    findings = [entries[reference] for reference in group]
    main = min(findings, key=lambda finding: SEVERITY[finding.severity])
    location = f"{main.file or 'emplacement non fourni'}:{main.line or '?'}"
    sources = unique(ref.rsplit("-", 1)[0].replace("agent-", "agent ").replace("outil-", "outil ") for ref in group)
    lines = [
        f"- **{safe(main.title)}** — gravité {SEVERITY_LABELS[main.severity]}",
        f"  Emplacement : {safe(location)}. Sources : {safe(', '.join(sources))}.",
    ]
    lines += ["  Preuve : " + safe(value) for value in unique(f.evidence for f in findings)]
    lines += ["  Action : " + safe(value) for value in unique(f.recommendation for f in findings)]
    return lines


def markdown(review, finding_limit=None):
    complete = all(result.status == "complete" for result in review.results)
    lines = [
        "# Revue de code", "", f"Dépôt : {safe(review.repository)} · PR #{review.pr}",
        f"Commit analysé : `{review.head_sha}`", "",
        f"**{DECISIONS[review.decision]}** — avis consultatif, validation humaine obligatoire.",
        f"Analyse IA : {'terminée' if complete else 'incomplète'}.", "",
    ]
    if review.demo:
        lines += ["**DÉMONSTRATION SIMULÉE — aucun modèle ni outil réel exécuté.**", ""]
    lines += ["## Synthèse", "", safe(review.results[-1].summary), ""]
    lines += ["## Contrôles", "", "| Outil | État | Constats |", "|---|---|---:|"]
    for name in ("ruff", "pytest", "bandit", "gitleaks"):
        tool = review.tools.get(name)
        lines.append(f"| {name} | {STATUS[tool.status] if tool else 'non exécuté'} | {tool.total_findings if tool else 'inconnu'} |")
    coverage = f"{review.coverage_percent:g} %" if review.coverage_percent is not None else "inconnue"
    lines += ["", f"Couverture de lignes : {coverage}.", "", "## Constats regroupés", ""]
    entries = catalog(review.results, review.tools)
    groups = review.finding_groups if finding_limit is None else review.finding_groups[:finding_limit]
    for group in groups:
        lines += finding_lines(group, entries) + [""]
    if not groups:
        lines += ["Aucun constat fourni ; cela ne garantit pas l'absence de problème.", ""]
    if len(groups) < len(review.finding_groups):
        lines += [f"{len(review.finding_groups) - len(groups)} autres constats dans le rapport complet.", ""]
    if finding_limit is None:
        lines += ["## Exigences", ""]
        for criterion in review.results[3].criteria:
            lines += [f"- {safe(criterion.id)} : {safe(criterion.text)} — {STATUS[criterion.status]}",
                      f"  Preuve : {safe(criterion.evidence)}"]
        if not review.results[3].criteria:
            lines.append("Aucun critère vérifiable disponible.")
        lines += ["", "## Agents", "", "| Agent | État |", "|---|---|"]
        lines += [f"| {result.agent} | {STATUS[result.status]} |" for result in review.results]
    limitations = list(review.warnings)
    limitations += [item for result in review.results for item in result.limitations]
    for name, tool in review.tools.items():
        if tool.details:
            limitations.append(f"{name} : {tool.details}")
        if tool.total_findings > len(tool.findings):
            limitations.append(f"{name} : {len(tool.findings)} constats détaillés sur {tool.total_findings}.")
    lines += ["", "## Limites", ""] + ["- " + safe(item) for item in unique(limitations)]
    if finding_limit is not None:
        lines += ["", "Le rapport JSON/Markdown complet est disponible auprès de l'opérateur."]
    return "\n".join(lines) + "\n"


def save(review, root: Path):
    dest = root / review.run_id
    dest.mkdir(parents=True, mode=0o700)
    (dest / "review.json").write_text(review.model_dump_json(indent=2), encoding="utf-8")
    (dest / "report.md").write_text(markdown(review), encoding="utf-8")
    return dest


def publication_text(review):
    # Publication manuelle provisoire ; mise à jour du même commentaire à l'étape 4.
    return markdown(review, finding_limit=5)
