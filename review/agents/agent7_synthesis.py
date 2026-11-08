"""Agent 7 : résumé rédactionnel et recommandation déterministe séparée."""
from .common import analyze
from ..findings import catalog


def run(context, model, results):
    tools = context.evidence.tools if context.evidence else {}
    result = analyze(model, 7,
        "Synthétise les six analyses en français en deux phrases brèves, sans répéter la liste des constats. "
        "Dans duplicate_groups, regroupe les identifiants des constats qui décrivent le même problème "
        "au même fichier et à la même ligne. Des formulations différentes peuvent désigner le même problème. "
        "Ne regroupe pas des problèmes distincts ou des emplacements inconnus. En cas de doute, laisse séparé. "
        "Les constats non regroupés seront conservés automatiquement ; ne réécris pas leurs preuves. "
        "Ne crée pas de nouveaux constats ; laisse findings et criteria vides. "
        "Ne déclare jamais une fusion approuvée. Le programme calculera la recommandation.",
        {"agents": [r.model_dump() for r in results], "warnings": context.warnings,
         "findings": {key: value.model_dump() for key, value in catalog(results, tools).items()}})
    result.findings = []
    result.criteria = []
    return result


def recommendation(context, results):
    corrections, missing = [], []
    if context.demo:
        missing.append("Démonstration simulée : aucune revue réelle.")
    for result in results:
        if result.status != "complete":
            missing.append(f"Agent {result.agent} incomplet.")
        if any(f.severity in ("high", "critical") for f in result.findings):
            corrections.append(f"Constat majeur de l'agent {result.agent} à vérifier et corriger.")
    compliance = next((r for r in results if r.agent == 4), None)
    if not compliance or not compliance.criteria or any(c.status == "unknown" for c in compliance.criteria):
        missing.append("Critères d'acceptation absents ou partiellement inconnus.")
    if compliance and any(c.status == "not_met" for c in compliance.criteria):
        corrections.append("Au moins un critère paraît non satisfait.")
    evidence = context.evidence
    for name in ("ruff", "pytest", "bandit", "gitleaks"):
        tool = evidence.tools.get(name) if evidence else None
        if not tool or tool.status in ("error", "not_run"):
            missing.append(f"Preuve {name} absente ou inexploitable.")
        elif tool.status == "failed" or tool.total_findings > 0 or tool.findings:
            corrections.append(f"Contrôle {name} avec écarts.")
    if not evidence or evidence.coverage_percent is None:
        missing.append("Couverture inconnue.")
    if not evidence or evidence.tests_run - evidence.tests_skipped <= 0:
        missing.append("Aucun test effectivement exécuté.")
    if evidence and evidence.tests_failed:
        corrections.append("Des tests ont échoué.")
    if context.warnings:
        missing.extend(context.warnings)
    if corrections:
        return "corrections_recommandees", corrections + missing
    if missing:
        return "revue_humaine_requise", missing
    return "pret_pour_validation_humaine", ["Contrôles disponibles satisfaits ; approbation humaine obligatoire."]
