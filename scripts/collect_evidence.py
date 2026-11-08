"""À exécuter dans un environnement jetable, sans jeton ni secret.

Les outils sont lancés avec des arguments fixes et un délai maximum.
pytest n'est exécuté qu'avec --run-tests car il exécute le code du dépôt.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from review.models import Evidence, Finding, ToolResult
from review.security import redact


def command(argv, cwd, timeout=180, extra_env=None):
    env = {k: v for k, v in os.environ.items() if k.upper() in ("PATH", "LANG", "LC_ALL", "SYSTEMROOT", "TMPDIR", "TEMP", "TMP")}
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.update(extra_env or {})
    try:
        result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout, check=False)
        return result.returncode, result.stdout, result.stderr
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return 127, "", type(exc).__name__


def git_state(repo):
    code, sha, _ = command(["git", "rev-parse", "HEAD"], repo)
    if code:
        raise ValueError("Dépôt Git introuvable")
    code, status, _ = command(["git", "status", "--porcelain", "--untracked-files=all"], repo)
    if code or status.strip():
        raise ValueError("Le dépôt doit être propre, sans fichiers non suivis")
    return sha.strip()


def location(path, repo):
    try:
        return str(Path(path).resolve().relative_to(repo))
    except ValueError:
        return str(path)


def finding(title, evidence, severity, file=None, line=None):
    return Finding(title=title[:200], evidence=redact(evidence)[:1500], severity=severity,
        file=file, line=line, source="tool", recommendation="Vérifier le constat et corriger ou documenter une exception justifiée.")


def test_counts(xml_text):
    if "<!DOCTYPE" in xml_text.upper() or "<!ENTITY" in xml_text.upper():
        raise ValueError("XML avec déclaration d'entité refusé")
    root = ET.fromstring(xml_text)
    cases = list(root.iter("testcase"))
    return len(cases), sum(c.find("failure") is not None or c.find("error") is not None for c in cases), sum(c.find("skipped") is not None for c in cases)


def collect(repo, run_tests=False, coverage_source=".", scan_path="."):
    repo = repo.resolve()
    target = (repo / scan_path).resolve()
    if not target.is_relative_to(repo) or not target.is_dir():
        raise ValueError("Le dossier d'analyse doit exister à l'intérieur du dépôt")
    sha = git_state(repo)
    tools = {}
    coverage, counts = None, (0, 0, 0)
    with tempfile.TemporaryDirectory(prefix="revue-evidence-") as tmp:
        work = Path(tmp)
        # Les fichiers de configuration des analyseurs restent hors du dépôt analysé.
        code, out, _ = command(["ruff", "check", "--isolated", "--select", "E4,E7,E9,F", "--output-format", "json", str(target)], work)
        try:
            rows = json.loads(out)
            if code not in (0, 1) or not isinstance(rows, list):
                raise ValueError()
            findings = [finding(f"Ruff {r['code']}", r["message"], "medium", location(r["filename"], repo), r["location"]["row"]) for r in rows[:100]]
            tools["ruff"] = ToolResult(status="failed" if code or rows else "passed", findings=findings, total_findings=len(rows))
        except (ValueError, KeyError, TypeError):
            tools["ruff"] = ToolResult(status="error", details="Ruff absent, en erreur ou résultat invalide")
        code, out, _ = command(["bandit", "-r", str(target), "-f", "json", "-q"], work)
        try:
            data = json.loads(out)
            if code not in (0, 1) or data.get("errors"):
                raise ValueError()
            rows = data["results"]
            findings = [finding(f"Bandit {r['test_id']}", r["issue_text"], r["issue_severity"].lower(), location(r["filename"], repo), r["line_number"]) for r in rows[:100]]
            tools["bandit"] = ToolResult(status="failed" if code or rows else "passed", findings=findings, total_findings=len(rows))
        except (ValueError, KeyError, TypeError):
            tools["bandit"] = ToolResult(status="error", details="Bandit absent, en erreur ou résultat invalide")
        config = work / "gitleaks.toml"
        config.write_text("[extend]\nuseDefault = true\n", encoding="utf-8")
        ignore = work / "gitleaksignore"
        ignore.write_text("", encoding="utf-8")
        output = work / "gitleaks.json"
        code, _, _ = command(["gitleaks", "dir", str(repo), "--config", str(config), "--gitleaks-ignore-path", str(ignore), "--redact=100", "--no-banner", "--report-format", "json", "--report-path", str(output)], work)
        try:
            if code not in (0, 1):
                raise ValueError()
            rows = json.loads(output.read_text(encoding="utf-8"))
            findings = [finding(f"Gitleaks {r['RuleID']}", "Secret potentiel détecté ; valeur volontairement omise.", "high", r["File"], r["StartLine"]) for r in rows[:100]]
            tools["gitleaks"] = ToolResult(status="failed" if code or rows else "passed", findings=findings, total_findings=len(rows))
        except (ValueError, KeyError, TypeError, OSError):
            tools["gitleaks"] = ToolResult(status="error", details="Gitleaks absent, en erreur ou résultat invalide")
        tools["pytest"] = ToolResult(status="not_run", details="Activer --run-tests uniquement dans un environnement isolé")
        if run_tests:
            junit, cov = work / "junit.xml", work / "coverage.json"
            code, _, _ = command([sys.executable, "-m", "pytest", "-p", "pytest_cov", "-p", "no:cacheprovider", "--junitxml=" + str(junit), "--cov=" + coverage_source, "--cov-report=json:" + str(cov)], repo, 300, {"COVERAGE_FILE": str(work / ".coverage")})
            try:
                counts = test_counts(junit.read_text(encoding="utf-8"))
                if code not in (0, 1):
                    raise ValueError()
                coverage = float(json.loads(cov.read_text(encoding="utf-8"))["totals"]["percent_covered"])
                tools["pytest"] = ToolResult(status="failed" if code or counts[1] else "passed", total_findings=counts[1], details=f"{counts[0]} cas, {counts[1]} échecs, {counts[2]} ignorés")
            except (ValueError, KeyError, TypeError, OSError, ET.ParseError):
                tools["pytest"] = ToolResult(status="error", details=f"Rapports absents ou invalides, ou code pytest {code}")
        if git_state(repo) != sha:
            raise ValueError("Le code a changé pendant la collecte")
    return Evidence(head_sha=sha, generated_at=datetime.now(timezone.utc).isoformat(), tools=tools,
        coverage_percent=coverage, tests_run=counts[0], tests_failed=counts[1], tests_skipped=counts[2])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--coverage-source", default=".")
    parser.add_argument("--scan-path", default=".", help="Dossier de code à analyser avec Ruff et Bandit, relatif au dépôt")
    args = parser.parse_args()
    if args.out.resolve().is_relative_to(args.repo.resolve()):
        raise SystemExit("Écrire evidence.json en dehors du dépôt analysé")
    result = collect(args.repo, args.run_tests, args.coverage_source, args.scan_path)
    args.out.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(args.out)
