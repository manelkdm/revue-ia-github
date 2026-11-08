"""Contexte GitHub et une issue explicitement liée aux exigences."""
import re
from .http import Client, RemoteError
from .models import Context, Issue


def repo_path(repository: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or any(
        part in (".", "..") for part in repository.split("/")
    ):
        raise ValueError("Le dépôt doit avoir la forme proprietaire/depot")
    return "/repos/" + repository


class GitHub:
    def __init__(self, url, token, api_version="2026-03-10"):
        self.http = Client(url, {
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": api_version,
            "User-Agent": "revue-ia-github/0.3.0",
        })

    def pull(self, repository, pr):
        return self.http.request("GET", f"{repo_path(repository)}/pulls/{int(pr)}")

    def diff(self, repository, pr):
        return self.http.request("GET", f"{repo_path(repository)}/pulls/{int(pr)}",
                                 as_text=True, accept="application/vnd.github.diff")

    def issue(self, repository, number):
        return self.http.request("GET", f"{repo_path(repository)}/issues/{int(number)}")

    def comment(self, repository, pr, text):
        return self.http.request("POST", f"{repo_path(repository)}/issues/{int(pr)}/comments", {"body": text})


def check_pull(pull, repository):
    if pull.get("state") != "open" or pull.get("merged") or pull.get("draft"):
        raise ValueError("La PR doit être ouverte et prête pour la revue")
    if pull["head"].get("repo", {}).get("full_name", "").lower() != repository.lower():
        raise ValueError("Seules les PR du même dépôt sont prises en charge")


def requirements_issue(git, repository, body):
    fields = re.findall(r"^(?:Issue liée|Requirements issue)[ \t]*:[ \t]*(.*)$", body, re.MULTILINE | re.IGNORECASE)
    if not fields or (len(fields) == 1 and not fields[0].strip()):
        return None, ["Aucune issue liée. La revue du code et des tests continue."]
    if len(fields) != 1:
        return None, ["Plusieurs champs d'issue liée : indiquez une seule issue."]
    reference = fields[0].strip()
    match = re.fullmatch(r"#([1-9][0-9]*)", reference)
    if not match:
        match = re.fullmatch(r"https://github\.com/" + re.escape(repository) + r"/issues/([1-9][0-9]*)",
                             reference, re.IGNORECASE)
    if not match:
        return None, ["Référence d'issue invalide : utilisez #42 ou l'URL d'une issue du même dépôt."]
    number = int(match[1])
    try:
        data = git.issue(repository, number)
    except RemoteError:
        return None, [f"Issue #{number} inaccessible. La revue du code et des tests continue."]
    if "pull_request" in data:
        return None, [f"La référence #{number} désigne une PR et non une issue."]
    if data.get("number") != number:
        raise ValueError("GitHub a renvoyé une autre issue")
    issue = Issue(number=number, title=data["title"], body=data.get("body") or "")
    return issue, []


def fetch_context(git, repository, pr, standards="", evidence=None):
    before = git.pull(repository, pr)
    check_pull(before, repository)
    diff = git.diff(repository, pr)
    body = before.get("body") or ""
    issue, warnings = requirements_issue(git, repository, body)
    after = git.pull(repository, pr)
    check_pull(after, repository)
    if any(before[branch]["sha"] != after[branch]["sha"] for branch in ("head", "base")):
        raise ValueError("Les commits ont changé pendant la lecture ; relancez la revue")
    if before["title"] != after["title"] or body != (after.get("body") or ""):
        raise ValueError("La description de la PR a changé pendant la lecture ; relancez la revue")
    if len(standards) > 10_000:
        raise ValueError("Standards supérieurs à 10 000 caractères")
    return Context(
        repository=repository, pr=pr, head_sha=before["head"]["sha"], base_sha=before["base"]["sha"],
        pr_title=before["title"], pr_body=body, issue=issue, diff=diff,
        standards=standards, evidence=evidence, warnings=warnings,
    )
