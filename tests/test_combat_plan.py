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


def make_craft_project():
    """The same plan upgraded to 1.2, satisfying every craft requirement."""
    project = make_project()
    project["schema_version"] = "1.2"
    lights = ["晴冷顶光压住两人，无术法光源主导",
              "剑锋微光成为画面主光，体修半边入影",
              "剑锋微光仍主导，断碑背面全暗",
              "顶光回到两人之间，术法光源退去"]
    risks = ("low", "low", "high", "low")
    for shot, light, risk in zip(project["shots"], lights, risks):
        shot["light"] = light
        shot["risk"] = risk
        shot["execution"]["light"] = light
        if risk == "high":
            shot["fallback"] = "改为侧向中景只拍剑锋与护臂接点，断碑留前景虚焦"
    project["beats"][1]["marks"] = ["pivotal", "adaptation"]
    project["beats"][2]["marks"] = ["breath"]
    project["scene"]["attrition"] = [
        {"id": "mark_scuff", "mark": "台面两道擦痕与散石", "from_beat": "beat_open",
         "consequence": "后续退步不能落在擦痕内侧，脚底会滑"},
    ]
    project["cost"] = [
        {"id": "cost_edge", "owner": "hero", "item": "剑刃近护手处一处缺口", "from_beat": "beat_open",
         "irreversible": True, "consequence": "此后格挡只能用剑脊，缺口侧不再承力"},
        {"id": "cost_arm", "owner": "opponent", "item": "护臂外层铜片", "from_beat": "beat_2",
         "irreversible": False, "consequence": "铜片变形后抬臂变慢，收势时仍可活动"},
    ]
    project["knowledge"] = [
        {"id": "know_block", "holder": "opponent", "belief": "剑修仍能用完整剑刃格挡",
         "truth": "剑刃已有缺口，只能用剑脊承力", "from_beat": "beat_open",
         "resolved_by": "beat_2", "cue": "擦痕上的金属碎屑先于缺口被看见"},
    ]
    near, far = ["arena", "hero", "opponent"], ["arena", "hero", "opponent", "late_prop"]
    project["keyframes"] = [
        {"id": "frame_0", "shot_id": "shot_0", "time_sec": 0, "role": "single",
         "asset_ids": near[:], "state": "双方隔台对峙", "prompt": "隔台对峙的静图，顶光压住两人"},
        {"id": "frame_1", "shot_id": "shot_1", "time_sec": 4, "role": "single",
         "asset_ids": near[:], "state": "剑锋压住护臂", "prompt": "剑锋压住护臂的静图，剑锋微光为主光"},
        {"id": "frame_handoff", "shot_id": "shot_1", "time_sec": 8, "role": "handoff",
         "asset_ids": near[:], "state": "双方僵持于台缘", "prompt": "台缘僵持的可复现静图：双脚落定、接点静止、轮廓完整"},
        {"id": "frame_prep", "shot_id": "shot_2", "time_sec": 8.5, "role": "prep",
         "asset_ids": far[:], "state": "断碑滑近前的预备姿态", "prompt": "决胜接点前的预备静图，重心已压低"},
        {"id": "frame_contact", "shot_id": "shot_2", "time_sec": 10, "role": "contact",
         "asset_ids": far[:], "state": "断碑抵住两人身后", "prompt": "决胜接触瞬间静图，接点与受力方向清楚"},
        {"id": "frame_result", "shot_id": "shot_2", "time_sec": 11.5, "role": "result",
         "asset_ids": far[:], "state": "断碑挡住退路", "prompt": "接触结果静图：退路被挡，碎石已落定"},
        {"id": "frame_3", "shot_id": "shot_3", "time_sec": 12, "role": "single",
         "asset_ids": far[:], "state": "断碑挡住退路", "prompt": "收势前的静图，顶光回到两人之间"},
    ]
    return project


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.project = make_project()

    def rejects(self, change, fragment):
        changed = copy.deepcopy(self.project)
        change(changed)
        self.assertTrue(any(fragment in error for error in plan.validate(changed)), plan.validate(changed))

    def test_all_examples_and_render(self):
        examples = sorted((ROOT / "examples").glob("*.json"))
        self.assertEqual(5, len(examples))
        self.assertEqual({"1.3"}, {plan.load_project(path)["schema_version"] for path in examples})
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

    def test_published_directories_match_current_render(self):
        for path in sorted((ROOT / "examples").glob("*.json")):
            published = path.with_suffix("")
            with self.subTest(example=path.name):
                self.assertTrue(published.is_dir(), f"缺少已发布目录 {published.name}")
                docs = plan.render(plan.load_project(path))
                for name, content in docs.items():
                    target = published / name
                    self.assertTrue(target.is_file(), f"{published.name} 缺少 {name}")
                    self.assertEqual(content, target.read_text(encoding="utf-8"),
                                     f"{published.name}/{name} 与当前 render 不一致，请重新导出")

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
        self.rejects(lambda p: p["segments"][0].update(opening_state="错误"), "的外层 opening_state 不一致")
        self.rejects(lambda p: p["segments"][-1].update(closing_state="错误"), "的外层 end_state 不一致")
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
        for version in ("1.0", 1.1, 1.2, 1.3, "1.4", "1.1 "):
            self.rejects(lambda p, version=version: p.update(schema_version=version), "升级")

    def test_one_one_rejects_one_two_fields(self):
        self.rejects(lambda p: p.update(cost=[]), "仅 1.2 支持该字段")
        self.rejects(lambda p: p.update(knowledge=[]), "仅 1.2 支持该字段")
        for change in (lambda p: p["shots"][0].update(light="x"),
                       lambda p: p["shots"][0].update(risk="low"),
                       lambda p: p["keyframes"][0].update(role="single"),
                       lambda p: p["scene"].update(attrition=[]),
                       lambda p: p["beats"][0].update(marks=["pivotal"])):
            self.rejects(change, "未知字段")

    def test_execution_and_context_required_strict_fields(self):
        self.rejects(lambda p: p["shots"][0].pop("execution"), "缺少字段 execution")
        self.rejects(lambda p: p["segments"][0].pop("prompt_context"), "prompt_context")
        self.rejects(lambda p: p["segments"][0].update(prompt_context=" "), "prompt_context")
        self.rejects(lambda p: p["segments"][0].update(prompt_context="22秒开始"), "不得含阿拉伯数字秒码或冒号时码")
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


class CraftTests(unittest.TestCase):
    """1.2 编舞要求：只检查可由结构证明的后果。"""

    def setUp(self):
        self.project = make_craft_project()

    def rejects(self, change, fragment):
        changed = copy.deepcopy(self.project)
        change(changed)
        errors = plan.validate(changed)
        self.assertTrue(any(fragment in error for error in errors), errors)

    def test_craft_project_is_valid_and_renders(self):
        self.assertEqual([], plan.validate(self.project))
        docs = plan.render(self.project)
        self.assertEqual(7, len(docs))
        self.assertEqual(self.project, json.loads(docs["project.json"]))

    def test_every_mark_is_required_once(self):
        for mark in plan.MARKS:
            def change(p, mark=mark):
                for beat in p["beats"]:
                    if mark in beat.get("marks", []):
                        beat["marks"] = [x for x in beat["marks"] if x != mark] or None
                        if beat["marks"] is None:
                            del beat["marks"]
            self.rejects(change, f"全场缺少 {mark} 标记节拍")
        self.rejects(lambda p: p["beats"][1].update(marks=["pivotal", "typo"]), "未知标记")
        self.rejects(lambda p: p["beats"][1].update(marks=["pivotal", "pivotal"]), "引用不得重复")
        self.rejects(lambda p: p["beats"][1].update(marks=[]), "数组不能为空")

    def test_pivotal_beat_needs_prep_contact_result_in_order(self):
        for role in plan.CONTACT_ROLES:
            self.rejects(lambda p, role=role: p.update(keyframes=[x for x in p["keyframes"] if x["role"] != role]),
                         f"缺少 {role} 帧")
        def swap(p):
            prep = next(x for x in p["keyframes"] if x["role"] == "prep")
            result = next(x for x in p["keyframes"] if x["role"] == "result")
            prep["time_sec"], result["time_sec"] = result["time_sec"], prep["time_sec"]
        self.rejects(swap, "时刻须严格递增")

    def test_breath_beat_must_not_overlap_the_turn(self):
        self.rejects(lambda p: p["beats"][2].update(marks=["breath", "pivotal"]), "不能同时是关键转折")
        self.rejects(lambda p: p["beats"][1].update(marks=["pivotal", "adaptation", "breath"]), "不得与关键转折窗口重叠")

    def test_adaptation_beat_needs_the_beat_it_answers(self):
        self.rejects(lambda p: p["beats"][1].update(requires=[]), "须登记它所回应的已完成前拍")

    def test_segment_boundary_needs_a_reproducible_handoff_frame(self):
        self.rejects(lambda p: p.update(keyframes=[x for x in p["keyframes"] if x["role"] != "handoff"]),
                     "段界缺少 handoff 关键帧")
        self.rejects(lambda p: next(x for x in p["keyframes"] if x["role"] == "handoff").update(time_sec=7.5),
                     "段界缺少 handoff 关键帧")
        def reassign(p):
            frame = next(x for x in p["keyframes"] if x["role"] == "handoff")
            frame["shot_id"] = "shot_2"
        self.rejects(reassign, "须归属前段末镜")

    def test_light_must_change_somewhere(self):
        def flatten(p):
            for shot in p["shots"]:
                shot["light"] = "晴冷顶光压住两人，无术法光源主导"
        self.rejects(flatten, "全场光照登记完全相同")
        self.assertEqual([], plan.validate(self.single_shot_project()),
                         "单镜方案没有第二个镜头可比，不应触发光照互异判据")

    def single_shot_project(self):
        """Collapse the fixture to one shot in one segment; craft rules must still pass."""
        project = copy.deepcopy(self.project)
        first, last = project["shots"][0], project["shots"][-1]
        project["shots"] = [{
            "id": "solo_shot", "start": 0, "end": project["duration_sec"],
            "beat_ids": [beat["id"] for beat in project["beats"]],
            "asset_ids": ["arena", "hero", "opponent", "late_prop"],
            "opening_state": first["opening_state"], "end_state": last["end_state"],
            "camera": "原稿机位", "effects": "原稿特效", "sound": "原稿声音",
            "light": first["light"], "risk": "low",
            "execution": {"opening_state": first["execution"]["opening_state"],
                          "end_state": last["execution"]["end_state"],
                          "camera": "侧面中景", "effects": "剑锋微光贴住接触点",
                          "light": "顶光压住两人", "sound": "金属摩擦与足底擦地",
                          "cues": [{"start": 0, "end": project["duration_sec"],
                                    "text": "单镜覆盖全场窗口动作，维持已有接触相位"}]},
        }]
        project["segments"] = [{"id": "solo_segment", "shot_ids": ["solo_shot"],
                               "opening_state": first["opening_state"], "closing_state": last["end_state"],
                               "prompt_context": "单镜单段：石台平坦，剑锋与护臂接触后持续承力"}]
        for frame in project["keyframes"]:
            frame["shot_id"] = "solo_shot"
        return project

    def test_two_beat_floor_is_satisfiable(self):
        """1.2 的硬下限：两拍即可满足九条后果，一拍不行。"""
        project = self.single_shot_project()
        project["beats"] = [x for x in project["beats"] if x["id"] in ("beat_open", "beat_2")]
        project["beats"][0].update(start=0, end=8, marks=["breath"], requires=[])
        project["beats"][1].update(start=8, end=project["duration_sec"],
                                   marks=["pivotal", "adaptation"], requires=["beat_open"])
        project["shots"][0]["beat_ids"] = ["beat_open", "beat_2"]
        project["scene"]["attrition"][0]["from_beat"] = "beat_open"
        for entry in project["cost"]:
            entry["from_beat"] = "beat_open"
        del project["knowledge"]
        keep = {"frame_prep", "frame_contact", "frame_result"}
        project["keyframes"] = [x for x in project["keyframes"] if x["id"] in keep]
        for frame, moment in zip(sorted(project["keyframes"], key=lambda x: x["time_sec"]), (9.0, 11.0, 13.0)):
            frame["time_sec"] = moment
        self.assertEqual([], plan.validate(project), "两拍方案应当合法")
        single = copy.deepcopy(project)
        single["beats"] = single["beats"][:1]
        single["beats"][0]["end"] = single["duration_sec"]
        single["beats"][0]["marks"] = ["pivotal", "adaptation"]
        single["shots"][0]["beat_ids"] = ["beat_open"]
        self.assertTrue(any("缺少 breath" in e for e in plan.validate(single)),
                        "单拍方案无法同时承担呼吸拍与关键转折，应被拒绝")

    def test_single_segment_needs_no_handoff_frame(self):
        project = self.single_shot_project()
        project["keyframes"] = [x for x in project["keyframes"] if x["role"] != "handoff"]
        self.assertEqual([], plan.validate(project),
                         "只有一个制作段时没有段界，不应要求 handoff 帧")
        self.rejects(lambda p: p["shots"][0].update(light=" "), ".light")
        self.rejects(lambda p: p["shots"][0].pop("light"), "缺少字段 light")
        self.rejects(lambda p: p["shots"][0]["execution"].update(light="推压22秒"), "不得含阿拉伯数字秒码")

    def test_terrain_must_degrade_before_the_turn(self):
        self.rejects(lambda p: p["scene"].update(attrition=[]), "非空战场累积痕迹数组")
        self.rejects(lambda p: p["scene"].pop("attrition"), "缺少字段 attrition")
        self.rejects(lambda p: p["scene"]["attrition"][0].update(from_beat="beat_3"),
                     "没有任何战场痕迹在关键转折之前形成")
        self.rejects(lambda p: p["scene"]["attrition"][0].update(from_beat="missing"), "未知节拍引用")
        self.rejects(lambda p: p["scene"]["attrition"][0].update(id="hero"), "ID全场重复")

    def test_cost_must_be_paid_by_both_sides_and_one_irreversible(self):
        self.rejects(lambda p: p.update(cost=[]), "战斗不得零支出收场")
        self.rejects(lambda p: p.pop("cost"), "非空代价账目")
        def reversible(p):
            for entry in p["cost"]:
                entry["irreversible"] = False
        self.rejects(reversible, "全场至少一项不可逆支出")
        self.rejects(lambda p: p["cost"][1].update(owner="hero"), "代价集中在同一方")
        self.rejects(lambda p: p["cost"][0].update(owner="arena"), "须引用行动主体资产")
        self.rejects(lambda p: p["cost"][0].update(irreversible="true"), "必须是布尔值")
        self.rejects(lambda p: p["cost"][0].update(from_beat="missing"), "未知节拍引用")

    def test_knowledge_track_needs_a_real_gap(self):
        self.rejects(lambda p: p["knowledge"][0].update(truth=p["knowledge"][0]["belief"]), "即无信息差")
        self.rejects(lambda p: p["knowledge"][0].update(resolved_by="beat_open"), "不能等于建立误判的同一拍")
        self.rejects(lambda p: p["knowledge"][0].update(from_beat="beat_3"), "识破拍早于误判建立拍")
        self.rejects(lambda p: p.update(knowledge=[]), "无信息差则省略该字段")
        changed = copy.deepcopy(self.project)
        del changed["knowledge"]
        self.assertEqual([], plan.validate(changed))
        changed = copy.deepcopy(self.project)
        del changed["knowledge"][0]["resolved_by"]
        self.assertEqual([], plan.validate(changed))
        self.assertIn("本场未识破", plan.render(changed)["01-design.md"])

    def test_high_risk_shot_needs_a_preauthorized_fallback(self):
        self.rejects(lambda p: p["shots"][2].pop("fallback"), "高风险镜头须预授权保底构图")
        self.rejects(lambda p: p["shots"][0].update(fallback="低风险却写保底"), "低风险镜头不登记保底构图")
        self.rejects(lambda p: p["shots"][2].update(risk="unknown"), "仅支持 low、high")
        self.rejects(lambda p: p["shots"][2].update(fallback="改用保底构图撑22秒"), "不得含阿拉伯数字秒码")

    def test_keyframe_role_is_strict(self):
        self.rejects(lambda p: p["keyframes"][0].update(role="keyframe"), "仅支持")
        self.rejects(lambda p: p["keyframes"][0].pop("role"), "缺少字段 role")

    def test_internal_ids_must_not_leak_into_copyable_text(self):
        for leaked in ("hero", "beat_open", "shot_0", "segment_open", "frame_0",
                       "cost_edge", "know_block", "mark_scuff"):
            with self.subTest(leaked=leaked):
                self.rejects(lambda p, x=leaked: p["shots"][0]["execution"]["cues"][0].update(text="承接 " + x + " 的相位"),
                             "不得含内部 ID " + leaked)
        self.rejects(lambda p: p["segments"][0].update(prompt_context="本段依赖 beat_open 的结果"), "不得含内部 ID")
        self.rejects(lambda p: p["keyframes"][0].update(prompt="静图，见 cost_edge"), "不得含内部 ID")
        self.rejects(lambda p: p["shots"][2].update(fallback="改用保底，承接 shot_1"), "不得含内部 ID")
        for key in ("opening_state", "end_state", "camera", "effects", "sound", "light"):
            self.rejects(lambda p, k=key: p["shots"][0]["execution"].update({k: "参照 frame_handoff 的姿态"}),
                         "不得含内部 ID")

    def test_keyframe_prompt_rejects_time_syntax(self):
        for value in ("全场 2.4 秒的静图", "到0:12的姿态", "推压22秒后的接点"):
            self.rejects(lambda p, v=value: p["keyframes"][0].update(prompt=v), "静图提示词不得含阿拉伯数字秒码")
        changed = copy.deepcopy(self.project)
        changed["keyframes"][0]["prompt"] = "静图：退三步、两柄戟压住巷口，离石面一米二"
        self.assertEqual([], plan.validate(changed), "计数与长度数字不应被时码规则拦下")

    def test_missing_frame_on_boundary_shot_names_the_handoff_duty(self):
        boundary = self.project["segments"][0]["shot_ids"][-1]
        self.rejects(lambda p: p.update(keyframes=[x for x in p["keyframes"] if x["shot_id"] != boundary]),
                     "该镜是段界所在的前段末镜")
        inner = self.project["segments"][1]["shot_ids"][0]
        changed = copy.deepcopy(self.project)
        changed["keyframes"] = [x for x in changed["keyframes"] if x["shot_id"] != inner]
        self.assertTrue(any("镜头缺少关键帧 " + inner in e and "段界" not in e for e in plan.validate(changed)),
                        "非段界镜头不应被加上交接帧提示")

    def test_craft_fields_reach_the_right_documents(self):
        docs = plan.render(self.project)
        board, video = docs["03-storyboard.md"], docs["05-video-prompts.md"]
        design, assets = docs["01-design.md"], docs["02-assets.md"]
        self.assertIn("光照与归属：" + self.project["shots"][1]["light"], board)
        self.assertIn("光照：" + self.project["shots"][1]["light"], video)
        self.assertIn("标记 pivotal, adaptation", board)
        self.assertIn("生成风险：高。保底构图：", board)
        self.assertIn("若一次生成未得到可用结果，改用保底构图", video)
        self.assertIn(self.project["shots"][2]["fallback"], video)
        self.assertIn("段界交接静图（本段末帧，亦为下段首帧条件）", video)
        self.assertIn("段界交接帧", docs["04-keyframes.md"])
        self.assertIn("接触帧", docs["04-keyframes.md"])
        self.assertIn("剑刃近护手处一处缺口", design)
        self.assertIn("此后格挡只能用剑脊", design)
        self.assertIn("台面两道擦痕与散石", assets)
        self.assertIn("以为：剑修仍能用完整剑刃格挡", design)
        self.assertIn("代价结算", docs["06-review.md"])
        self.assertIn("信息差结算", docs["06-review.md"])

    def test_craft_documents_keep_director_data_out_of_video(self):
        video = plan.render(self.project)["05-video-prompts.md"]
        for group in ("assets", "beats", "shots", "segments", "keyframes"):
            for item in self.project[group]:
                self.assertNotIn(item["id"], video)
        for group in ("cost", "knowledge"):
            for item in self.project[group]:
                self.assertNotIn(item["id"], video)
        for entry in self.project["scene"]["attrition"]:
            self.assertNotIn(entry["id"], video)
        for entry in self.project["cost"]:
            self.assertNotIn(entry["consequence"], video)
        for entry in self.project["knowledge"]:
            self.assertNotIn(entry["truth"], video)
            self.assertNotIn(entry["belief"], video)
        self.assertNotIn("标记 pivotal", video)
        self.assertNotIn("生成风险：高。保底构图：", video)


if __name__ == "__main__":
    unittest.main()
