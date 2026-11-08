"""Agent 4 : matrice exigences et preuves, sans verdict juridique."""
from .common import analyze, code_payload
from ..models import Criterion
from ..models import AgentResult


def run(context, model, requirements):
    if context.issue is None:
        return AgentResult(agent=4, status="incomplete", summary="Conformité aux exigences non évaluée : issue indisponible.")
    payload = code_payload(context)
    payload["requirements"] = [x.model_dump() for x in requirements.criteria]
    result = analyze(model, 4,
        "Compare chaque critère au diff. Reprends exactement les identifiants et textes. "
        "L'issue fait autorité : signale les conflits avec la description de la PR sans les résoudre silencieusement. "
        "supported veut dire étayé par le code visible, pas validé en fonctionnement. "
        "not_met exige une contradiction explicite ; sinon unknown. Cite une preuve pour chaque conclusion.", payload)
    # Les critères perdus par le modèle redeviennent inconnus, ils ne disparaissent pas.
    by_id = {c.id: c for c in result.criteria}
    result.criteria = [Criterion(id=c.id, text=c.text,
        status=by_id[c.id].status if c.id in by_id and by_id[c.id].evidence.strip() else "unknown",
        evidence=by_id[c.id].evidence if c.id in by_id else "Critère non évalué par le modèle") for c in requirements.criteria]
    return result
