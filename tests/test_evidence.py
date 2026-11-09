import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from review.models import Evidence
from review.watch import fingerprint
from test_review import context

spec = importlib.util.spec_from_file_location("collector", Path(__file__).resolve().parents[1] / "scripts" / "collect_evidence.py")
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class EvidenceTests(unittest.TestCase):
    def test_junit_counts_do_not_double_count_suites(self):
        xml = '<testsuites tests="3"><testsuite tests="3"><testcase/><testcase><failure/></testcase><testcase><skipped/></testcase></testsuite></testsuites>'
        self.assertEqual(collector.test_counts(xml), (3, 1, 1))

    def test_entities_refused(self):
        with self.assertRaises(ValueError):
            collector.test_counts('<!DOCTYPE test [<!ENTITY a "abc">]><testsuites/>')

    def test_counts_must_be_coherent(self):
        with self.assertRaises(ValueError):
            Evidence(head_sha="a" * 40, generated_at="now", tools={}, tests_run=1, tests_failed=2)

    def test_tools_and_coverage_collected(self):
        def fake_command(argv, cwd, timeout=180, extra_env=None):
            if argv[0] == "ruff":
                return 1, json.dumps([{"code": "F401", "message": "unused import", "filename": str(cwd / "app.py"), "location": {"row": 1}}]), ""
            if argv[0] == "bandit":
                return 0, '{"results": [], "errors": []}', ""
            if argv[0] == "gitleaks":
                Path(argv[argv.index("--report-path") + 1]).write_text('[]')
                return 0, "", ""
            junit = next(x.split("=", 1)[1] for x in argv if x.startswith("--junitxml="))
            cov = next(x.split(":", 1)[1] for x in argv if x.startswith("--cov-report="))
            Path(junit).write_text('<testsuites><testsuite><testcase/></testsuite></testsuites>')
            Path(cov).write_text('{"totals":{"percent_covered": 88.5}}')
            self.assertIn("COVERAGE_FILE", extra_env)
            return 0, "", ""
        with patch.object(collector, "git_state", return_value="a" * 40), patch.object(collector, "command", side_effect=fake_command):
            result = collector.collect(Path("/tmp"), True)
        self.assertEqual(result.coverage_percent, 88.5)
        self.assertEqual(result.tests_run, 1)
        self.assertEqual(result.tools["ruff"].status, "failed")
        self.assertEqual(result.tools["bandit"].status, "passed")
        self.assertEqual(result.tools["gitleaks"].status, "passed")

    def test_absent_tools_are_errors_not_success(self):
        with patch.object(collector, "git_state", return_value="a" * 40), patch.object(collector, "command", return_value=(127, "", "not found")):
            result = collector.collect(Path("/tmp"))
        self.assertEqual(result.tools["ruff"].status, "error")
        self.assertEqual(result.tools["bandit"].status, "error")
        self.assertEqual(result.tools["gitleaks"].status, "error")
        self.assertEqual(result.tools["pytest"].status, "not_run")

    def test_watch_changes_with_commit(self):
        self.assertNotEqual(fingerprint(context(), "m"), fingerprint(context(head_sha="c" * 40), "m"))
        self.assertEqual(fingerprint(context(), "m"), fingerprint(context(), "m"))

    def test_watch_changes_with_issue(self):
        self.assertNotEqual(fingerprint(context(), "m"), fingerprint(context(issue_description="Nouveau besoin"), "m"))


if __name__ == "__main__":
    unittest.main()
