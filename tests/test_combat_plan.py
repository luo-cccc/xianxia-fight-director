"""Structural and export regression checks, using original example plans."""

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("combat_plan", ROOT / "scripts" / "combat_plan.py")
plan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plan)


def make_project():
    """A small 1.1 plan independent of concurrently edited example files."""
    assets = [
        {"id": key, "kind": kind, "name": name, "anchors": [name + "稳定锚点"],
         "states": [], "image_prompt": name + "资产图"}
        for key, kind, name in (("arena", "scene", "石台"), ("hero", "character", "剑修"),
                                ("opponent", "character", "体修"), ("late_prop", "prop", "断碑"))
    ]
    states = ["双方隔台对峙", "剑锋压住护臂", "双方僵持于台缘", "断碑挡住退路", "双方收势分开"]
    execution_states = ["剑修与体修隔台站定", "剑尖抵住抬起的护臂", "护臂仍抵剑锋，双脚贴近台缘", "断碑横在两人身后", "两人各退一步收势"]
    shots = []
    frames = []
    for i in range(4):
        asset_ids = ["arena", "hero", "opponent"] + (["late_prop"] if i >= 2 else [])
        shots.append({
            "id": f"shot_{i}", "start": i * 4, "end": (i + 1) * 4,
            "beat_ids": ["beat_open" if i < 2 else f"beat_{i}"], "asset_ids": asset_ids,
            "opening_state": states[i], "end_state": states[i + 1],
            "camera": "原稿机位", "effects": "原稿特效", "sound": "原稿声音",
            "execution": {"opening_state": execution_states[i], "end_state": execution_states[i + 1],
                          "camera": "侧面中景缓推", "effects": "剑锋微光贴住接触点", "sound": "金属摩擦与足底擦地",
                          "cues": [{"start": i * 4, "end": (i + 1) * 4, "text": f"本镜窗口动作{i}，维持已有接触相位"}]},
        })
        frames.append({"id": f"frame_{i}", "shot_id": f"shot_{i}", "time_sec": i * 4,
                       "asset_ids": asset_ids[:], "state": states[i], "prompt": "接触点清晰的静图"})
    return {
        "schema_version": "1.1", "title": "结构测试战斗", "duration_sec": 16, "aspect_ratio": "16:9", "style": "写实仙侠",
        "assumptions": ["测试补充假设"], "constraints": ["测试硬约束"],
        "design": {"goals": ["剑修要逼退体修夺取通路", "体修要守住通路保护身后阵眼"],
                   "rules": ["测试全场规则"], "turns": ["接触后改变受力"], "outcome": "全场结局专用文本",
                   "viewing_tasks": ["观看任务专用文本"]},
        "assets": assets, "scene": {"asset_id": "arena", "geography": "全场地理专用文本"},
        "beats": [
            {"id": "beat_open", "start": 0, "end": 8, "actors": ["hero", "opponent"],
             "action": "旧过程从拔剑起手持续推压", "response": "体修抬臂承力", "result": "剑臂相抵到台缘", "requires": []},
            {"id": "beat_2", "start": 8, "end": 12, "actors": ["hero", "opponent"],
             "action": "断碑滑入后方", "response": "双方收脚避让", "result": "退路被挡", "requires": ["beat_open"]},
            {"id": "beat_3", "start": 12, "end": 16, "actors": ["hero", "opponent"],
             "action": "双方撤力", "response": "各退一步", "result": "收势", "requires": ["beat_2"]},
        ],
        "shots": shots,
        "segments": [
            {"id": "segment_open", "shot_ids": ["shot_0", "shot_1"], "opening_state": states[0], "closing_state": states[2],
             "prompt_context": "石台平坦，剑锋与护臂接触后持续承力"},
            {"id": "segment_close", "shot_ids": ["shot_2", "shot_3"], "opening_state": states[2], "closing_state": states[4],
             "prompt_context": "台缘有滑入的断碑，两人须先腾出落脚处"},
        ],
        "keyframes": frames,
        "review": {"scope": "作者审阅本场动作", "fixed": ["已校正承力"], "pending": ["检查成片接触点"],
                   "invalidated": [], "verification": "作者原样登记的验证范围；含未解决疑点"},
    }


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.project = make_project()

    def rejects(self, change, fragment):
        changed = copy.deepcopy(self.project)
        change(changed)
        self.assertTrue(any(fragment in error for error in plan.validate(changed)), plan.validate(changed))

    def test_all_examples_and_render(self):
        examples = sorted((ROOT / "examples").glob("*.json"))
        self.assertEqual(3, len(examples))
        for path in examples:
            with self.subTest(example=path.name):
                project = plan.load_project(path)
                self.assertEqual([], plan.validate(project))
                docs = plan.render(project)
                self.assertEqual(7, len(docs))
                self.assertEqual(project, json.loads(docs["project.json"]))
                video = docs["05-video-prompts.md"]
                self.assertEqual(len(project["segments"]), video.count("本段起态："))
                shots = {shot["id"]: shot for shot in project["shots"]}
                for segment in project["segments"]:
                    self.assertIn(shots[segment["shot_ids"][0]]["execution"]["opening_state"], video)
                    self.assertIn(shots[segment["shot_ids"][-1]]["execution"]["end_state"], video)
                    self.assertIn(segment["prompt_context"], video)
                self.assertIn("semantic_status: needs_review", docs["06-review.md"])
                for beat in project["beats"]:
                    self.assertIn(beat["action"], docs["03-storyboard.md"])
                for shot in project["shots"]:
                    for cue in shot["execution"]["cues"]:
                        self.assertIn(cue["text"], video)

    def test_duplicate_keys_and_constants(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            for text in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    plan.load_project(path)

    def test_non_object_and_missing(self):
        for value in ([], None, {}, {"title": "x"}):
            self.assertTrue(plan.validate(value))

    def test_unknown_fields(self):
        self.rejects(lambda p: p.update(typo=1), "未知字段")
        self.rejects(lambda p: p["assets"][0].update(typo=1), "未知字段")

    def test_invalid_numbers(self):
        for value in (True, float("nan"), float("inf"), -1, 0, 10**1000):
            self.rejects(lambda p: p.update(duration_sec=value), "duration_sec")
        self.rejects(lambda p: p["keyframes"][0].update(time_sec=False), "time_sec")

    def test_duplicate_id_and_reference(self):
        self.rejects(lambda p: p["shots"][0].update(id=p["assets"][0]["id"]), "ID全场重复")
        self.rejects(lambda p: p["shots"][0]["asset_ids"].append("missing"), "未知引用")
        self.rejects(lambda p: p["beats"][0].update(actors=[p["scene"]["asset_id"]]), "主体类型")
        self.rejects(lambda p: p["shots"][0]["asset_ids"].append(p["shots"][0]["asset_ids"][0]), "引用不得重复")

    def test_malformed_values_do_not_crash(self):
        mutations = [
            lambda p: p["assets"][0].update(id=[]),
            lambda p: p["assets"][0].update(kind={}),
            lambda p: p["shots"][0].update(beat_ids=[{}]),
            lambda p: p["shots"][0].update(asset_ids=None),
            lambda p: p["beats"][0].update(requires=[[]]),
            lambda p: p["segments"][0].update(shot_ids=[{}]),
            lambda p: p["keyframes"][0].update(shot_id=[]),
        ]
        for change in mutations:
            changed = copy.deepcopy(self.project)
            change(changed)
            self.assertTrue(plan.validate(changed))

    def test_timeline_gaps_overlap_and_end(self):
        self.rejects(lambda p: p["shots"][1].update(start=p["shots"][1]["start"] + 0.1), "时间轴")
        self.rejects(lambda p: p["shots"][1].update(start=p["shots"][1]["start"] - 0.1), "时间轴")
        self.rejects(lambda p: p["shots"][-1].update(end=p["duration_sec"] - 1), "覆盖到总时长")

    def test_beats_need_coverage_and_ready_dependencies(self):
        self.rejects(lambda p: p["beats"][0].update(requires=[p["beats"][-1]["id"]]), "尚未完成")
        self.rejects(lambda p: p["beats"][0].update(requires=[p["beats"][0]["id"]]), "自依赖")
        self.rejects(lambda p: p["beats"][0].update(end=p["duration_sec"]), "未完整覆盖")

    def test_parallel_beats_and_cross_shot_coverage(self):
        changed = copy.deepcopy(self.project)
        other = copy.deepcopy(changed["beats"][0])
        other["id"] = "parallel_test"
        other["requires"] = []
        changed["beats"].append(other)
        for shot in changed["shots"]:
            if changed["beats"][0]["id"] in shot["beat_ids"]:
                shot["beat_ids"].append(other["id"])
        self.assertEqual([], plan.validate(changed))
        changed = copy.deepcopy(self.project)
        beat = changed["beats"][0]
        beat["start"] = 0
        beat["end"] = changed["shots"][1]["end"]
        for item in changed["beats"]:
            item["requires"] = []
        for shot in changed["shots"][:2]:
            if beat["id"] not in shot["beat_ids"]:
                shot["beat_ids"].append(beat["id"])
        self.assertEqual([], plan.validate(changed))
        self.assertIn("此拍跨镜", plan.render(changed)["03-storyboard.md"])
        self.assertNotIn("此拍跨镜", plan.render(changed)["05-video-prompts.md"])

    def test_segment_mapping_and_handoff(self):
        self.rejects(lambda p: p["segments"][0].update(opening_state="错误"), "首镜起态")
        self.rejects(lambda p: p["segments"][1].update(opening_state="错误"), "前段终态")
        self.rejects(lambda p: p["segments"][0]["shot_ids"].reverse(), "恰好分配")

    def test_keyframe_bounds_assets_and_presence(self):
        self.rejects(lambda p: p["keyframes"][0].update(time_sec=p["duration_sec"] + 1), "超出所属镜头")
        first_shot = self.project["shots"][0]["id"]
        self.rejects(lambda p: p.update(keyframes=[x for x in p["keyframes"] if x["shot_id"] != first_shot]), "缺少关键帧")
        p = copy.deepcopy(self.project)
        p["keyframes"][0]["time_sec"] = p["shots"][0]["end"]
        self.assertEqual([], plan.validate(p))

    def test_export_new_directory_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "bundle"
            plan.export_bundle(self.project, target)
            before = {p.name: p.read_bytes() for p in target.iterdir()}
            self.assertEqual(7, len(before))
            with self.assertRaises(FileExistsError):
                plan.export_bundle(self.project, target)
            self.assertEqual(before, {p.name: p.read_bytes() for p in target.iterdir()})
            existing = Path(tmp) / "existing.txt"
            existing.write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                plan.export_bundle(self.project, existing)
            self.assertEqual("keep", existing.read_text(encoding="utf-8"))

    def test_failed_export_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "bundle"
            with mock.patch.object(Path, "write_text", side_effect=OSError("injected write failure")):
                with self.assertRaises(OSError):
                    plan.export_bundle(self.project, target)
            self.assertEqual([], list(Path(tmp).iterdir()))

    def test_effects_and_review_export(self):
        self.rejects(lambda p: p["shots"][0].update(effects=""), "effects")
        docs = plan.render(self.project)
        self.assertIn(self.project["shots"][0]["execution"]["effects"], docs["05-video-prompts.md"])
        self.assertIn(self.project["review"]["fixed"][0], docs["06-review.md"])
        changed = copy.deepcopy(self.project)
        del changed["review"]
        self.assertEqual([], plan.validate(changed))
        self.assertIn("语义审阅尚未登记", plan.render(changed)["06-review.md"])
        self.rejects(lambda p: p.update(review={}), "review")

    def test_local_edits_and_shared_outputs(self):
        mutations = [
            ("outcome", "双方停止争夺，保留退路；其余动作暂不变，此项只测文本传播。"),
        ]
        for key, value in mutations:
            changed = copy.deepcopy(self.project)
            changed["design"][key] = value
            docs = plan.render(changed)
            self.assertIn(value, docs["01-design.md"])
            self.assertNotIn(value, docs["05-video-prompts.md"])
            self.assertEqual(changed["assets"], json.loads(docs["project.json"])["assets"])
        changed = copy.deepcopy(self.project)
        changed["assets"][0]["reference"] = {"source": "用户提供的角色图（仅登记，测试未读取图片）", "control": "外观", "keep": "已有身份锚点", "exclude": "不继承图中姿势"}
        self.assertEqual([], plan.validate(changed))
        self.assertIn("不继承图中姿势", plan.render(changed)["02-assets.md"])

    def test_schema_upgrade_required(self):
        self.assertEqual([], plan.validate(self.project))
        for version in ("1.0", 1.1, "1.2"):
            self.rejects(lambda p, version=version: p.update(schema_version=version), "升级")

    def test_execution_and_context_required_strict_fields(self):
        self.rejects(lambda p: p["shots"][0].pop("execution"), "缺少字段 execution")
        self.rejects(lambda p: p["segments"][0].pop("prompt_context"), "prompt_context")
        self.rejects(lambda p: p["segments"][0].update(prompt_context=" "), "prompt_context")
        self.rejects(lambda p: p["segments"][0].update(prompt_context="22秒开始"), "执行文本不得含时间语法")
        self.rejects(lambda p: p["shots"][0].update(execution=None), "必须是对象")
        self.rejects(lambda p: p["shots"][0]["execution"].update(extra="x"), "未知字段")
        for key in plan.EXECUTION_FIELDS - {"cues"}:
            self.rejects(lambda p, key=key: p["shots"][0]["execution"].update({key: " "}), ".execution." + key)
        self.rejects(lambda p: p["shots"][0]["execution"].update(cues=[]), "非空对象数组")
        self.rejects(lambda p: p["shots"][0]["execution"].update(cues={}), "非空对象数组")
        self.rejects(lambda p: p["shots"][0]["execution"]["cues"].append(None), "必须是对象")
        self.rejects(lambda p: p["shots"][0]["execution"]["cues"][0].pop("text"), "缺少字段 text")
        self.rejects(lambda p: p["shots"][0]["execution"]["cues"][0].update(extra="x"), "未知字段")
        self.rejects(lambda p: p["shots"][0]["execution"]["cues"][0].update(text=""), ".text")

    def test_cue_coverage_gap_overlap_order_and_bounds(self):
        project = copy.deepcopy(self.project)
        cues = [{"start": 0, "end": 2, "text": "剑尖接触护臂"},
                {"start": 2, "end": 4, "text": "维持接触并推压"}]
        project["shots"][0]["execution"]["cues"] = cues
        self.assertEqual([], plan.validate(project))
        for start in (2.1, 1.9):
            changed = copy.deepcopy(project)
            changed["shots"][0]["execution"]["cues"][1]["start"] = start
            self.assertTrue(any("缺口、重叠" in e for e in plan.validate(changed)))
        changed = copy.deepcopy(project)
        changed["shots"][0]["execution"]["cues"].reverse()
        self.assertTrue(any("顺序错误" in e for e in plan.validate(changed)))
        for update in ({"start": -1}, {"end": 5}, {"end": 0}):
            self.rejects(lambda p, update=update: p["shots"][0]["execution"]["cues"][0].update(update), "不得超镜")
        self.rejects(lambda p: p["shots"][0]["execution"]["cues"][0].update(end=3), "镜头终点")
        for value in (True, "0", float("inf"), float("nan"), 10**1000):
            for key in ("start", "end"):
                self.rejects(lambda p, key=key, value=value: p["shots"][0]["execution"]["cues"][0].update({key: value}), "有限数字")

    def test_execution_time_syntax_is_rejected(self):
        fields = sorted(plan.EXECUTION_FIELDS - {"cues"}) + ["cue_text"]
        for field in fields:
            for value in ("推压22秒", "22—24秒继续动作", "到0:12撤步", "01:02:03.5收势", "0：12撤步"):
                def change(p, field=field, value=value):
                    execution = p["shots"][0]["execution"]
                    if field == "cue_text":
                        execution["cues"][0]["text"] = value
                    else:
                        execution[field] = value
                self.rejects(change, "时刻只允许写在 cues.start / cues.end 数值字段")
        changed = copy.deepcopy(self.project)
        changed["shots"][0]["execution"]["cues"][0]["text"] = "向侧面移动2米，一秒呼吸后保持承力"
        self.assertEqual([], plan.validate(changed))

    def test_adjacent_world_and_execution_states_in_same_segment(self):
        self.assertEqual(self.project["segments"][0]["shot_ids"], ["shot_0", "shot_1"])
        self.rejects(lambda p: p["shots"][1].update(opening_state="段内原状态漂移"), "与前镜 end_state 必须逐字一致")
        self.rejects(lambda p: p["shots"][1]["execution"].update(opening_state="段内执行状态漂移"), "与前镜 execution.end_state 必须逐字一致")
        self.rejects(lambda p: p["shots"][0]["execution"].update(end_state=p["shots"][1]["execution"]["opening_state"] + " "), "逐字一致")
        changed = copy.deepcopy(self.project)
        changed["shots"][1]["camera"] = "完全不同的机位"
        changed["shots"][1]["execution"]["camera"] = "反打近景"
        self.assertEqual([], plan.validate(changed))

    def test_video_local_time_and_window_only_text(self):
        docs = plan.render(self.project)
        video = docs["05-video-prompts.md"]
        first, second = video.split("## 制作段 1\n", 1)[1].split("## 制作段 2\n", 1)
        self.assertIn("0–4秒：本镜窗口动作2", second)
        self.assertIn("4–8秒：本镜窗口动作3", second)
        self.assertNotIn("8–12秒", second)
        self.assertNotIn("12–16秒", second)
        for text in ("旧过程从拔剑", "完成依赖", "全场", "原稿机位", "原稿特效", "原稿声音",
                     self.project["design"]["outcome"], self.project["scene"]["geography"]):
            self.assertNotIn(text, video)
        for key in ("goals", "rules", "viewing_tasks"):
            for value in self.project["design"][key]:
                self.assertNotIn(value, video)
        for key in ("assumptions", "constraints"):
            for value in self.project[key]:
                self.assertNotIn(value, video)
        for group in ("assets", "beats", "shots", "segments", "keyframes"):
            for item in self.project[group]:
                self.assertNotIn(item["id"], video)
        self.assertIn("### 镜头 1", first)
        self.assertIn("### 镜头 2", first)
        self.assertIn("### 镜头 1", second)
        self.assertIn("本段起态：" + self.project["shots"][2]["execution"]["opening_state"], second)
        self.assertIn("本段终态与承接：" + self.project["shots"][3]["execution"]["end_state"], second)
        self.assertIn("旧过程从拔剑起手持续推压", docs["03-storyboard.md"])
        self.assertIn("全场时间：8–12秒", docs["03-storyboard.md"])
        self.assertIn(self.project["review"]["verification"], docs["03-storyboard.md"])
        self.assertIn("观看任务专用文本", docs["01-design.md"])
        changed = copy.deepcopy(self.project)
        changed["shots"][0]["execution"]["cues"][0]["text"] = "改变首镜的独有窗口动作"
        changed["segments"][0]["prompt_context"] = "改变首段的局部规则"
        self.assertEqual(second, plan.render(changed)["05-video-prompts.md"].split("## 制作段 2\n", 1)[1])

    def test_video_assets_are_segment_union_with_local_references(self):
        changed = copy.deepcopy(self.project)
        changed["shots"][2]["asset_ids"].remove("late_prop")
        changed["keyframes"][2]["asset_ids"].remove("late_prop")
        changed["assets"][-1]["reference"] = {"source": "断碑参考.png", "control": "外观局部控制", "keep": "保留碑面裂纹", "exclude": "不继承旧光线"}
        unused = copy.deepcopy(changed["assets"][-1])
        unused.update(id="unused_prop", name="未用资产", anchors=["未用锚点"],
                      reference={"source": "未用来源", "control": "未用控制", "keep": "未用继承", "exclude": "未用排除"})
        changed["assets"].append(unused)
        self.assertEqual([], plan.validate(changed))
        video = plan.render(changed)["05-video-prompts.md"]
        first, second = video.split("## 制作段 1\n", 1)[1].split("## 制作段 2\n", 1)
        self.assertNotIn("断碑稳定锚点", first)
        self.assertNotIn("断碑参考.png", first)
        self.assertIn("断碑稳定锚点", second)
        for value in changed["assets"][-2]["reference"].values():
            self.assertIn(value, second)
        for value in ("未用资产", "未用锚点", "未用来源", "未用控制", "未用继承", "未用排除"):
            self.assertNotIn(value, video)

    def test_review_media_observations_preserve_author_claims_without_verdict(self):
        for observations in (None, []):
            changed = copy.deepcopy(self.project)
            if observations is not None:
                changed["review"]["media_observations"] = observations
            self.assertEqual([], plan.validate(changed))
            self.assertIn("未登记媒体观察", plan.render(changed)["06-review.md"])
        changed = copy.deepcopy(self.project)
        changed["review"]["media_observations"] = [
            {"source": kind + "素材来源", "kind": kind, "observation": "作者已观看或听辨本素材并登记接触情况", "limitations": "只观察此素材，未覆盖全场"}
            for kind in ("image", "video", "audio")
        ]
        self.assertEqual([], plan.validate(changed))
        docs = plan.render(changed)
        review = docs["06-review.md"]
        self.assertIn("semantic_status: needs_review", review)
        self.assertIn("structural_status: pass", review)
        self.assertIn("作者登记的媒体观察（脚本未复核）", review)
        self.assertIn(changed["review"]["verification"], review)
        for item in changed["review"]["media_observations"]:
            for value in item.values():
                self.assertIn(value, review)
        for forbidden in ("not_generated", "没有观看", "media_status:", "未登记媒体观察", "semantic_status: pass"):
            self.assertNotIn(forbidden, review)
        self.assertEqual(changed["review"], json.loads(docs["project.json"])["review"])
        self.assertNotIn("待生成", docs["02-assets.md"].splitlines()[0])
        self.assertNotIn("待生成", docs["04-keyframes.md"].splitlines()[0])

    def test_review_observations_and_viewing_tasks_are_strict(self):
        observation = {"source": "片段.mp4", "kind": "video", "observation": "接触点可见", "limitations": "只看此片段"}
        self.rejects(lambda p: p["review"].update(media_observations={}), "对象数组")
        for value in (None, {}, dict(observation, kind="text"), dict(observation, kind=[]), dict(observation, typo="x")):
            self.rejects(lambda p, value=value: p["review"].update(media_observations=[value]), "media_observations")
        for key in observation:
            self.rejects(lambda p, key=key: p["review"].update(media_observations=[dict(observation, **{key: " "})]), "非空字符串")
        self.rejects(lambda p: p["design"].update(viewing_tasks="任务"), "字符串数组")
        self.rejects(lambda p: p["design"].update(viewing_tasks=[""]), "非空字符串")
        self.rejects(lambda p: p["design"].update(viewing_tasks=[]), "数组不能为空")


if __name__ == "__main__":
    unittest.main()
