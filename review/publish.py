"""Publication explicite. Un envoi incertain n'est jamais réessayé aveuglément."""
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
    if pull.get("state") != "open" or pull.get("merged") or pull["head"]["sha"] != review.head_sha or pull["base"]["sha"] != review.base_sha:
        raise ValueError("PR fermée ou commits modifiés depuis la revue. Refaire l'analyse.")
    state["run_id"] = review.run_id
    text = publication_text(review)
    for target in ("github",):
        if state.get(target) == "sent":
            continue
        if state.get(target) == "sending":
            raise ValueError(f"Envoi {target} incertain. Vérifier le commentaire et le journal avant une nouvelle tentative.")
        state[target] = "sending"
        journal.write_text(json.dumps(state, indent=2), encoding="utf-8")
        if target == "github":
            git.comment(review.repository, review.pr, text)
        else:
            raise ValueError(f"Destination inconnue : {target}")
        state[target] = "sent"
        journal.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state
