"""Sept agents conservés ; synthèse et constats regroupés dans le rapport final."""
import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4
from .models import Context, Review, AgentResult
from .security import sanitize
from .findings import catalog, consolidate
from .agents import agent1_requirements as a1, agent2_code as a2, agent3_quality as a3
from .agents import agent4_compliance as a4, agent5_tests as a5, agent6_security as a6, agent7_synthesis as a7


def source_digest(context):
    data = {
        "head": context.head_sha, "base": context.base_sha,
        "title": context.pr_title, "body": context.pr_body,
        "issue": context.issue.model_dump() if context.issue else None,
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()


def run(context: Context, model) -> Review:
    if context.evidence and context.evidence.head_sha != context.head_sha:
        raise ValueError("Le commit des preuves ne correspond pas au commit de la PR")
    original = context.model_dump_json()
    fingerprint = source_digest(context)
    context = Context.model_validate(sanitize(context.model_dump()))
    if original != context.model_dump_json():
        context.warnings.append("Certaines données ont été masquées ; vérifier leur impact sur la revue.")
    if context.issue is None and not any("issue" in w.lower() for w in context.warnings):
        context.warnings.append("Aucune issue liée. La revue du code et des tests continue.")
    context.warnings.append("Analyse du diff uniquement : fichiers inchangés, binaires et contexte du dépôt non inspectés.")
    if len(context.diff) > 45_000:
        results = [
            AgentResult(agent=n, status="incomplete", summary="Analyse IA non exécutée.",
                        limitations=["Diff supérieur à 45 000 caractères ; aucune troncature silencieuse."])
            for n in range(1, 8)
        ]
    else:
        results = [a1.run(context, model)]
        results.extend([a2.run(context, model), a3.run(context, model)])
        results.append(a4.run(context, model, results[0]))
        results.append(a5.run(context, model, results[0]))
        results.append(a6.run(context, model))
        results.append(a7.run(context, model, results))
    results = [AgentResult.model_validate(sanitize(result.model_dump())) for result in results]
    tools = context.evidence.tools if context.evidence else {}
    groups, rejected = consolidate(catalog(results, tools), results[-1].duplicate_groups)
    if rejected:
        context.warnings.append("Certains regroupements proposés étaient invalides ; les constats ont été conservés séparément.")
    decision, reasons = a7.recommendation(context, results)
    return Review(
        schema_version=3, run_id=uuid4().hex, created_at=datetime.now(timezone.utc).isoformat(),
        model=model.name, demo=context.demo, repository=context.repository, pr=context.pr,
        head_sha=context.head_sha, base_sha=context.base_sha, source_digest=fingerprint,
        input_digest=hashlib.sha256(original.encode("utf-8")).hexdigest(), results=results,
        finding_groups=groups, decision=decision, reasons=reasons, tools=tools,
        coverage_percent=context.evidence.coverage_percent if context.evidence else None,
        warnings=context.warnings,
    )
