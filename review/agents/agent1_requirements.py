"""Agent 1 : transforme la description de l'issue GitHub en critères traçables."""
from .common import analyze
from ..models import AgentResult


def run(context, model):
    if context.issue is None:
        return AgentResult(agent=1, status="incomplete", summary="Exigences indisponibles : aucune issue exploitable.",
                           limitations=["La revue du code et des tests continue sans exigences inventées."])
    result = analyze(model, 1,
        "Extrais les exigences explicites et les critères d'acceptation. Attribue CA-1, CA-2, etc. "
        "Chaque critère cite un passage exact de la description de l'issue dans evidence et reste unknown. "
        "N'invente pas de besoin. Signale les ambiguïtés et contraintes. "
        "Si l'issue ne contient pas de critère vérifiable, laisse criteria vide.",
        {"subject": context.issue.title, "description": context.issue.body})
    for criterion in result.criteria:
        criterion.status = "unknown"
    return result
