"""Agent 6 : analyse de sécurité, Bandit et Gitleaks."""
from .common import analyze, code_payload, note_tools


def run(context, model):
    payload = code_payload(context)
    payload["security_tools"] = {name: context.evidence.tools[name].model_dump() for name in ("bandit", "gitleaks") if context.evidence and name in context.evidence.tools}
    result = analyze(model, 6,
        "Cherche injections, absence de contrôle d'accès, validation d'entrée et exposition de secrets. "
        "Ne fournis que les emplacements de secrets, jamais leur valeur. "
        "Signale les limites du diff. Ne recopie pas Bandit/Gitleaks dans findings, ils figurent séparément dans le rapport. "
        "Une absence de constat ne prouve pas la sécurité de l'application.", payload)
    return note_tools(result, context, ["bandit", "gitleaks"])
