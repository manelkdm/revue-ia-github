"""Publish a GitHub-only PR summary; check commit/issue freshness first."""
import json
from pathlib import Path
from .report import publication_text


def publish(review, git, journal: Path):
    if review.demo:
        raise ValueError("La publication d'une simulation est interdite")
    state = json.loads(journal.read_text()) if journal.exists() else {}
    if state.get("run_id", review.run_id) != review.run_id:
        raise ValueError("Journal de publication associé à une autre revue")
    if state.get("github") == "sent":
        return state
    pull = git.pull(review.repository, review.pr)
    if (
        pull.get("state") != "open" or pull.get("merged")
        or pull["head"]["sha"] != review.head_sha
        or pull["base"]["sha"] != review.base_sha
    ):
        raise ValueError("PR fermée ou commits modifiés depuis la revue. Refaire l'analyse.")
    if git.issue(review.repository, review.issue_id)["updated_at"] != review.issue_updated_at:
        raise ValueError("Issue GitHub modifiée depuis la revue. Refaire l'analyse.")
    if state.get("github") == "sending":
        raise ValueError("Envoi GitHub incertain. Vérifier la PR et le journal avant une nouvelle tentative.")
    state.update(run_id=review.run_id, github="sending")
    journal.write_text(json.dumps(state, indent=2), encoding="utf-8")
    # The bot updates its previous review comment instead of adding one per PR push.
    git.review_comment(review.repository, review.pr, publication_text(review))
    state["github"] = "sent"
    journal.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state
