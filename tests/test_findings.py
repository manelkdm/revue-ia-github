import unittest
from review.findings import catalog, consolidate, validate_groups
from review.models import AgentResult, Finding, ToolResult, Review
from review.llm import DemoModel
from review.orchestrator import run
from review.report import markdown, publication_text, finding_lines
from test_review import context, clean_evidence


def finding(**overrides):
    return Finding(**{**dict(severity="medium", title="Division non protégée",
                            evidence="return a / b", recommendation="Vérifier b avant la division",
                            file="calculator.py", line=4), **overrides})


class FindingsTests(unittest.TestCase):
    def test_exact_duplicates_keep_highest_severity_and_all_actions(self):
        entries = {"a": finding(), "b": finding(severity="high", recommendation="Ajouter le test de division par zéro")}
        groups, rejected = consolidate(entries, [])
        self.assertEqual(groups, [["a", "b"]])
        self.assertFalse(rejected)
        validate_groups(entries, groups)

    def test_distinct_locations_and_problems_stay_separate(self):
        entries = {"a": finding(), "b": finding(file="other.py"),
                   "c": finding(line=9), "d": finding(title="Autre problème", evidence="Autre ligne")}
        groups, rejected = consolidate(entries, [["a", "b"], ["a", "c"]])
        self.assertEqual(len(groups), 4)
        self.assertTrue(rejected)

    def test_unknown_ids_and_locations_do_not_drop_findings(self):
        entries = {"a": finding(file=None), "b": finding(title="Autre formulation", file=None)}
        groups, rejected = consolidate(entries, [["a", "missing"], ["a", "b"], ["a"]])
        self.assertEqual(groups, [["a"], ["b"]])
        self.assertTrue(rejected)

    def test_overlapping_groups_keep_each_reference_once(self):
        entries = {key: finding(title=key) for key in ("a", "b", "c", "d")}
        groups, _ = consolidate(entries, [["a", "b"], ["b", "c"]])
        validate_groups(entries, groups)
        self.assertIn(["a", "b", "c"], groups)
        self.assertIn(["d"], groups)

    def test_semantic_duplicates_are_grouped_in_report_with_original_evidence(self):
        model = DemoModel()
        original = model.analyze
        def analyze(agent, instruction, payload):
            result = original(agent, instruction, payload)
            if agent == 2:
                result.findings = [finding()]
            elif agent == 3:
                result.findings = [finding(title="Diviseur zéro non géré", severity="high",
                                           evidence="Aucune garde avant la ligne 4",
                                           recommendation="Ajouter le test de division par zéro")]
            elif agent == 6:
                result.findings = [finding(title="Autre risque", evidence="Risque distinct")]
            elif agent == 7:
                self.assertEqual(set(payload["findings"]), {"agent-2-1", "agent-3-1", "agent-6-1"})
                result.duplicate_groups = [["agent-2-1", "agent-3-1"]]
                # Aucun constat inventé par la synthèse ne doit entrer dans le rapport.
                result.findings = [finding(title="Constat inventé")]
            return result
        model.analyze = analyze
        report = run(context(), model)
        self.assertEqual(len(report.results), 7)
        self.assertEqual(len(report.finding_groups), 2)
        text = markdown(report)
        self.assertEqual(text.count("**Diviseur zéro non géré**"), 1)
        self.assertIn("gravité élevée", text)
        self.assertIn("return a / b", text)
        self.assertIn("Aucune garde avant la ligne 4", text)
        self.assertIn("Vérifier b avant la division", text)
        self.assertIn("Ajouter le test de division par zéro", text)
        self.assertIn("Autre risque", text)
        self.assertNotIn("Constat inventé", report.model_dump_json())
        self.assertIn("Division non protégée", report.model_dump_json())

    def test_tool_finding_survives_grouping_with_model(self):
        evidence = clean_evidence()
        evidence.tools["bandit"] = ToolResult(status="failed", total_findings=1,
                                              findings=[finding(source="tool", severity="critical")])
        model = DemoModel()
        original = model.analyze
        def analyze(agent, instruction, payload):
            result = original(agent, instruction, payload)
            if agent == 2:
                result.findings = [finding()]
            return result
        model.analyze = analyze
        report = run(context(evidence=evidence), model)
        self.assertEqual(len(report.finding_groups), 1)
        self.assertIn("outil-bandit-1", report.finding_groups[0])
        self.assertEqual(report.tools["bandit"].status, "failed")
        self.assertIn("gravité critique", markdown(report))
        self.assertIn("outil bandit", markdown(report))

    def test_synthesis_failure_still_preserves_and_deduplicates_findings(self):
        model = DemoModel()
        original = model.analyze
        def analyze(agent, instruction, payload):
            if agent == 7:
                raise TimeoutError()
            result = original(agent, instruction, payload)
            if agent in (2, 3):
                result.findings = [finding()]
            return result
        model.analyze = analyze
        report = run(context(), model)
        self.assertEqual(report.results[-1].status, "incomplete")
        self.assertEqual(len(report.finding_groups), 1)
        self.assertIn("Division non protégée", markdown(report))

    def test_saved_report_cannot_omit_or_duplicate_references(self):
        evidence = clean_evidence()
        evidence.tools["ruff"].findings = [finding(source="tool")]
        report = run(context(evidence=evidence), DemoModel())
        for groups in ([], [["outil-ruff-1"], ["outil-ruff-1"]], [["inconnu"]]):
            data = report.model_dump()
            data["finding_groups"] = groups
            with self.assertRaisesRegex(ValueError, "chaque constat"):
                Review.model_validate(data)

    def test_comment_limits_groups_without_losing_full_report(self):
        evidence = clean_evidence()
        evidence.tools["ruff"].findings = [finding(title=f"Problème {n}", line=n + 1) for n in range(7)]
        report = run(context(evidence=evidence), DemoModel())
        self.assertEqual(len(report.finding_groups), 7)
        self.assertEqual(publication_text(report).count("**Problème"), 5)
        self.assertIn("2 autres constats", publication_text(report))
        self.assertEqual(markdown(report).count("**Problème"), 7)

    def test_saved_groups_cannot_hide_another_location(self):
        entries = {"a": finding(), "b": finding(file="other.py")}
        with self.assertRaisesRegex(ValueError, "emplacements"):
            validate_groups(entries, [["a", "b"]])

    def test_code_evidence_preserves_case_and_spacing(self):
        entries = {"a": finding(evidence="return A / b"), "b": finding(evidence="return a / b")}
        groups, _ = consolidate(entries, [])
        self.assertEqual(len(groups), 2)
        text = "\n".join(finding_lines(["a", "b"], entries))
        self.assertIn("return A / b", text)
        self.assertIn("return a / b", text)
