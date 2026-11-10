"""1.4 window planning: content-driven boundaries, knots, carries, frames and rendering."""

import copy
import unittest

from test_combat_plan import make_craft_project, plan
from test_layers import make_layered_project, make_tracked_project


def add_exit_frame(project):
    """The 16-second fixture has no frame at the film end; windows need one."""
    project["keyframes"].append({
        "id": "frame_exit", "shot_id": "shot_3", "time_sec": 16, "role": "single",
        "asset_ids": ["arena", "hero", "opponent", "late_prop"],
        "state": "双方收势分开",
        "prompt": "收势后的完整静图：两人各退一步、断碑在身后、台面擦痕可见",
    })
    return project


def make_windowed_project():
    project = add_exit_frame(make_craft_project())
    project["schema_version"] = "1.4"
    project["window_plan"] = {
        "capability": {"max_window_sec": 8, "source": "user_stated", "arbitrary_start": True,
                       "frame_conditioning": "both", "internal_cuts": True, "audio": False},
        "knots": [
            {"id": "K1", "shot_ids": ["shot_0", "shot_1"], "kind": "action",
             "why": "剑锋压住护臂的连续承力，拆开则支点与受力方向丢失"},
            {"id": "K2", "shot_ids": ["shot_2", "shot_3"], "kind": "causal",
             "why": "断碑滑入与退路被挡是同一因果，决胜帧不能与结果分开"},
        ],
        "candidates": [
            {"id": "C1", "time_sec": 8, "shot_id": "shot_1", "grade": "A",
             "reason": "台缘僵持的短暂稳定瞬间，双脚落定、接点静止", "seam": "硬切"},
            {"id": "C2", "time_sec": 12, "shot_id": "shot_2", "grade": "B",
             "reason": "断碑落定后的可读姿态，只作降级切点"},
        ],
        "windows": [
            {"id": "W1", "start": 0, "end": 8, "shot_ids": ["shot_0", "shot_1"],
             "knot_ids": ["K1"],
             "opening_state": "双方隔台对峙", "closing_state": "双方僵持于台缘",
             "entry_frame": "frame_0", "exit_frame": "frame_handoff",
             "carries": {"text": "开场：双方隔台站定，剑锋与护臂尚未接触，台面无积水"},
             "fallback_splits": [], "risk": "low"},
            {"id": "W2", "start": 8, "end": 16, "shot_ids": ["shot_2", "shot_3"],
             "knot_ids": ["K2"],
             "opening_state": "双方僵持于台缘", "closing_state": "双方收势分开",
             "entry_frame": "frame_handoff", "exit_frame": "frame_exit",
             "carries": {"text": "台缘僵持，剑刃缺口已开，擦痕与散石留在台面",
                         "costs": ["cost_edge"], "knowledge": ["know_block"],
                         "attrition": ["mark_scuff"]},
             "fallback": "改为只拍断碑、剑锋与退路的接点特写，保持本窗起终态",
             "fallback_splits": ["C2"], "risk": "high"},
        ],
        "notes": "示例前提：用户声明上限八秒，不是全包默认。被否：四秒处为段内呼吸，不切；十二秒处只作降级切点。",
    }
    return project


def make_windowed_tracked():
    project = make_tracked_project()
    project["schema_version"] = "1.4"
    add_exit_frame(project)
    project["transitions"] = [
        {"id": "cut_in", "from_shot": "shot_1", "to_shot": "shot_2", "method": "match_graphic",
         "layer": "world", "keeps": ["剑修面容", "闭目姿态"], "changes": ["石台变为识海"],
         "cut_condition": "眼睑完全闭合静止时切", "route": "cut"},
        {"id": "cut_out", "from_shot": "shot_2", "to_shot": "shot_3", "method": "sound_bridge",
         "layer": "world", "keeps": ["剑修面容", "断弦余音"], "changes": ["识海回到石台"],
         "cut_condition": "断弦余音落下时切", "route": "cut"},
    ]
    project["window_plan"] = {
        "capability": {"max_window_sec": 8, "source": "user_stated", "arbitrary_start": True,
                       "frame_conditioning": "both", "internal_cuts": True, "audio": False},
        "knots": [
            {"id": "K1", "shot_ids": ["shot_0", "shot_1"], "kind": "action",
             "why": "外层承力与剑锋接触不可拆"},
            {"id": "K2", "shot_ids": ["shot_2", "shot_3"], "kind": "space",
             "why": "内景决胜与外层同一时刻的状态不可拆"},
        ],
        "candidates": [
            {"id": "C1", "time_sec": 8, "shot_id": "shot_1", "grade": "A",
             "reason": "台缘僵持稳定，动作线在此切换", "seam": "图形匹配"},
        ],
        "windows": [
            {"id": "W1", "start": 0, "end": 8, "shot_ids": ["shot_0", "shot_1"],
             "knot_ids": ["K1"], "opening_state": "双方隔台对峙",
             "closing_state": "双方僵持于台缘",
             "entry_frame": "frame_0", "exit_frame": "frame_handoff",
             "carries": {"text": "开场：双方隔台站定，外层承力尚未开始"},
             "fallback_splits": [], "risk": "low"},
            {"id": "W2", "start": 8, "end": 16, "shot_ids": ["shot_2", "shot_3"],
             "knot_ids": ["K2"], "opening_state": "双方僵持于台缘",
             "closing_state": "双方收势分开",
             "entry_frame": "frame_handoff", "exit_frame": "frame_exit",
             "carries": {"text": "外层剑修闭目承力、护臂抵在剑脊上，内景同时展开；断碑与擦痕仍在",
                         "costs": ["cost_edge"], "knowledge": ["know_block"],
                         "attrition": ["mark_scuff"],
                         "tracks": ["line_world", "line_inner"]},
             "fallback_splits": [], "risk": "low"},
        ],
    }
    return project


def make_mid_shot_project():
    """A window boundary inside shot_1, aligned to a cue boundary."""
    project = make_windowed_project()
    project["window_plan"]["capability"]["max_window_sec"] = 10
    project["window_plan"]["knots"][0]["shot_ids"] = ["shot_0"]
    project["window_plan"]["candidates"][0].update(
        time_sec=7.5, shot_id="shot_1", grade="B",
        reason="镜头中部的 cue 边界，剑锋仍压住护臂，可作半动作接缝",
    )
    project["shots"][1]["execution"]["cues"] = [
        {"start": 4, "end": 7.5, "text": "前半动作，剑锋压住护臂"},
        {"start": 7.5, "end": 8, "text": "后半动作，护臂开始下沉"},
    ]
    project["keyframes"].append({
        "id": "frame_mid", "shot_id": "shot_1", "time_sec": 7.5, "role": "handoff",
        "asset_ids": project["shots"][1]["asset_ids"][:],
        "state": "台缘僵持，剑锋已压住护臂",
        "prompt": "台缘僵持的静帧：剑锋压住护臂，双脚落定，接点静止",
    })
    first, second = project["window_plan"]["windows"]
    first.update(end=7.5, shot_ids=["shot_0", "shot_1"],
                 closing_state="台缘僵持，剑锋已压住护臂",
                 exit_frame="frame_mid", risk="low", fallback_splits=[])
    first.pop("fallback", None)
    second.update(start=7.5, shot_ids=["shot_1", "shot_2", "shot_3"],
                  opening_state="台缘僵持，剑锋已压住护臂",
                  entry_frame="frame_mid", risk="low", fallback_splits=[])
    second.pop("fallback", None)
    second["carries"].update(costs=["cost_edge"], knowledge=["know_block"])
    return project


class WindowPlanTests(unittest.TestCase):
    def setUp(self):
        self.project = make_windowed_project()

    def rejects(self, change, fragment, base=None):
        changed = copy.deepcopy(self.project if base is None else base)
        change(changed)
        errors = plan.validate(changed)
        self.assertTrue(any(fragment in error for error in errors), errors)

    def test_valid_window_plan_renders_everywhere(self):
        self.assertEqual([], plan.validate(self.project))
        docs = plan.render(self.project)
        self.assertEqual(7, len(docs))
        board, frames, video, review = docs["03-storyboard.md"], docs["04-keyframes.md"], docs["05-video-prompts.md"], docs["06-review.md"]
        self.assertIn("## 生成窗口规划", board)
        self.assertIn("K1｜连续动作", board)
        self.assertIn("W1｜0–8 秒", board)
        self.assertIn("生成窗口：W1（0–8 秒）", board)
        self.assertIn("窗口入口、出口", frames)
        self.assertIn("## 生成窗口 1（成片 0–8 秒）", video)
        self.assertIn("### 剪辑点 1", video)
        self.assertIn("入口静帧：隔台对峙的静图", video)
        self.assertIn("接缝包：台缘僵持，剑刃缺口已开", video)
        self.assertIn("本窗生成风险高", video)
        self.assertIn("降级切点：12 秒", video)
        self.assertIn("返修卡：只改本窗时", video)
        self.assertIn("## 窗口规划", review)
        for leaked in ("W1", "W2", "K1", "K2", "C1", "C2", "frame_handoff", "frame_exit"):
            self.assertNotIn(leaked, video, leaked)

    def test_mid_shot_window_clips_cues_to_the_window(self):
        project = make_mid_shot_project()
        self.assertEqual([], plan.validate(project))
        docs = plan.render(project)
        video = docs["05-video-prompts.md"]
        board = docs["03-storyboard.md"]
        first, second = video.split("## 生成窗口 2", 1)
        self.assertIn("前半动作", first)
        self.assertNotIn("后半动作", first)
        self.assertIn("后半动作", second)
        self.assertNotIn("前半动作", second)
        self.assertIn("0–0.5秒：后半动作", second)
        self.assertIn("生成窗口：W1（0–7.5 秒）、W2（7.5–16 秒）", board)

    def test_mid_shot_window_needs_a_cue_boundary(self):
        def no_alignment(p):
            p["shots"][1]["execution"]["cues"] = [{"start": 4, "end": 8, "text": "整段动作"}]
        self.rejects(no_alignment, "须对齐该镜 cue 边界", make_mid_shot_project())

    def test_knots_must_stay_in_one_window(self):
        self.rejects(lambda p: p["window_plan"]["windows"][1].update(knot_ids=["K1", "K2"]),
                     "恰好落在一个窗口")
        self.rejects(lambda p: p["window_plan"]["windows"][0].update(knot_ids=["K1", "K2"]),
                     "恰好落在一个窗口")
        self.rejects(lambda p: p["window_plan"]["windows"][1].update(knot_ids=[]),
                     "恰好落在一个窗口")

    def test_windows_cover_in_order(self):
        self.rejects(lambda p: p["window_plan"]["windows"][1].update(start=9), "连续覆盖")
        self.rejects(lambda p: p["window_plan"]["windows"][0].update(end=7), "连续覆盖")
        self.rejects(lambda p: p["window_plan"]["windows"][1].update(end=15), "结束于总时长")

    def test_internal_boundary_needs_a_candidate(self):
        def no_candidates(p):
            p["window_plan"]["candidates"] = []
            p["window_plan"]["windows"][1].update(fallback_splits=[], risk="low")
            p["window_plan"]["windows"][1].pop("fallback")
        self.rejects(no_candidates, "内部边界须引用")
        self.rejects(lambda p: p["window_plan"]["candidates"][0].update(time_sec=7), "内部边界须引用")

    def test_post_layer_transition_cannot_be_a_window_seam(self):
        def post_seam(p):
            p["transitions"] = [{"id": "cut_post", "from_shot": "shot_1", "to_shot": "shot_2",
                                 "method": "match_action", "layer": "post",
                                 "keeps": ["人物位置"], "changes": ["景别"],
                                 "cut_condition": "剑锋越过画面中线时切", "route": "cut"}]
        self.rejects(post_seam, "窗口接缝不能用呈现层转场")

    def test_post_effect_cannot_cross_a_window_boundary(self):
        def post_vfx(p):
            p["vfx"] = [{"id": "vfx_post", "owner": "hero", "name": "速度线",
                         "layer": "post", "scale": "body", "function": "强化冲击方向",
                         "look": "沿剑势拉出细线", "lifecycle": {"release": "剑势起时出现", "fade": "收势时消失"},
                         "spends": "只存在于画面", "route": "one_pass",
                         "shot_ids": ["shot_1", "shot_2"]}]
        self.rejects(post_vfx, "呈现层特效不能跨窗口边界")

    def test_c_grade_boundary_carries_the_risk(self):
        def c_low(p):
            p["window_plan"]["candidates"][0]["grade"] = "C"
            p["window_plan"]["windows"][1].update(risk="low")
            p["window_plan"]["windows"][1].pop("fallback")
        self.rejects(c_low, "C 级边界由后窗承担风险")
        def c_no_split(p):
            p["window_plan"]["candidates"][0]["grade"] = "C"
            p["window_plan"]["windows"][1].update(fallback_splits=[])
        self.rejects(c_no_split, "高风险窗口须给可执行的降级切点")

    def test_max_length_and_knot_spans(self):
        self.rejects(lambda p: p["window_plan"]["capability"].update(max_window_sec=7), "关联簇跨度超过窗口上限")
        self.rejects(lambda p: p["window_plan"]["capability"].update(source="unknown"), "能力未知时不要写上限")

    def test_carries_must_include_crossing_items(self):
        self.rejects(lambda p: p["window_plan"]["windows"][1]["carries"].pop("costs"), "接缝包缺少跨界项")
        self.rejects(lambda p: p["window_plan"]["windows"][1]["carries"].pop("knowledge"), "接缝包缺少跨界项")
        self.rejects(lambda p: p["window_plan"]["windows"][1]["carries"].pop("attrition"), "接缝包缺少跨界项")
        self.rejects(lambda p: p["window_plan"]["windows"][1]["carries"].update(costs=["missing"]), "未知引用")

    def test_window_frames_must_align_and_share_boundary(self):
        self.rejects(lambda p: p["window_plan"]["windows"][1].update(entry_frame="frame_3"), "入口帧时刻须等于窗口起点")
        def duplicate_boundary(p):
            frame = copy.deepcopy(next(x for x in p["keyframes"] if x["id"] == "frame_handoff"))
            frame["id"] = "frame_handoff_other"
            p["keyframes"].append(frame)
            p["window_plan"]["windows"][1]["entry_frame"] = "frame_handoff_other"
        self.rejects(duplicate_boundary, "内部边界两侧须共用")
        self.rejects(lambda p: p["window_plan"]["windows"][0].update(entry_frame="frame_1"), "入口帧时刻须等于窗口起点")
        self.rejects(lambda p: p["window_plan"]["windows"][1].update(exit_frame="frame_3"), "出口帧时刻须等于窗口终点")
        def bad_role(p):
            next(x for x in p["keyframes"] if x["id"] == "frame_handoff")["role"] = "single"
        self.rejects(bad_role, "内部边界帧须为 handoff")

    def test_high_window_needs_fallback_and_valid_splits(self):
        self.rejects(lambda p: p["window_plan"]["windows"][1].pop("fallback"), "高风险窗口须写保底构图")
        self.rejects(lambda p: p["window_plan"]["windows"][1].update(fallback_splits=[]), "高风险窗口须给可执行的降级切点")
        self.rejects(lambda p: p["window_plan"]["windows"][1].update(fallback_splits=["C1"]), "降级切点须位于窗口内部")
        self.rejects(lambda p: p["window_plan"]["candidates"][1].update(grade="X"), "仅支持 A、B、C")
        def low_with_fallback(p):
            p["window_plan"]["windows"][0].update(fallback="不该有")
        self.rejects(low_with_fallback, "低风险窗口不登记保底构图")

    def test_window_text_hygiene(self):
        self.rejects(lambda p: p["window_plan"]["windows"][0].update(opening_state="双方隔台对峙22秒"),
                     "窗口状态不得含阿拉伯数字秒码")
        self.rejects(lambda p: p["window_plan"]["windows"][1]["carries"].update(text="承接 cost_edge 的缺口"),
                     "不得含内部 ID")
        self.rejects(lambda p: p["window_plan"]["windows"][1].update(fallback="改用保底，见 frame_handoff"),
                     "不得含内部 ID")

    def test_track_switch_needs_both_lines_carried(self):
        tracked = make_windowed_tracked()
        self.assertEqual([], plan.validate(tracked))
        self.rejects(lambda p: p["window_plan"]["windows"][1]["carries"].pop("tracks"),
                     "接缝包缺少跨界项", tracked)
        self.rejects(lambda p: p["window_plan"]["windows"][1]["carries"].update(tracks=["line_world"]),
                     "接缝包缺少跨界项", tracked)

    def test_form_must_not_cross_window_boundary(self):
        project = make_layered_project()
        project["schema_version"] = "1.4"
        add_exit_frame(project)
        # A new spanning pivotal beat lets one occlusion form touch both windows.
        project["beats"].append({"id": "beat_span", "start": 4, "end": 12,
                                 "actors": ["hero", "opponent"], "action": "青雾跨过台缘",
                                 "response": "体修退步", "result": "雾散后覆鳞",
                                 "requires": [], "marks": ["pivotal"]})
        project["shots"][1]["beat_ids"].append("beat_span")
        project["shots"][2]["beat_ids"].append("beat_span")
        project["forms"][0].update(shot_ids=["shot_1", "shot_2"], beat_id="beat_span")
        project["shots"][1]["asset_ids"].append("hero_form")
        project["keyframes"].append({"id": "frame_span_0", "shot_id": "shot_1", "time_sec": 6,
                                     "role": "prep", "asset_ids": ["arena", "hero", "opponent", "hero_form"],
                                     "state": "青纹刚起", "prompt": "青纹刚起的静图"})
        project["keyframes"].append({"id": "frame_span_1", "shot_id": "shot_2", "time_sec": 9,
                                     "role": "contact", "asset_ids": ["arena", "hero", "opponent", "hero_form"],
                                     "state": "青雾裹身", "prompt": "青雾裹身的静图"})
        project["keyframes"].append({"id": "frame_span_2", "shot_id": "shot_2", "time_sec": 11,
                                     "role": "result", "asset_ids": ["arena", "hero", "opponent", "hero_form"],
                                     "state": "雾散覆鳞", "prompt": "雾散覆鳞的静图"})
        project["window_plan"] = copy.deepcopy(make_windowed_project()["window_plan"])
        project["window_plan"]["windows"][0]["shot_ids"] = ["shot_0", "shot_1"]
        project["window_plan"]["windows"][1]["shot_ids"] = ["shot_2", "shot_3"]
        self.assertTrue(any("形态切换不得跨窗口边界" in error for error in plan.validate(project)),
                        plan.validate(project))

    def test_old_versions_are_rejected(self):
        for version in ("1.1", "1.2", "1.3"):
            project = make_craft_project()
            project["schema_version"] = version
            project["window_plan"] = copy.deepcopy(self.project["window_plan"])
            self.assertTrue(any("只接受 schema_version" in error for error in plan.validate(project)),
                            plan.validate(project))

    def test_capability_shape(self):
        self.rejects(lambda p: p["window_plan"]["capability"].update(source="guessed"), "仅支持")
        self.rejects(lambda p: p["window_plan"]["capability"].update(frame_conditioning="middle"), "仅支持")
        self.rejects(lambda p: p["window_plan"]["capability"].update(max_window_sec=0), "必须大于零")
        self.rejects(lambda p: p["window_plan"]["capability"].update(audio="yes"), "必须是布尔值")


if __name__ == "__main__":
    unittest.main()
