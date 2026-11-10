"""Keep the v2.0 single-arm behavior trial valid and its exported bundle current."""

from pathlib import Path
import unittest

from test_combat_plan import plan

ROOT = Path(__file__).resolve().parents[1]


class BehaviorV20Tests(unittest.TestCase):
    def test_trial_project_and_bundle(self):
        project = plan.load_project(ROOT / "tests" / "behavior" / "v2.0" / "project.json")
        self.assertEqual([], plan.validate(project))
        docs = plan.render(project)
        self.assertEqual(7, len(docs))
        bundle = ROOT / "tests" / "behavior" / "v2.0" / "bundle"
        for name, content in docs.items():
            self.assertEqual(content, (bundle / name).read_text(encoding="utf-8"), name)


if __name__ == "__main__":
    unittest.main()
