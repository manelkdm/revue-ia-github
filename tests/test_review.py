import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from review.models import Context, Issue, Evidence, ToolResult, AgentResult, Criterion, Finding, Review
from review.llm import DemoModel, Ollama
from review.orchestrator import run
from review.agents.agent7_synthesis import recommendation
from review.agents.agent4_compliance import run as compliance
from review.connectors import GitHub, fetch_context, repo_path
from review.http import Client, NoRedirect, RemoteError
from review.publish import publish
from review.report import save, markdown
from review.security import redact, safe_markdown


def context(**overrides):
    values = dict(
        issue=Issue(number=42, title="Division", body="CA-1 division sûre"),
        repository="team/calculator", pr=1, head_sha="a" * 40, base_sha="b" * 40,
        pr_title="Division", pr_body="Issue liée : #42", diff="+ return a / b",
    )
    return Context(**{**values, **overrides})


def clean_evidence(**overrides):
    values = dict(head_sha="a" * 40, generated_at="2026-10-04T00:00:00Z",
                  tools={n: ToolResult(status="passed") for n in ("ruff", "bandit", "gitleaks")},
                  coverage_percent=90, tests_run=3)
    values["tools"]["pytest"] = ToolResult(status="passed")
    return Evidence(**{**values, **overrides})


def results():
    return [AgentResult(agent=n, status="complete", summary="Analyse",
                        criteria=[Criterion(id="CA-1", text="Critère", status="supported", evidence="Extrait")]
                        if n == 4 else []) for n in range(1, 8)]


def github():
    git = Mock()
    git.issue.return_value = {"number": 42, "title": "Division", "body": "CA-1 division sûre"}
    git.pull.return_value = {
        "state": "open", "merged": False, "draft": False,
        "head": {"sha": "a" * 40, "repo": {"full_name": "team/calculator"}},
        "base": {"sha": "b" * 40}, "title": "Division", "body": "Issue liée : #42",
    }
    git.diff.return_value = "+ return a / b"
    return git


class PipelineTests(unittest.TestCase):
    def test_seven_agents_demo(self):
        report = run(context(demo=True), DemoModel())
        self.assertEqual([r.agent for r in report.results], list(range(1, 8)))
        self.assertEqual(report.decision, "revue_humaine_requise")
        self.assertTrue(report.human_approval_required)

    def test_missing_evidence_is_unknown(self):
        decision, reasons = recommendation(context(), results())
        self.assertEqual(decision, "revue_humaine_requise")
        self.assertIn("Couverture inconnue.", reasons)

    def test_all_checks_never_merge(self):
        self.assertEqual(recommendation(context(evidence=clean_evidence()), results())[0],
                         "pret_pour_validation_humaine")

    def test_static_failure_survives_positive_model(self):
        evidence = clean_evidence()
        evidence.tools["bandit"].status = "failed"
        report = run(context(evidence=evidence), DemoModel())
        self.assertEqual(report.decision, "corrections_recommandees")
        self.assertEqual(report.tools["bandit"].status, "failed")

    def test_passed_with_findings_is_not_clean(self):
        evidence = clean_evidence()
        evidence.tools["ruff"].total_findings = 1
        self.assertEqual(recommendation(context(evidence=evidence), results())[0], "corrections_recommandees")

    def test_skipped_tests_not_pass(self):
        self.assertEqual(recommendation(context(evidence=clean_evidence(tests_skipped=3)), results())[0],
                         "revue_humaine_requise")

    def test_no_implicit_coverage_threshold(self):
        self.assertEqual(recommendation(context(evidence=clean_evidence(coverage_percent=20)), results())[0],
                         "pret_pour_validation_humaine")

    def test_evidence_wrong_sha_rejected(self):
        with self.assertRaisesRegex(ValueError, "commit"):
            run(context(evidence=clean_evidence(head_sha="c" * 40)), DemoModel())

    def test_llm_down_records_incomplete(self):
        model = Mock(analyze=Mock(side_effect=TimeoutError()))
        model.name = "test"
        report = run(context(), model)
        self.assertTrue(all(r.status == "incomplete" for r in report.results))
        self.assertEqual(model.analyze.call_count, 7)

    def test_missing_issue_continues_other_agents(self):
        model = DemoModel()
        model.analyze = Mock(wraps=model.analyze)
        report = run(context(issue=None, pr_body=""), model)
        self.assertEqual([call.args[0] for call in model.analyze.call_args_list], [2, 3, 5, 6, 7])
        self.assertFalse(report.results[0].criteria)
        self.assertFalse(report.results[3].criteria)
        self.assertIn("Aucune issue liée", markdown(report))

    def test_missing_criterion_preserved(self):
        req = AgentResult(agent=1, status="complete", summary="",
                          criteria=[Criterion(id="CA-99", text="Obligation")])
        output = compliance(context(), DemoModel(), req)
        self.assertEqual(output.criteria[0].id, "CA-99")
        self.assertEqual(output.criteria[0].status, "unknown")

    def test_conflicting_requirements_reach_model_and_survive_report(self):
        model = DemoModel()
        original = model.analyze
        def analyze(agent, instruction, payload):
            result = original(agent, instruction, payload)
            if agent == 4:
                self.assertIn("autorité", instruction)
                self.assertEqual(payload["issue"]["body"], "CA-1 division sûre")
                self.assertEqual(payload["pr_body"], "Autoriser la division par zéro")
                result.criteria = [Criterion(id="CA-1", text="Division", status="not_met",
                                             evidence="L'issue exige une erreur, la PR propose le contraire.")]
            return result
        model.analyze = analyze
        report = run(context(pr_body="Autoriser la division par zéro"), model)
        self.assertEqual(report.results[3].criteria[0].status, "not_met")
        self.assertEqual(report.decision, "corrections_recommandees")
        self.assertIn("propose le contraire", markdown(report))

    def test_oversized_diff_keeps_tools_without_calling_model(self):
        evidence = clean_evidence()
        evidence.tools["bandit"] = ToolResult(status="failed", total_findings=1, findings=[
            Finding(severity="high", title="Injection", evidence="Ligne 2",
                    recommendation="Valider", source="tool")])
        model = Mock()
        model.name = "test"
        report = run(context(diff="x" * 45001, evidence=evidence), model)
        model.analyze.assert_not_called()
        self.assertTrue(all(r.status == "incomplete" for r in report.results))
        self.assertIn("Injection", markdown(report))
        self.assertEqual(report.finding_groups, [["outil-bandit-1"]])

    def test_secrets_removed_from_results(self):
        model = DemoModel()
        original = model.analyze
        def response(*args):
            result = original(*args)
            result.summary = 'api_key = "example-secret-value"'
            return result
        model.analyze = response
        self.assertNotIn("example-secret-value", run(context(), model).model_dump_json())

    def test_report_files_without_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = save(run(context(demo=True), DemoModel()), root)
            self.assertIn("DÉMONSTRATION", (dest / "report.md").read_text(encoding="utf-8"))
            report = Review.model_validate_json((dest / "review.json").read_text(encoding="utf-8"))
            self.assertEqual(len(report.results), 7)
            self.assertEqual(set(p.name for p in dest.iterdir()), {"review.json", "report.md"})
            self.assertEqual(list(root.iterdir()), [dest])


class ConnectorTests(unittest.TestCase):
    def test_fetch_stable(self):
        git = github()
        ctx = fetch_context(git, "team/calculator", 1)
        self.assertEqual(ctx.issue.number, 42)
        git.issue.assert_called_once_with("team/calculator", 42)

    def test_issue_missing_invalid_or_inaccessible(self):
        for body in ("", "Issue liée :", "Issue liée : #42 #43",
                     "Issue liée : https://github.com/other/repo/issues/42",
                     "Issue liée : #42\nIssue liée : #43"):
            with self.subTest(body=body):
                git = github()
                git.pull.return_value["body"] = body
                ctx = fetch_context(git, "team/calculator", 1)
                self.assertIsNone(ctx.issue)
                self.assertTrue(ctx.warnings)
                git.issue.assert_not_called()
        git = github()
        git.issue.side_effect = RemoteError("indisponible")
        ctx = fetch_context(git, "team/calculator", 1)
        self.assertIn("inaccessible", ctx.warnings[0])

    def test_same_repository_issue_url(self):
        git = github()
        git.pull.return_value["body"] = "Issue liée : https://github.com/team/calculator/issues/42"
        self.assertEqual(fetch_context(git, "team/calculator", 1).issue.number, 42)

    def test_pr_reference_is_not_an_issue(self):
        git = github()
        git.issue.return_value["pull_request"] = {}
        self.assertIsNone(fetch_context(git, "team/calculator", 1).issue)

    def test_changed_head_or_description_during_fetch(self):
        for change in ({"head": {"sha": "c" * 40, "repo": {"full_name": "team/calculator"}}},
                       {"body": "Nouvelle description"}):
            git = github()
            before = git.pull.return_value
            git.pull.side_effect = [before, {**before, **change}]
            with self.assertRaisesRegex(ValueError, "changé"):
                fetch_context(git, "team/calculator", 1)

    def test_drafts_closed_and_forks_rejected(self):
        for change in ({"draft": True}, {"state": "closed"},
                       {"head": {"sha": "a" * 40, "repo": {"full_name": "other/calculator"}}}):
            git = github()
            git.pull.return_value.update(change)
            with self.assertRaises(ValueError):
                fetch_context(git, "team/calculator", 1)
            git.diff.assert_not_called()

    def test_big_diff_reaches_incomplete_report(self):
        git = github()
        git.diff.return_value = "x" * 45001
        ctx = fetch_context(git, "team/calculator", 1)
        self.assertTrue(all(r.status == "incomplete" for r in run(ctx, DemoModel()).results))

    def test_api_paths_and_payloads(self):
        git = GitHub("https://api.github.com", "fake-token")
        git.http = Mock()
        git.issue("team/repo", 42)
        git.http.request.assert_called_once_with("GET", "/repos/team/repo/issues/42")

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
        git = github()
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, "simulation"):
            publish(run(context(demo=True), DemoModel()), git, Path(tmp) / "pub.json")
        git.comment.assert_not_called()

    def test_publish_once(self):
        git = github()
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "pub.json"
            review = run(context(), DemoModel())
            publish(review, git, journal)
            publish(review, git, journal)
            git.comment.assert_called_once()

    def test_stale_inputs_not_published(self):
        for changed in ("base", "description", "issue"):
            git = github()
            if changed == "base":
                git.pull.return_value["base"]["sha"] = "c" * 40
            elif changed == "description":
                git.pull.return_value["body"] = "Nouvelle description"
            else:
                git.issue.return_value["body"] = "Nouvelles exigences"
            with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, "changé"):
                publish(run(context(), DemoModel()), git, Path(tmp) / "pub.json")
            git.comment.assert_not_called()

    def test_uncertain_send_not_repeated(self):
        git = github()
        git.comment.side_effect = TimeoutError()
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "pub.json"
            review = run(context(), DemoModel())
            with self.assertRaises(TimeoutError):
                publish(review, git, journal)
            with self.assertRaisesRegex(ValueError, "incertain"):
                publish(review, git, journal)
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
        result = AgentResult(agent=2, status="complete", summary="", findings=[
            Finding(severity="high", title="Bug", evidence="diff", recommendation="Corriger", source="tool")])
        model = Ollama("http://localhost:11434", "test")
        model.http = Mock()
        model.http.request.return_value = {"message": {"content": result.model_dump_json()}}
        self.assertEqual(model.analyze(2, "", {}).findings[0].source, "llm")

    def test_length_limit_records_incomplete(self):
        model = Ollama("http://localhost:11434", "test")
        model.http = Mock()
        model.http.request.return_value = {
            "message": {"content": AgentResult(agent=2, status="complete", summary="").model_dump_json()},
            "done_reason": "length",
        }
        self.assertEqual(model.analyze(2, "", {}).status, "incomplete")

    def test_escape_untrusted_markdown(self):
        output = safe_markdown("<script>@everyone [clic](https://evil.example)</script>")
        self.assertNotIn("@everyone", output)
        self.assertNotIn("<script>", output)

    def test_redact_env(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "secret-abcdef123"}):
            self.assertNotIn("secret-abcdef123", redact("le jeton secret-abcdef123"))


if __name__ == "__main__":
    unittest.main()
