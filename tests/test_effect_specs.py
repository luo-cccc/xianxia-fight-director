"""1.3 effect relations and immutable legacy input/output regression checks."""

import copy
import hashlib
import json
import unittest

from test_combat_plan import ROOT, make_craft_project, plan


def make_effect_project():
    project = make_craft_project()
    project["schema_version"] = "1.3"
    project["effect_specs"] = [{
        "id": "fx_guard", "name": "受压薄膜", "families": ["柔体形变型", "光学扭曲型"],
        "applications": ["防御、偏转与卸力"], "reality": "world",
        "asset_ids": ["hero", "opponent"], "summary": "薄膜受压凹陷，背景沿接点弯曲；结束后保留护臂变形。",
        "stages": [{"name": "接触并持续承力", "start": 0, "end": 8,
                    "beat_ids": ["beat_open"], "keyframe_ids": ["frame_0", "frame_1", "frame_handoff"]}],
    }]
    for i, shot in enumerate(project["shots"]):
        shot["effect_ids"] = ["fx_guard"] if i < 2 else []
    return project


class CompatibilityTests(unittest.TestCase):
    def test_frozen_inputs_and_all_seven_outputs_remain_unchanged(self):
        base = ROOT / "tests/fixtures/compat"
        manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(40, len(manifest["files"]))
        for name, digest in manifest["files"].items():
            self.assertEqual(digest, hashlib.sha256((base / name).read_bytes()).hexdigest(), name)
        inputs = sorted(base.glob("*/*/input.json"))
        self.assertEqual(5, len(inputs))
        for source in inputs:
            with self.subTest(source=str(source.relative_to(base))):
                project = plan.load_project(source)
                self.assertEqual([], plan.validate(project))
                docs = plan.render(project)
                expected = source.parent / "expected"
                self.assertEqual(set(docs), {p.name for p in expected.iterdir()})
                for name, content in docs.items():
                    self.assertEqual((expected / name).read_text(encoding="utf-8"), content, name)

    def test_older_versions_reject_new_fields(self):
        for version in ("1.1", "1.2"):
            project = make_craft_project() if version == "1.2" else plan.load_project(
                ROOT / "tests/fixtures/compat/1.1/minimal-battle/input.json")
            for change in (lambda p: p.update(effect_specs=[]), lambda p: p["shots"][0].update(effect_ids=[])):
                changed = copy.deepcopy(project)
                change(changed)
                self.assertTrue(any("未知字段" in e for e in plan.validate(changed)))


class EffectTests(unittest.TestCase):
    def setUp(self):
        self.project = make_effect_project()

    def rejects(self, change, fragment):
        changed = copy.deepcopy(self.project)
        change(changed)
        errors = plan.validate(changed)
        self.assertTrue(any(fragment in e for e in errors), errors)

    def test_valid_effect_has_director_and_frame_links_without_prompt_injection(self):
        self.assertEqual([], plan.validate(self.project))
        docs = plan.render(self.project)
        self.assertEqual(7, len(docs))
        self.assertIn("fx_guard · 受压薄膜", docs["03-storyboard.md"])
        self.assertIn("柔体形变型、光学扭曲型", docs["03-storyboard.md"])
        self.assertIn("受压薄膜／接触并持续承力", docs["04-keyframes.md"])
        self.assertIn("影响镜头 shot_0, shot_1", docs["06-review.md"])
        video = docs["05-video-prompts.md"]
        for text in ("fx_guard", self.project["effect_specs"][0]["summary"], "世界实效", "stages"):
            self.assertNotIn(text, video)
        old = make_craft_project()
        self.assertEqual(plan.render(old)["05-video-prompts.md"], video)
        self.assertEqual(self.project, json.loads(docs["project.json"]))

    def test_no_major_effects_and_open_tags_are_accepted(self):
        project = copy.deepcopy(self.project)
        project["effect_specs"] = []
        for shot in project["shots"]:
            shot["effect_ids"] = []
        self.assertEqual([], plan.validate(project))
        self.project["effect_specs"][0]["families"] = ["新创的视觉类型"]
        self.project["effect_specs"][0]["applications"] = ["独特任务用途"]
        self.assertEqual([], plan.validate(self.project))

    def test_storyboard_links_review_without_duplicating_it(self):
        self.project["review"]["verification"] = "仅审阅文件持有的验证说明"
        docs = plan.render(self.project)
        self.assertIn("[检查与承接](06-review.md)", docs["03-storyboard.md"])
        self.assertNotIn("仅审阅文件持有的验证说明", docs["03-storyboard.md"])
        self.assertIn("仅审阅文件持有的验证说明", docs["06-review.md"])
        self.assertEqual(7, len(docs))

    def test_one_three_inherits_every_craft_requirement(self):
        for mark in plan.MARKS:
            changed = copy.deepcopy(self.project)
            for beat in changed["beats"]:
                marks = [m for m in beat.get("marks", []) if m != mark]
                if marks:
                    beat["marks"] = marks
                else:
                    beat.pop("marks", None)
            self.assertTrue(any("缺少 " + mark in e for e in plan.validate(changed)))
        self.rejects(lambda p: p.update(cost=[]), "代价账目")
        self.rejects(lambda p: p["scene"].update(attrition=[]), "累积痕迹")
        self.rejects(lambda p: p["shots"][0].pop("light"), "缺少字段 light")
        self.rejects(lambda p: p.update(keyframes=[f for f in p["keyframes"] if f["role"] != "prep"]), "缺少 prep")

    def test_required_new_fields_and_strict_object_fields(self):
        self.rejects(lambda p: p.pop("effect_specs"), "缺少字段 effect_specs")
        self.rejects(lambda p: p["shots"][0].pop("effect_ids"), "缺少字段 effect_ids")
        self.rejects(lambda p: p["effect_specs"][0].update(production={}), "未知字段 production")
        self.rejects(lambda p: p["effect_specs"][0]["stages"][0].update(prompt="第二份提示词"), "未知字段 prompt")
        self.rejects(lambda p: p["effect_specs"][0].update(generation={"prompt": "第二份提示词"}), "未知字段 generation")

    def test_one_three_cannot_bypass_remaining_craft_relations(self):
        def no_handoff(p):
            p["keyframes"] = [f for f in p["keyframes"] if f["role"] != "handoff"]
            p["effect_specs"][0]["stages"][0]["keyframe_ids"].remove("frame_handoff")
        def no_irreversible(p):
            for entry in p["cost"]:
                entry["irreversible"] = False
        def same_light(p):
            for shot in p["shots"]:
                shot["light"] = "同一环境光"
        def reversed_turn_frames(p):
            prep = next(f for f in p["keyframes"] if f["role"] == "prep")
            result = next(f for f in p["keyframes"] if f["role"] == "result")
            prep["time_sec"], result["time_sec"] = result["time_sec"], prep["time_sec"]
        cases = [
            (no_handoff, "段界缺少 handoff"),
            (no_irreversible, "至少一项不可逆"),
            (same_light, "全场光照登记完全相同"),
            (reversed_turn_frames, "时刻须严格递增"),
            (lambda p: p["cost"][1].update(owner="hero"), "代价集中在同一方"),
            (lambda p: p["knowledge"][0].update(truth=p["knowledge"][0]["belief"]), "即无信息差"),
            (lambda p: p["shots"][2].pop("fallback"), "高风险镜头须预授权"),
            (lambda p: p["beats"][1].update(marks=["pivotal", "adaptation", "breath"]), "呼吸拍不能同时"),
        ]
        for change, fragment in cases:
            with self.subTest(fragment=fragment):
                self.rejects(change, fragment)

    def test_identifiers_are_global_and_prefixed(self):
        self.rejects(lambda p: p["effect_specs"][0].update(id="p1"), "须以 fx_")
        def duplicate(p):
            p["assets"].append({"id": "fx_guard", "kind": "prop", "name": "额外器物",
                                "anchors": ["额外器物"], "states": [], "image_prompt": "器物静图"})
        self.rejects(duplicate, "ID全场重复")
        self.rejects(lambda p: p["effect_specs"].append(copy.deepcopy(p["effect_specs"][0])), "ID全场重复")

    def test_lists_reality_and_references_are_checked(self):
        for field in ("families", "applications", "stages"):
            self.rejects(lambda p, f=field: p["effect_specs"][0].update({f: []}), "不能为空" if field != "stages" else "非空阶段")
        self.rejects(lambda p: p["effect_specs"][0].update(reality="mixed"), "仅支持 world")
        self.rejects(lambda p: p["effect_specs"][0].update(asset_ids=["missing"]), "未知引用 missing")
        self.rejects(lambda p: p["shots"][0].update(effect_ids=["missing"]), "未知引用 missing")
        self.rejects(lambda p: p["shots"][0].update(effect_ids=["fx_guard", "fx_guard"]), "引用不得重复")
        self.rejects(lambda p: p["effect_specs"][0]["stages"][0].update(beat_ids=[]), "数组不能为空")
        self.rejects(lambda p: p["effect_specs"][0]["stages"][0].update(keyframe_ids=["missing"]), "未知引用 missing")

    def test_bad_shapes_and_numbers_report_errors_without_crashing(self):
        for value in (None, {}, "bad", True):
            self.rejects(lambda p, v=value: p.update(effect_specs=v), "对象数组")
        for value in (None, [], "bad", True, float("nan"), float("inf"), 10**1000):
            self.rejects(lambda p, v=value: p["effect_specs"][0]["stages"][0].update(start=v), "有限数字")
        mutations = [
            lambda p: p["effect_specs"].__setitem__(0, None),
            lambda p: p["effect_specs"][0].update(id=[]),
            lambda p: p["effect_specs"][0].update(reality={}),
            lambda p: p["effect_specs"][0].update(families=[{}]),
            lambda p: p["effect_specs"][0].update(stages=[None]),
            lambda p: p["effect_specs"][0]["stages"][0].update(beat_ids=[{}]),
            lambda p: p["shots"][0].update(effect_ids=[{}]),
            lambda p: p["effect_specs"][0].update(transitions=[None]),
            lambda p: p["effect_specs"][0].update(transformation={"subject_asset_id": [], "invariants": [], "allowed_changes": []}),
        ]
        for change in mutations:
            changed = copy.deepcopy(self.project)
            change(changed)
            self.assertTrue(plan.validate(changed))

    def test_stage_windows_and_full_shot_coverage(self):
        self.rejects(lambda p: p["effect_specs"][0]["stages"][0].update(end=0), "阶段时间")
        self.rejects(lambda p: p["effect_specs"][0]["stages"][0].update(end=17), "阶段时间")
        self.rejects(lambda p: p["shots"][0].update(effect_ids=[]), "未完整覆盖效果阶段")
        self.rejects(lambda p: p["shots"][2].update(effect_ids=["fx_guard"]), "没有正时长阶段交集")
        def unused(p):
            for shot in p["shots"]:
                shot["effect_ids"] = []
        self.rejects(unused, "未被任何镜头引用")

    def test_malformed_segment_boundary_reference_does_not_crash(self):
        for version in ("1.2", "1.3"):
            base = make_craft_project() if version == "1.2" else self.project
            for value in ({}, [], None, 7):
                with self.subTest(version=version, value=value):
                    changed = copy.deepcopy(base)
                    changed["segments"][0]["shot_ids"][-1] = value
                    self.assertTrue(plan.validate(changed))

    def test_stage_beat_relation_and_frame_time_binding(self):
        self.rejects(lambda p: p["effect_specs"][0]["stages"][0].update(beat_ids=["beat_2"]), "阶段与节拍没有正时长交集")
        self.rejects(lambda p: p["effect_specs"][0]["stages"][0].update(keyframe_ids=["frame_contact"]), "关键帧时刻不在本阶段")
        self.rejects(lambda p: p["shots"][1].update(effect_ids=[]), "关键帧所属镜头未登记本效果")

    def test_mid_shot_stage_edges_require_cue_edges(self):
        def shift(p):
            p["effect_specs"][0]["stages"][0].update(start=1, keyframe_ids=["frame_1"])
        self.rejects(shift, "cue 边界对齐")
        project = copy.deepcopy(self.project)
        shift(project)
        project["shots"][0]["execution"]["cues"] = [
            {"start": 0, "end": 1, "text": "薄膜尚未建立，人物继续对峙"},
            {"start": 1, "end": 4, "text": "薄膜从掌前展开，剑锋接触并压出凹面"},
        ]
        self.assertEqual([], plan.validate(project))

    def test_parallel_stages_and_optional_frame_references(self):
        self.project["effect_specs"][0]["stages"].append({
            "name": "边缘仍在展开", "start": 4, "end": 8,
            "beat_ids": ["beat_open"], "keyframe_ids": [],
        })
        self.assertEqual([], plan.validate(self.project))

    def test_subjective_editorial_and_unbound_assets(self):
        for reality in ("subjective", "editorial"):
            self.project["effect_specs"][0]["reality"] = reality
            self.project["effect_specs"][0]["asset_ids"] = []
            self.assertEqual([], plan.validate(self.project))
        # An overall effect may mention a later asset without injecting it into early prompts.
        self.project["effect_specs"][0]["asset_ids"] = ["late_prop"]
        self.assertEqual([], plan.validate(self.project))
        video = plan.render(self.project)["05-video-prompts.md"].split("## 制作段 2")[0]
        self.assertNotIn("断碑", video)

    def transition(self, source="shot_0", target="shot_1"):
        return {"from_shot_id": source, "to_shot_id": target, "method": "薄膜遮蔽",
                "out_condition": "薄膜折射覆盖接点附近画面，人物保持承力",
                "in_condition": "同一薄膜继续下凹，手和剑没有重新起手"}

    def test_multiple_effect_transitions_and_director_only_export(self):
        effect = self.project["effect_specs"][0]
        effect["stages"].append({"name": "变形继续", "start": 8, "end": 12,
                                 "beat_ids": ["beat_2"], "keyframe_ids": []})
        self.project["shots"][2]["effect_ids"] = ["fx_guard"]
        effect["transitions"] = [self.transition(), self.transition("shot_1", "shot_2")]
        self.assertEqual([], plan.validate(self.project))
        docs = plan.render(self.project)
        self.assertIn("shot_1 → shot_2", docs["03-storyboard.md"])
        self.assertNotIn(effect["transitions"][0]["out_condition"], docs["05-video-prompts.md"])

    def test_transition_must_be_adjacent_unique_bound_and_at_cut(self):
        self.project["effect_specs"][0]["transitions"] = [self.transition()]
        self.rejects(lambda p: p["effect_specs"][0]["transitions"][0].update(to_shot_id="shot_2"), "按序相邻")
        self.rejects(lambda p: p["effect_specs"][0]["transitions"].append(self.transition()), "不得重复")
        self.rejects(lambda p: p["effect_specs"][0]["transitions"][0].update(from_shot_id="missing"), "未知镜头引用")
        self.rejects(lambda p: p["effect_specs"][0]["transitions"][0].update(out_condition=""), "非空字符串")
        self.rejects(lambda p: p["effect_specs"][0].update(transitions=[]), "非空转场")
        def no_cut(p):
            p["effect_specs"][0]["stages"] = [
                {"name": "离切点较远", "start": 0, "end": 2, "beat_ids": ["beat_open"], "keyframe_ids": []},
                {"name": "后来重现", "start": 6, "end": 8, "beat_ids": ["beat_open"], "keyframe_ids": []},
            ]
            for shot, split in ((p["shots"][0], 2), (p["shots"][1], 6)):
                shot["execution"]["cues"] = [{"start": shot["start"], "end": split, "text": "前一阶段"},
                                               {"start": split, "end": shot["end"], "text": "后一阶段"}]
        self.rejects(no_cut, "须覆盖切点两侧")

    def test_transformation_accepts_character_prop_and_scene(self):
        for subject in ("hero", "late_prop", "arena"):
            effect = self.project["effect_specs"][0]
            effect["asset_ids"] = [subject]
            effect["transformation"] = {"subject_asset_id": subject,
                                         "invariants": ["既有损伤与位置连续"],
                                         "allowed_changes": ["外层逐步结晶"]}
            self.assertEqual([], plan.validate(self.project))
        self.rejects(lambda p: p["effect_specs"][0]["transformation"].update(subject_asset_id="missing"), "未知资产引用")
        self.rejects(lambda p: p["effect_specs"][0]["transformation"].update(invariants=[]), "数组不能为空")
        self.rejects(lambda p: p["effect_specs"][0]["transformation"].update(subject_asset_id="hero"), "须列入本效果")

    def test_effect_id_cannot_leak_through_any_copyable_asset_or_prompt(self):
        self.rejects(lambda p: p["shots"][0]["execution"].update(effects="保持 fx_guard 的效果"), "不得含内部 ID fx_guard")
        self.rejects(lambda p: p["keyframes"][0].update(prompt="fx_guard 的接点静图"), "不得含内部 ID fx_guard")
        self.rejects(lambda p: p["assets"][0].update(anchors=["参照 fx_guard"]), "不得含内部 ID fx_guard")
        self.rejects(lambda p: p["assets"][0].update(name="fx_guard 的石台"), "不得含内部 ID fx_guard")
        self.rejects(lambda p: p["assets"][0].update(reference={"source": "图A", "control": "fx_guard", "keep": "器形", "exclude": "原背景"}), "不得含内部 ID fx_guard")


if __name__ == "__main__":
    unittest.main()
