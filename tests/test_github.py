import io
import contextlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from review.connectors import GitHub
from review.cli import github_client
from review.ci import gate, read_evidence, main as ci_main
from review.models import Review, Provenance
from review.orchestrator import run
from review.llm import DemoModel
from review.publish import publish
from test_review import context, clean_evidence, github


class GitHubTests(unittest.TestCase):
    def test_auth_and_diff_media_type(self):
        github = GitHub("https://api.github.com", "example-token")
        response = io.BytesIO(b"diff --git a/a.py b/a.py\n")
        github.http.opener = Mock()
        github.http.opener.open.return_value = response
        self.assertIn("diff --git", github.diff("team/repo", 2))
        request = github.http.opener.open.call_args.args[0]
        headers = {k.lower(): v for k, v in request.header_items()}
        self.assertEqual(request.full_url, "https://api.github.com/repos/team/repo/pulls/2")
        self.assertEqual(headers["accept"], "application/vnd.github.diff")
        self.assertEqual(headers["authorization"], "Bearer example-token")
        self.assertEqual(headers["x-github-api-version"], "2026-03-10")

    def test_comment_json_and_path(self):
        github = GitHub("https://api.github.com", "example-token")
        github.http.opener = Mock()
        github.http.opener.open.return_value = io.BytesIO(b'{"id":123}')
        self.assertEqual(github.comment("team/repo", 3, "Résumé")["id"], 123)
        request = github.http.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.github.com/repos/team/repo/issues/3/comments")
        self.assertEqual(json.loads(request.data), {"body": "Résumé"})
        self.assertEqual(request.get_method(), "POST")

    def test_pull_json_media_type(self):
        github = GitHub("https://api.github.com", "example-token")
        github.http.opener = Mock()
        github.http.opener.open.return_value = io.BytesIO(b'{"state":"open"}')
        github.pull("team/repo", 3)
        request = github.http.opener.open.call_args.args[0]
        self.assertEqual(dict((k.lower(), v) for k, v in request.header_items())["accept"], "application/vnd.github+json")

    def test_clients_default_github_url(self):
        with patch.dict("os.environ", {"GITHUB_TOKEN": "gh-test"}, clear=True):
            self.assertEqual(github_client().http.base, "https://api.github.com")

    def test_old_report_version_is_rejected(self):
        data = run(context(demo=True), DemoModel()).model_dump()
        data["schema_version"] = 2
        with self.assertRaisesRegex(ValueError, "incompatible"):
            Review.model_validate(data)

    def test_github_publication_journal(self):
        git = github()
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "publication.json"
            publish(run(context(), DemoModel()), git, journal)
            self.assertEqual(json.loads(journal.read_text(encoding="utf-8"))["github"], "sent")


class ArtifactTests(unittest.TestCase):
    def test_normalize_replaces_claimed_provenance_and_verify_checks_it(self):
        provenance = Provenance(repository="team/calculator", pr=1, base_sha="b" * 40,
                                run_id=123, run_attempt=1)
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw.json"
            output = Path(tmp) / "normalized.json"
            raw.write_text(clean_evidence(provenance=provenance.model_copy(update={"run_id": 999})).model_dump_json(), encoding="utf-8")
            options = ["--head", "a" * 40, "--repo", "team/calculator", "--pr", "1", "--base", "b" * 40,
                       "--run-id", "123", "--run-attempt", "1"]
            with patch("sys.argv", ["ci", "normalize", "--input", str(raw), "--output", str(output), *options]), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ci_main(), 0)
            self.assertEqual(read_evidence(output).provenance, provenance)
            with patch("sys.argv", ["ci", "verify", "--input", str(output), *options]), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ci_main(), 0)

    def test_provenance_must_match_repository_pr_base_run_and_attempt(self):
        provenance = Provenance(repository="team/calculator", pr=1, base_sha="b" * 40,
                                run_id=123, run_attempt=1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evidence.json"
            evidence = clean_evidence(provenance=provenance)
            path.write_text(evidence.model_dump_json(), encoding="utf-8")
            self.assertEqual(read_evidence(path, "a" * 40, provenance).provenance, provenance)
            for change in ({"repository": "other/repo"}, {"pr": 2}, {"base_sha": "c" * 40},
                           {"run_id": 124}, {"run_attempt": 2}):
                with self.subTest(change=change), self.assertRaisesRegex(ValueError, "provenance"):
                    read_evidence(path, "a" * 40, provenance.model_copy(update=change))
            evidence.provenance = None
            path.write_text(evidence.model_dump_json(), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "provenance"):
                read_evidence(path, "a" * 40, provenance)

    def test_valid_evidence_for_exact_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evidence.json"
            path.write_text(clean_evidence().model_dump_json(), encoding="utf-8")
            self.assertEqual(read_evidence(path, "a" * 40).head_sha, "a" * 40)

    def test_wrong_commit_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evidence.json"
            path.write_text(clean_evidence().model_dump_json(), encoding="utf-8")
            with self.assertRaises(ValueError):
                read_evidence(path, "b" * 40)

    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evidence.json"
            path.write_text(clean_evidence().model_dump_json(), encoding="utf-8")
            link = Path(tmp) / "link.json"
            try:
                link.symlink_to(path)
            except OSError as exc:
                if getattr(exc, "winerror", None) == 1314:
                    self.skipTest("Windows symlink creation requires Developer Mode or elevated privileges")
                raise
            with self.assertRaises(ValueError):
                read_evidence(link)

    def test_oversized_file_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evidence.json"
            path.write_bytes(b"x" * 2_000_001)
            with self.assertRaises(ValueError):
                read_evidence(path)

    def test_invalid_schema_does_not_echo_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evidence.json"
            path.write_text('{"secret":"do-not-print-this"}', encoding="utf-8")
            with self.assertRaises(ValueError) as exc:
                read_evidence(path)
            self.assertNotIn("do-not-print-this", str(exc.exception))

    def test_clean_gate(self):
        self.assertEqual(gate(clean_evidence()), [])

    def test_coverage_threshold_is_explicit(self):
        evidence = clean_evidence(coverage_percent=20)
        self.assertEqual(gate(evidence), [])
        self.assertTrue(gate(evidence, minimum_coverage=80))

    def test_missing_tool_fails_gate(self):
        evidence = clean_evidence()
        del evidence.tools["bandit"]
        self.assertTrue(any("bandit" in x for x in gate(evidence)))

    def test_skipped_and_missing_coverage_fail_gate(self):
        evidence = clean_evidence(tests_skipped=3, coverage_percent=None)
        self.assertEqual(len(gate(evidence)), 2)


if __name__ == "__main__":
    unittest.main()
