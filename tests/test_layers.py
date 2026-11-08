"""1.3 checks: signature effects, form changes, parallel action lines, transitions and migration."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from test_combat_plan import make_craft_project, make_project, plan


def make_layered_project():
    """1.3：在 1.2 编舞要求之上登记签名特效、形态切换与转场（单动作线）。"""
    project = make_craft_project()
    project["schema_version"] = "1.3"
    project["assets"].append({"id": "hero_form", "kind": "character", "name": "覆鳞剑修",
                              "anchors": ["剑修稳定锚点", "剑身与右臂覆青鳞"], "states": [],
                              "image_prompt": "覆鳞剑修资产图"})
    project["shots"][2]["asset_ids"].append("hero_form")
    project["vfx"] = [{
        "id": "vfx_glint", "owner": "hero", "name": "剑锋冷光", "layer": "world", "scale": "body",
        "function": "标出接触点，并让缺口在光线断开处被看见",
        "look": "贴刃一线冷白光，缺口处断开",
        "lifecycle": {"omen": "刃根先亮", "release": "冷光沿刃推到剑尖", "contact": "光压进护臂铜片",
                      "residue": "铜片上留一道发白的划痕"},
        "spends": "剑修灵力外放，缺口侧光线断开说明此处不再承力",
        "route": "one_pass", "shot_ids": ["shot_1", "shot_2"],
    }]
    project["forms"] = [{
        "id": "form_scale", "actor": "hero", "from_asset": "hero", "to_asset": "hero_form",
        "beat_id": "beat_2", "shot_ids": ["shot_2"], "method": "occlusion",
        "ladder": ["右臂皮下透出青纹", "青雾从袖口涌出裹住半身", "雾散后剑身与右臂已覆青鳞"],
        "shared_anchors": ["剑修稳定锚点"], "cost_id": "cost_edge",
        "duration": "从雾散起维持到收势", "exit": "收势时鳞片褪回皮下，右臂脱力下垂",
    }]
    project["transitions"] = [
        {"id": "cut_lift", "from_shot": "shot_0", "to_shot": "shot_1", "method": "match_action", "layer": "post",
         "keeps": ["剑锋运动方向", "画面左右关系"], "changes": ["景别由全景进到近景"],
         "cut_condition": "剑尖刚越过画面中线时切", "route": "cut"},
        {"id": "cut_mist", "from_shot": "shot_2", "to_shot": "shot_3", "method": "occlusion", "layer": "world",
         "occluder": "断碑撞落扬起的石粉", "keeps": ["两人站位", "断碑位置"], "changes": ["机位绕到断碑另一侧"],
         "cut_condition": "石粉完全遮住画面时切", "route": "cut"},
    ]
    return project


def make_tracked_project():
    """1.3：世界线与内景线并行；决胜拍发生在内景，外层同时登记身体状态。"""
    project = make_craft_project()
    project["schema_version"] = "1.3"
    project["tracks"] = [
        {"id": "line_world", "kind": "world", "name": "石台", "time_relation": "成片时间即世界时间"},
        {"id": "line_inner", "kind": "inner", "name": "剑修识海",
         "time_relation": "识海中一念展开为一段对决，外层只过去一次呼吸"},
    ]
    for beat, line in zip(project["beats"], ("line_world", "line_inner", "line_world")):
        beat["track"] = line
    for shot, line in zip(project["shots"], ("line_world", "line_world", "line_inner", "line_world")):
        shot["track"] = line
    outer = "外层剑修双目紧闭，护臂仍抵在剑脊上，断碑已滑到身后"
    project["shots"][2]["outer_state"] = outer
    project["shots"][3]["opening_state"] = outer
    project["segments"][1]["opening_state"] = project["shots"][2]["opening_state"]
    return project


class LayeredTests(unittest.TestCase):
    def setUp(self):
        self.project = make_layered_project()
        self.tracked = make_tracked_project()

    def rejects(self, change, fragment, base=None):
        changed = copy.deepcopy(self.project if base is None else base)
        change(changed)
        errors = plan.validate(changed)
        self.assertTrue(any(fragment in error for error in errors), errors)

    def test_fixtures_pass(self):
        self.assertEqual([], plan.validate(self.project))
        self.assertEqual([], plan.validate(self.tracked))

    def test_older_versions_reject_layer_fields(self):
        for key in plan.LAYER_FIELDS:
            changed = make_craft_project()
            changed[key] = []
            self.assertTrue(any("仅 1.3 支持该字段" in x for x in plan.validate(changed)), key)
        self.rejects(lambda p: p["beats"][0].update(track="x"), "未知字段", make_craft_project())

    def test_vfx_rules(self):
        self.rejects(lambda p: p["vfx"][0].update(owner="nobody"), "特效必须有归属")
        self.rejects(lambda p: p["vfx"][0].update(layer="post"), "呈现层特效不进入世界")
        self.rejects(lambda p: p["vfx"][0]["lifecycle"].pop("residue"), "须写残留或消退")
        self.rejects(lambda p: p["vfx"][0]["lifecycle"].pop("release"), "缺少字段 release")
        self.rejects(lambda p: p["vfx"][0]["lifecycle"].update(peak="x"), "未知字段 peak")
        self.rejects(lambda p: p["vfx"][0].update(scale="cosmic"), "仅支持")
        self.rejects(lambda p: p["vfx"][0].update(route="asset"), "须引用已登记资产")
        self.rejects(lambda p: p["vfx"][0].update(asset_id="arena"), "仅 route 为 asset")
        self.rejects(lambda p: p["vfx"][0].update(look="冷光持续 2 秒"), "不得含阿拉伯数字秒码")
        self.rejects(lambda p: p["vfx"][0].update(look="冷光贴住 hero_form 的剑"), "不得含内部 ID")
        self.rejects(lambda p: p["vfx"][0].update(shot_ids=["shot_9"]), "未知镜头引用")
        changed = copy.deepcopy(self.project)
        changed["vfx"][0].update(route="asset", asset_id="late_prop")
        self.assertEqual([], plan.validate(changed))

    def test_form_rules(self):
        self.rejects(lambda p: p["beats"][1].update(marks=["adaptation"]), "须标 pivotal")
        self.rejects(lambda p: p["forms"][0].update(to_asset="hero"), "两套资产")
        self.rejects(lambda p: p["forms"][0].update(shared_anchors=["剑身与右臂覆青鳞"]), "逐字出现在前后两套资产")
        self.rejects(lambda p: p["forms"][0].update(ladder=["青纹", "落定"]), "至少写征兆")
        self.rejects(lambda p: p["forms"][0].update(cost_id="cost_arm"), "变身者本人支出")
        self.rejects(lambda p: p["forms"][0].update(cost_id="cost_none"), "变身须有代价")
        self.rejects(lambda p: p["shots"][2]["asset_ids"].remove("hero_form"), "同时登记前后两套资产")
        self.rejects(lambda p: p["forms"][0].update(shot_ids=["shot_1"]), "未引用变身节拍")
        self.rejects(lambda p: p["forms"][0].update(method="flash"), "仅支持")

        def morph_low(p):
            p["forms"][0]["method"] = "morph"
            p["shots"][2]["risk"] = "low"
            del p["shots"][2]["fallback"]
        self.rejects(morph_low, "连续形变难以保持身份")
        changed = copy.deepcopy(self.project)
        changed["forms"][0]["method"] = "morph"
        self.assertEqual([], plan.validate(changed))

    def test_transition_rules(self):
        self.rejects(lambda p: p["transitions"][0].update(to_shot="shot_2"), "相邻镜头")
        self.rejects(lambda p: p["transitions"][0].update(method="hard_cut"), "硬切是默认")
        self.rejects(lambda p: p["transitions"][1].pop("occluder"), "须写清遮挡物")
        self.rejects(lambda p: p["transitions"][0].update(occluder="烟"), "仅遮挡")
        self.rejects(lambda p: p["transitions"][0].update(route="bridge"), "首尾帧桥接不保证可用")
        self.rejects(lambda p: p["transitions"][1].update(cut_condition="第 10 秒切"), "不得含阿拉伯数字秒码")
        self.rejects(lambda p: p["transitions"][1].update(keeps=["shot_2 的站位"]), "不得含内部 ID")
        self.rejects(lambda p: p["transitions"][1].update(keeps=[]), "数组不能为空")

        def duplicate(p):
            extra = copy.deepcopy(p["transitions"][0])
            extra["id"] = "cut_again"
            p["transitions"].append(extra)
        self.rejects(duplicate, "同一切点只登记一种转场")

        def dense(p):
            extra = copy.deepcopy(p["transitions"][0])
            extra.update(id="cut_more", from_shot="shot_1", to_shot="shot_2")
            p["transitions"].append(extra)
        self.rejects(dense, "登记转场过密")

        def post_inside_form(p):
            p["forms"][0]["shot_ids"] = ["shot_2", "shot_3"]
            p["shots"][3]["asset_ids"].append("hero_form")
            p["shots"][3]["beat_ids"].insert(0, "beat_2")
            p["beats"][1]["end"] = 13
            p["beats"][2]["start"] = 13
            p["shots"][3]["execution"]["cues"] = [{"start": 12, "end": 16, "text": "雾散后收势"}]
            p["transitions"][1].update(layer="post")
        self.rejects(post_inside_form, "形态切换内部的遮挡须是世界内")

    def test_tracks_rules(self):
        base = self.tracked
        self.rejects(lambda p: p["tracks"][1].update(kind="world"), "恰好登记一条 world", base)
        self.rejects(lambda p: p.update(tracks=p["tracks"][:1]), "只有世界线时省略 tracks", base)
        self.rejects(lambda p: p["shots"][0].pop("track"), "每个镜头须归属", base)
        self.rejects(lambda p: p["beats"][0].pop("track"), "每个节拍须归属", base)
        self.rejects(lambda p: p["shots"][2].pop("outer_state"), "外界不暂停", base)
        self.rejects(lambda p: p["shots"][0].update(outer_state="x"), "不登记 outer_state", base)
        self.rejects(lambda p: p["shots"][3].update(opening_state="外层没有变化"), "outer_state 逐字一致", base)
        self.rejects(lambda p: p["beats"][1].update(track="line_world"), "不在同一动作线", base)
        self.rejects(lambda p: p["tracks"][1].update(time_relation="外层只过去 1 秒"), "不得含阿拉伯数字秒码", base)
        self.rejects(lambda p: p["tracks"][1].update(name="line_world 识海"), "不得含内部 ID", base)
        self.rejects(lambda p: p["shots"][0].update(track="line_world"), "未登记 tracks", self.project)
        self.rejects(lambda p: p["shots"][1].update(opening_state="漂移"), "与前镜 end_state 必须逐字一致", base)

        def post_cross(p):
            p["transitions"] = [{"id": "cut_in", "from_shot": "shot_1", "to_shot": "shot_2", "method": "ink_bleed",
                                 "layer": "post", "occluder": "墨色从瞳孔晕开", "keeps": ["剑修面容"],
                                 "changes": ["石台变为识海"], "cut_condition": "墨色铺满画面时切", "route": "composite"}]
        self.rejects(post_cross, "跨动作线的进出是世界内事件", base)
        changed = copy.deepcopy(base)
        post_cross(changed)
        changed["transitions"][0]["layer"] = "world"
        self.assertEqual([], plan.validate(changed))

    def test_render_layers(self):
        docs = plan.render(self.project)
        self.assertIn("剑锋冷光", docs["02-assets.md"])
        self.assertIn("形态切换", docs["01-design.md"])
        self.assertIn("遮挡转场", docs["03-storyboard.md"])
        video = docs["05-video-prompts.md"]
        self.assertIn("石粉完全遮住画面时切", video)
        self.assertIn("右臂皮下透出青纹 → 青雾从袖口涌出裹住半身", video)
        for key in ("cut_mist", "vfx_glint", "form_scale", "hero_form"):
            self.assertNotIn(key, video)
        tracked = plan.render(self.tracked)
        self.assertIn("同一时刻外层状态", tracked["03-storyboard.md"])
        self.assertIn("剑修识海", tracked["01-design.md"])
        self.assertIn("semantic_status: needs_review", tracked["06-review.md"])

    def test_render_no_doubled_punctuation(self):
        # 登记文本常以句号结尾，渲染器接自己的标点前须去掉，避免“。。”
        project = copy.deepcopy(self.project)
        project["style"] += "。"
        project["forms"][0]["ladder"] = [x + "。" for x in project["forms"][0]["ladder"]]
        project["transitions"][1]["keeps"] = [x + "。" for x in project["transitions"][1]["keeps"]]
        self.assertEqual([], plan.validate(project))
        for name, text in plan.render(project).items():
            for pair in ("。。", "。；", "；。"):
                self.assertNotIn(pair, text, name)
        for path in sorted(Path(__file__).resolve().parents[1].glob("examples/*/0*.md")):
            for pair in ("。。", "。；", "；。"):
                self.assertNotIn(pair, path.read_text(encoding="utf-8"), str(path))

    def test_migrate(self):
        migrated, todo = plan.migrate(make_craft_project())
        self.assertEqual("1.3", migrated["schema_version"])
        self.assertEqual([], plan.validate(migrated))
        self.assertEqual(list(plan.MIGRATION_TODO), todo)
        for key in plan.LAYER_FIELDS:
            self.assertNotIn(key, migrated)
        for source in (make_project(), self.project):
            with self.assertRaises(ValueError):
                plan.migrate(source)
        broken = make_craft_project()
        broken["shots"][0]["light"] = ""
        with self.assertRaises(ValueError):
            plan.migrate(broken)

    def test_migrate_cli_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "old.json"
            source.write_text(json.dumps(make_craft_project(), ensure_ascii=False), encoding="utf-8")
            target = Path(tmp) / "new.json"
            with mock.patch("sys.stdout"):
                self.assertEqual(0, plan.main(["migrate", str(source), "--out", str(target)]))
                self.assertEqual("1.3", plan.load_project(target)["schema_version"])
                self.assertEqual(1, plan.main(["migrate", str(source), "--out", str(target)]))
                self.assertEqual(1, plan.main(["migrate", str(source), "--out", str(source)]))
            self.assertEqual("1.2", plan.load_project(source)["schema_version"])


if __name__ == "__main__":
    unittest.main()
