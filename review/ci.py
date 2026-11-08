"""Valide un artefact JSON sans exécuter le code de la PR."""
import argparse
import os
from pathlib import Path
import re
import stat
from .models import Evidence


def read_evidence(path: Path, expected_sha: str | None = None) -> Evidence:
    if expected_sha is not None and not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        raise ValueError("SHA attendu invalide")
    if path.is_symlink():
        raise ValueError("Un artefact ne doit pas être un lien symbolique")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(fd, "rb") as stream:
        meta = os.fstat(stream.fileno())
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > 2_000_000:
            raise ValueError("Artefact invalide ou supérieur à 2 Mo")
        data = stream.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError("Artefact trop volumineux")
    try:
        evidence = Evidence.model_validate_json(data)
    except ValueError:
        raise ValueError("Schéma des preuves invalide") from None
    if expected_sha is not None and evidence.head_sha != expected_sha:
        raise ValueError("Les preuves ne correspondent pas au commit attendu")
    return evidence


def gate(evidence: Evidence, minimum_coverage: float | None = None) -> list[str]:
    issues = []
    for name in ("ruff", "bandit", "gitleaks", "pytest"):
        tool = evidence.tools.get(name)
        if not tool or tool.status != "passed" or tool.total_findings or tool.findings:
            issues.append(f"{name} : contrôle absent, incomplet ou avec constats")
    if evidence.tests_run - evidence.tests_skipped <= 0 or evidence.tests_failed:
        issues.append("Tests absents, tous ignorés ou en échec")
    if evidence.coverage_percent is None:
        issues.append("Couverture inconnue")
    elif minimum_coverage is not None and evidence.coverage_percent < minimum_coverage:
        issues.append(f"Couverture inconnue ou inférieure à {minimum_coverage:g} %")
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("normalize", "gate"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        evidence = read_evidence(args.input, args.head)
        if args.command == "normalize":
            if not args.output:
                parser.error("normalize demande --output")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(evidence.model_dump_json(indent=2), encoding="utf-8")
            print("Preuves structurées et commit vérifiés. Ceci n'atteste pas leur authenticité.")
            return 0
        issues = gate(evidence)
        for issue in issues:
            print(issue)
        return 1 if issues else 0
    except (ValueError, OSError) as exc:
        print(f"Contrôle des preuves refusé ({type(exc).__name__}). Vérifier le fichier et le SHA.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
