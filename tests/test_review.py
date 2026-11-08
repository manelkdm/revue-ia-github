import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from review.models import Context, Evidence, ToolResult, AgentResult, Criterion, Finding
from review.llm import DemoModel, Ollama
from review.orchestrator import run
from review.agents.agent7_synthesis import recommendation
from review.agents.agent4_compliance import run as compliance
from review.connectors import OpenProject, GitHub, fetch_context, repo_path
from review.http import Client, NoRedirect
from review.publish import publish
from review.report import save, export_csv
from review.security import redact, safe_markdown


def context(**overrides):
    return Context(**{**dict(ticket_id=42, ticket_subject="Division", ticket_description="CA-1 division sûre", ticket_updated_at="2026-10-04T00:00:00Z", repository="team/calculator", pr=1, head_sha="a" * 40, base_sha="b" * 40, pr_title="Division", diff="+ return a / b"), **overrides})


def clean_evidence(**overrides):
    values = dict(head_sha="a" * 40, generated_at="2026-10-04T00:00:00Z", tools={n: ToolResult(status="passed") for n in ("ruff", "bandit", "gitleaks", "pytest")}, coverage_percent=90, tests_run=3)
    return Evidence(**{**values, **overrides})


def results():
    return [AgentResult(agent=n, status="complete", summary="Analyse", criteria=[Criterion(id="CA-1", text="Critère", status="supported", evidence="Extrait")] if n == 4 else []) for n in range(1, 8)]


class PipelineTests(unittest.TestCase):
    def test_seven_agents_demo(self):
        report = run(context(demo=True), DemoModel())
        self.assertEqual([r.agent for r in report.results], list(range(1, 8)))
        self.assertEqual(report.decision, "revue_humaine_requise")
        self.assertTrue(report.human_approval_required)

    def test_missing_evidence_is_unknown(self):
        decision, reasons = recommendation(context(), results())
        self.assertEqual(decision, "revue_humaine_requise")
        self.assertTrue(any("Couverture inconnue" in r for r in reasons))

    def test_all_checks_never_merge(self):
        decision, _ = recommendation(context(evidence=clean_evidence()), results())
        self.assertEqual(decision, "pret_pour_validation_humaine")

    def test_static_failure_survives_positive_model(self):
        e = clean_evidence()
        e.tools["bandit"].status = "failed"
        self.assertEqual(recommendation(context(evidence=e), results())[0], "corrections_recommandees")

    def test_passed_with_findings_is_not_clean(self):
        e = clean_evidence()
        e.tools["ruff"].total_findings = 1
        self.assertEqual(recommendation(context(evidence=e), results())[0], "corrections_recommandees")

    def test_skipped_tests_not_pass(self):
        e = clean_evidence(tests_skipped=3)
        self.assertEqual(recommendation(context(evidence=e), results())[0], "revue_humaine_requise")

    def test_low_coverage(self):
        self.assertEqual(recommendation(context(evidence=clean_evidence(coverage_percent=20)), results())[0], "corrections_recommandees")

    def test_evidence_wrong_sha_rejected(self):
        with self.assertRaisesRegex(ValueError, "commit"):
            run(context(evidence=clean_evidence(head_sha="c" * 40)), DemoModel())

    def test_llm_down_records_incomplete(self):
        model = Mock(name="model", analyze=Mock(side_effect=TimeoutError()))
        model.name = "test"
        report = run(context(), model)
        self.assertTrue(all(r.status == "incomplete" for r in report.results))
        self.assertEqual(report.decision, "revue_humaine_requise")

    def test_missing_criterion_preserved(self):
        req = AgentResult(agent=1, status="complete", summary="", criteria=[Criterion(id="CA-99", text="Obligation")])
        output = compliance(context(), DemoModel(), req)
        self.assertEqual(output.criteria[0].id, "CA-99")
        self.assertEqual(output.criteria[0].status, "unknown")

    def test_secrets_removed_from_results(self):
        model = DemoModel()
        original = model.analyze
        def response(*args):
            r = original(*args)
            r.summary = 'api_key = "example-secret-value"'
            return r
        model.analyze = response
        self.assertNotIn("example-secret-value", run(context(), model).model_dump_json())

    def test_report_and_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = save(run(context(demo=True), DemoModel()), root)
            self.assertIn("DÉMONSTRATION", (dest / "report.md").read_text(encoding="utf-8"))
            self.assertEqual(len(json.loads((dest / "review.json").read_text(encoding="utf-8"))["results"]), 7)
            export_csv(root, root / "history.csv")
            self.assertIn("team/calculator", (root / "history.csv").read_text(encoding="utf-8"))


class ConnectorTests(unittest.TestCase):
    def clients(self):
        op, git = Mock(), Mock()
        op.ticket.return_value = {"subject": "Ticket", "description": {"raw": "CA-1"}, "updatedAt": "2026-10-04T00:00:00Z"}
        git.pull.return_value = {"state": "open", "merged": False, "head": {"sha": "a" * 40}, "base": {"sha": "b" * 40}, "title": "PR"}
        git.diff.return_value = "+ changed"
        return op, git

    def test_fetch_stable(self):
        op, git = self.clients()
        ctx = fetch_context(op, git, 42, "team/calculator", 1)
        self.assertEqual(ctx.head_sha, "a" * 40)
        self.assertTrue(ctx.warnings)

    def test_changed_head_during_fetch(self):
        op, git = self.clients()
        first = git.pull.return_value
        git.pull.side_effect = [first, {**first, "head": {"sha": "c" * 40}}]
        with self.assertRaisesRegex(ValueError, "changé"):
            fetch_context(op, git, 42, "team/calculator", 1)

    def test_big_diff_refused(self):
        op, git = self.clients()
        git.diff.return_value = "x" * 45001
        with self.assertRaisesRegex(ValueError, "45 000"):
            fetch_context(op, git, 42, "team/calculator", 1)

    def test_api_paths_and_payloads(self):
        op = OpenProject("http://localhost:8080", "fake-token")
        op.http = Mock()
        op.comment(42, "résumé")
        op.http.request.assert_called_once_with("POST", "/api/v3/work_packages/42/activities", {"comment": {"raw": "résumé"}})
        git = GitHub("https://api.github.com", "fake-token")
        git.http = Mock()
        git.diff("team/repo", 2)
        git.http.request.assert_called_once_with("GET", "/repos/team/repo/pulls/2", as_text=True, accept="application/vnd.github.diff")

    def test_repository_paths(self):
        for value in ("../foo", "a/b/c", "a/b?x=1", "https://evil/x"):
            with self.assertRaises(ValueError):
                repo_path(value)

    def test_https_required_remotely(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            Client("http://example.org")

    def test_no_redirect(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.org"))

    def test_demo_publish_refused(self):
        op, git = self.clients()
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, "simulation"):
            publish(run(context(demo=True), DemoModel()), op, git, Path(tmp) / "pub.json")
        git.comment.assert_not_called()

    def test_publish_once(self):
        op, git = self.clients()
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "pub.json"
            review = run(context(), DemoModel())
            publish(review, op, git, journal)
            publish(review, op, git, journal)
            git.comment.assert_called_once()
            op.comment.assert_called_once()

    def test_stale_base_not_published(self):
        op, git = self.clients()
        git.pull.return_value["base"]["sha"] = "c" * 40
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, "commits"):
            publish(run(context(), DemoModel()), op, git, Path(tmp) / "pub.json")
        git.comment.assert_not_called()

    def test_uncertain_send_not_repeated(self):
        op, git = self.clients()
        git.comment.side_effect = TimeoutError()
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "pub.json"
            review = run(context(), DemoModel())
            with self.assertRaises(TimeoutError):
                publish(review, op, git, journal)
            with self.assertRaisesRegex(ValueError, "incertain"):
                publish(review, op, git, journal)
        self.assertEqual(git.comment.call_count, 1)


class ModelTests(unittest.TestCase):
    def test_json_retry_exhausted(self):
        model = Ollama("http://localhost:11434", "test")
        model.http = Mock()
        model.http.request.return_value = {"message": {"content": "{}"}}
        with self.assertRaises(ValueError):
            model.analyze(1, "instructions", {})
        self.assertEqual(model.http.request.call_count, 2)

    def test_llm_cannot_claim_tool_source(self):
        result = AgentResult(agent=2, status="complete", summary="", findings=[Finding(severity="high", title="Bug", evidence="diff", recommendation="Corriger", source="tool")])
        model = Ollama("http://localhost:11434", "test")
        model.http = Mock()
        model.http.request.return_value = {"message": {"content": result.model_dump_json()}}
        self.assertEqual(model.analyze(2, "", {}).findings[0].source, "llm")

    def test_escape_untrusted_markdown(self):
        output = safe_markdown("<script>@everyone [clic](https://evil.example)</script>")
        self.assertNotIn("@everyone", output)
        self.assertNotIn("<script>", output)

    def test_redact_env(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "secret-abcdef123"}):
            self.assertNotIn("secret-abcdef123", redact("le jeton secret-abcdef123"))


if __name__ == "__main__":
    unittest.main()
