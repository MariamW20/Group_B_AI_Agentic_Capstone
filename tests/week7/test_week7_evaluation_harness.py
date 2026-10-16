import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "evidence" / "demo" / "centenary-agent-week6" / "week7_evaluation_harness.py"


spec = importlib.util.spec_from_file_location("week7_evaluation_harness", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Week7EvaluationHarnessTests(unittest.TestCase):
    def test_build_week7_scenarios_returns_30_scenarios(self):
        scenarios = module.build_week7_scenarios()
        self.assertEqual(len(scenarios), 30)
        for scenario in scenarios:
            self.assertIn("scenario_id", scenario)
            self.assertIn("category", scenario)
            self.assertIn("expected_result", scenario)
            self.assertIn("request", scenario)
            self.assertIn("session", scenario)
            self.assertIn("planner_script", scenario)
            self.assertIn("tool", scenario)

    def test_run_week7_evaluation_writes_complete_observability_bundle(self):
        output_dir = Path(__file__).resolve().parents[2] / "evidence" / "traces" / "week7"
        result = module.run_week7_evaluation(output_dir=output_dir)
        self.assertEqual(len(result), 30)
        self.assertTrue((output_dir / "week7-observability-evidence.json").exists())
        for item in result:
            self.assertIn("terminal_outcome", item)
            self.assertIn("scenario_id", item)
            self.assertIn("events", item)
            self.assertGreaterEqual(len(item["events"]), 1)
            self.assertIn("event", item["events"][0])


if __name__ == "__main__":
    unittest.main()
