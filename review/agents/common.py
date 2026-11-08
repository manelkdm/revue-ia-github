from ..models import AgentResult


def analyze(model, number, instruction, payload):
    try:
        result = AgentResult.model_validate(model.analyze(number, instruction, payload).model_dump())
        if result.agent != number:
            raise ValueError("Numéro d'agent incorrect")
        for finding in result.findings:
            finding.source = "llm"
        if number != 7:
            result.duplicate_groups = []
        return result
    except Exception as exc:
        # Un échec reste visible ; pas de résultat favorable par défaut.
        return AgentResult(agent=number, status="incomplete", summary="Analyse non terminée.",
            limitations=[f"Échec {type(exc).__name__} ; vérifier le service et relancer."])


def code_payload(context):
    return {"diff": context.diff, "standards": context.standards,
            "pr_title": context.pr_title, "pr_body": context.pr_body,
            "issue": context.issue.model_dump() if context.issue else None,
            "head_sha": context.head_sha, "scope": context.warnings}


def note_tools(result, context, names):
    for name in names:
        tool = context.evidence.tools.get(name) if context.evidence else None
        if not tool or tool.status in ("not_run", "error"):
            result.limitations.append(f"{name} non exécuté ou en erreur.")
        # Les constats des outils restent dans Review.tools, indépendants du modèle.
    return result
