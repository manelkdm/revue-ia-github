"""Publication GitHub manuelle ; pas de nouvelle tentative aveugle après un envoi incertain."""
import json
from pathlib import Path
from .connectors import fetch_context
from .orchestrator import source_digest
from .report import publication_text


def publish(review, git, journal: Path):
    if review.demo:
        raise ValueError("La publication d'une simulation est interdite")
    state = json.loads(journal.read_text(encoding="utf-8")) if journal.exists() else {}
    if state.get("run_id", review.run_id) != review.run_id:
        raise ValueError("Journal de publication associé à une autre revue")
    if state.get("github") == "sent":
        return state
    if state.get("github") == "sending":
        raise ValueError("Envoi GitHub incertain ; vérifier le commentaire et le journal avant de réessayer")
    current = fetch_context(git, review.repository, review.pr)
    if source_digest(current) != review.source_digest:
        raise ValueError("Les commits, la description ou les exigences ont changé ; refaire la revue")
    state.update(run_id=review.run_id, github="sending")
    journal.write_text(json.dumps(state, indent=2), encoding="utf-8")
    git.comment(review.repository, review.pr, publication_text(review))
    state["github"] = "sent"
    journal.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state
