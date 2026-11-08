"""Agent 3 : lisibilité et résultats Ruff."""
from .common import analyze, code_payload, note_tools


def run(context, model):
    payload = code_payload(context)
    payload["ruff"] = context.evidence.tools["ruff"].model_dump() if context.evidence and "ruff" in context.evidence.tools else None
    result = analyze(model, 3,
        "Évalue lisibilité, duplication visible, responsabilités et maintenabilité. "
        "Explique l'impact concret des écarts. Le rapport Ruff peut être absent. "
        "Ne recopie pas les constats Ruff dans findings : ils figurent séparément dans le rapport.", payload)
    return note_tools(result, context, ["ruff"])
