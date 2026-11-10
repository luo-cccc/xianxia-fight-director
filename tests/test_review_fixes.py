"""Regressions for the 1.4 review: crash paths, ID/timecode scanning and CLI behaviour."""

import copy
import io
import json
import unittest
from unittest import mock

from test_combat_plan import make_craft_project, plan
from test_layers import make_layered_project, make_tracked_project


def errors_of(project, change):
    changed = copy.deepcopy(project)
    change(changed)
    return plan.validate(changed)


class ReviewFixTests(unittest.TestCase):
    def setUp(self):
        self.project = make_craft_project()
        self.layered = make_layered_project()

    def assert_rejects(self, project, change, fragment):
        errors = errors_of(project, change)
        self.assertTrue(any(fragment in x for x in errors), errors)

    def test_unhashable_boundary_shot_ids_do_not_crash(self):
        for bad in (["x"], {"k": 1}):
            with self.subTest(bad=bad):
                errors = errors_of(self.project, lambda p, b=bad: p["segments"][0]["shot_ids"].append(b))
                self.assertTrue(errors)

    def test_short_ids_are_scanned_on_token_boundaries(self):
        def rename(p, old, new):
            text = json.dumps(p, ensure_ascii=False).replace(f'"{old}"', f'"{new}"')
            return json.loads(text)

        short = rename(self.project, "hero", "B03")
        self.assertEqual([], plan.validate(short))
        self.assert_rejects(short, lambda p: p["segments"][0].update(prompt_context="依赖 B03 的结果"), "不得含内部 ID B03")
        # 普通词里的子串不是 ID：hero 不应命中 heroic
        self.assertEqual([], errors_of(self.project, lambda p: p["segments"][0].update(prompt_context="一记 heroic 的突刺")))

    def test_ratio_is_not_a_timecode_but_full_width_seconds_are(self):
        self.assertEqual([], errors_of(self.project, lambda p: p["segments"][0].update(prompt_context="画幅16:9，备用4:3")))
        for value in ("推压２２秒", "到０:１２撤步", "到0:12撤步", "01:02:03收势"):
            with self.subTest(value=value):
                self.assert_rejects(self.project, lambda p, v=value: p["segments"][0].update(prompt_context=v), "不得含阿拉伯数字秒码")

    def test_layer_names_and_printed_asset_text_are_checked(self):
        self.assert_rejects(self.layered, lambda p: p["vfx"][0].update(name="冷光22秒"), "不得含阿拉伯数字秒码")
        tracked = make_tracked_project()
        self.assert_rejects(tracked, lambda p: p["tracks"][0].update(name="世界线0:12"), "不得含阿拉伯数字秒码")
        self.assert_rejects(self.project, lambda p: p["assets"][1]["anchors"].append("出场22秒后换衣"), "资产文本不得含")
        self.assert_rejects(self.project, lambda p: p["assets"][1]["anchors"].append("佩剑同 opponent"), "不得含内部 ID opponent")
        self.assert_rejects(self.layered, lambda p: p["forms"][0]["shared_anchors"].append("同 shot_0 的剑修"), "不得含内部 ID")

    def test_extra_handoff_frames_are_allowed(self):
        def add(p):
            extra = copy.deepcopy(next(x for x in p["keyframes"] if x["role"] == "handoff"))
            extra.update(id="frame_handoff_next", shot_id="shot_2", time_sec=8)
            p["keyframes"].append(extra)
        self.assertEqual([], errors_of(self.project, add))

    def test_pivotal_order_is_strict_across_all_frames_of_a_role(self):
        def late_prep(p):
            extra = copy.deepcopy(next(x for x in p["keyframes"] if x["role"] == "prep"))
            extra.update(id="frame_prep_late", time_sec=10.5)
            p["keyframes"].append(extra)
        self.assert_rejects(self.project, late_prep, "时刻须严格递增")

    def test_bad_version_and_bad_cue_do_not_cascade(self):
        self.assertEqual(1, len(errors_of(self.project, lambda p: p.update(schema_version="9.9"))))
        errors = errors_of(self.project, lambda p: p["shots"][0]["execution"]["cues"][0].update(start="x"))
        self.assertFalse(any("连续覆盖" in x for x in errors), errors)

    def test_render_fixes(self):
        docs = plan.render(self.layered)
        video, board = docs["05-video-prompts.md"], docs["03-storyboard.md"]
        self.assertIn("征兆：刃根先亮", video)
        self.assertIn("残留：铜片上留一道发白的划痕", video)
        self.assertNotIn("\n# 检查与承接", board)
        self.assertIn("\n### 制作段接点", board)
        self.assertNotIn("之间的转场至下一镜", video)
        self.assertEqual("0", plan._time(-0.0000001))

    def test_migrate_command_is_gone(self):
        self.assertFalse(hasattr(plan, "migrate"))
        with mock.patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                plan.main(["migrate", "missing.json"])
            self.assertEqual(2, caught.exception.code)

    def test_argument_errors_exit_two_before_loading(self):
        with mock.patch("sys.stderr", io.StringIO()):
            for argv in (["export", "missing.json"], ["validate", "missing.json", "--out", "x"]):
                with self.subTest(argv=argv), self.assertRaises(SystemExit) as caught:
                    plan.main(argv)
                self.assertEqual(2, caught.exception.code)


if __name__ == "__main__":
    unittest.main()
