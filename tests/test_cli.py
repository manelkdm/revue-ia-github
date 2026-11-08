import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from review.cli import main
from review.llm import DemoModel
from review.models import Review
from test_review import github


class CliTests(unittest.TestCase):
    def test_changed_workflow_commits_refuse_model_and_report(self):
        for flag in ("--expected-head", "--expected-base"):
            with tempfile.TemporaryDirectory() as tmp:
                args = ["review", "--env", str(Path(tmp) / "absent.env"), "review",
                        "--repo", "team/calculator", "--pr", "1", "--out", tmp, flag, "c" * 40]
                with patch("sys.argv", args), patch("review.cli.github_client", return_value=github()), \
                        patch("review.cli.Ollama") as model, contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(), 2)
                model.assert_not_called()
                self.assertFalse(list(Path(tmp).glob("*/review.json")))

    def test_review_without_ticket_writes_complete_report(self):
        git = github()
        with tempfile.TemporaryDirectory() as tmp:
            args = ["review", "--env", str(Path(tmp) / "absent.env"), "review",
                    "--repo", "team/calculator", "--pr", "1", "--out", tmp]
            with patch("sys.argv", args), patch("review.cli.github_client", return_value=git), \
                    patch("review.cli.Ollama", return_value=DemoModel()), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
            paths = list(Path(tmp).glob("*/review.json"))
            self.assertEqual(len(paths), 1)
            report = Review.model_validate_json(paths[0].read_text(encoding="utf-8"))
            self.assertEqual(len(report.results), 7)
            git.comment.assert_not_called()

    def test_missing_issue_saves_partial_report_and_continues_code_review(self):
        git = github()
        git.pull.return_value["body"] = ""
        with tempfile.TemporaryDirectory() as tmp:
            args = ["review", "--env", str(Path(tmp) / "absent.env"), "review",
                    "--repo", "team/calculator", "--pr", "1", "--out", tmp]
            with patch("sys.argv", args), patch("review.cli.github_client", return_value=git), \
                    patch("review.cli.Ollama", return_value=DemoModel()), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 2)
            report = Review.model_validate_json(next(Path(tmp).glob("*/review.json")).read_text(encoding="utf-8"))
            self.assertEqual(report.results[1].status, "complete")
            self.assertEqual(report.results[3].status, "incomplete")
            self.assertTrue(any("Aucune issue" in warning for warning in report.warnings))
            git.comment.assert_not_called()
