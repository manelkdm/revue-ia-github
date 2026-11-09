"""Ordre explicite : exigences, analyses, conformité, tests, sécurité, synthèse."""
import hashlib
from datetime import datetime, timezone
from uuid import uuid4
from .models import Context, Review, AgentResult
from .security import sanitize
from .agents import agent1_requirements as a1, agent2_code as a2, agent3_quality as a3
from .agents import agent4_compliance as a4, agent5_tests as a5, agent6_security as a6, agent7_synthesis as a7


def run(context: Context, model) -> Review:
    if context.evidence and context.evidence.head_sha != context.head_sha:
        raise ValueError("Le commit des preuves ne correspond pas au commit de la PR")
    original = context.model_dump_json()
    context = Context.model_validate(sanitize(context.model_dump()))
    if original != context.model_dump_json():
        context.warnings.append("Certaines données ont été masquées ; vérifier leur impact sur la revue.")
    results = [a1.run(context, model)]
    results.extend([a2.run(context, model), a3.run(context, model)])
    results.append(a4.run(context, model, results[0]))
    results.append(a5.run(context, model, results[0]))
    results.append(a6.run(context, model))
    results.append(a7.run(context, model, results))
    # Validation et masquage de la sortie aussi, avant stockage.
    results = [AgentResult.model_validate(sanitize(r.model_dump())) for r in results]
    decision, reasons = a7.recommendation(context, results)
    return Review(run_id=uuid4().hex, created_at=datetime.now(timezone.utc).isoformat(),
        model=model.name, demo=context.demo, issue_id=context.issue_id,
        issue_updated_at=context.issue_updated_at, repository=context.repository, pr=context.pr,
        head_sha=context.head_sha, base_sha=context.base_sha,
        input_digest=hashlib.sha256(original.encode()).hexdigest(), results=results,
        decision=decision, reasons=reasons, tools=context.evidence.tools if context.evidence else {},
        coverage_percent=context.evidence.coverage_percent if context.evidence else None,
        warnings=context.warnings)
