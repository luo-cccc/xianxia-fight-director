#!/usr/bin/env python3
"""Validate and render a platform-independent single-battle plan."""

import argparse
import copy
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unicodedata

EPS = 1e-6
EXECUTION_FIELDS = {"opening_state", "end_state", "camera", "effects", "sound", "cues"}
# 冒号时码要求冒号后为两位数（0:12、01:02:03），16:9 这类比例不算时刻；匹配前做 NFKC 归一化，全角数字同样受检
EXECUTION_TIME = re.compile(r"[0-9]+(?:\.[0-9]+)?\s*秒|(?<![0-9])[0-9]{1,2}(?:[:：][0-9]{2}){1,2}(?![0-9])(?:\.[0-9]+)?")
KINDS = {"character", "creature", "scene", "prop", "formation", "manifestation"}
ACTORS = {"character", "creature", "manifestation"}
ROOT = {"schema_version", "title", "duration_sec", "aspect_ratio", "style", "assumptions", "constraints", "design", "assets", "scene", "beats", "shots", "segments", "keyframes"}
VERSIONS = ("1.1", "1.2", "1.3", "1.4")
MARKS = ("pivotal", "breath", "adaptation")
ROLES = {"single", "prep", "contact", "result", "handoff"}
RISKS = {"low", "high"}
CONTACT_ROLES = ("prep", "contact", "result")
# 1.3：并行动作线、签名特效、形态切换与转场登记
LAYER_FIELDS = ("tracks", "vfx", "forms", "transitions")
# 1.4：按剧本关联规划生成窗口；窗口是生成单位，镜头是剪辑单位，制作段是叙事单位
WINDOW_PLAN = "window_plan"
KNOT_KINDS = {"action", "causal", "information", "form", "space", "scale", "sound", "performance", "other"}
CANDIDATE_GRADES = ("A", "B", "C")
CAPABILITY_SOURCES = {"user_stated", "verified", "unknown"}
FRAME_CONDITIONS = {"start", "end", "both", "none", "unknown"}
CARRY_KEYS = ("vfx", "forms", "costs", "knowledge", "tracks", "attrition")
TRACK_KINDS = {"world", "inner"}
LAYERS = {"world", "post"}
SCALES = {"micro", "body", "field", "heaven"}
# 硬切是默认，不登记；登记的都是需要额外设计与生成成本的转场
METHODS = {"occlusion", "match_graphic", "match_action", "whip", "eyeline", "sound_bridge",
           "medium_pass", "cloud_pass", "space_tear", "ink_bleed", "dissolve"}
CARRIED = {"occlusion", "medium_pass", "cloud_pass", "space_tear", "ink_bleed"}
FORM_METHODS = {"occlusion", "morph", "cut"}
VFX_ROUTES = {"one_pass", "composite", "asset"}
TRANSITION_ROUTES = {"cut", "composite", "bridge"}
LIFECYCLE = ("omen", "release", "travel", "contact", "result", "residue", "fade")
TRACK_LABELS = {"world": "世界线", "inner": "内景线"}
LAYER_LABELS = {"world": "世界内", "post": "呈现层"}
SCALE_LABELS = {"micro": "微观", "body": "个体", "field": "场域", "heaven": "天地"}
VFX_ROUTE_LABELS = {"one_pass": "随镜一次生成", "composite": "分层合成", "asset": "资产化复用"}
TRANSITION_ROUTE_LABELS = {"cut": "两侧分别生成后在切点拼接", "composite": "后期叠加遮挡或过渡层", "bridge": "首尾帧桥接生成"}
LIFECYCLE_LABELS = {"omen": "征兆", "release": "释放", "travel": "传播", "contact": "接触", "result": "结果", "residue": "残留", "fade": "消退"}
FORM_LABELS = {"occlusion": "遮挡切换", "morph": "连续形变", "cut": "切镜切换"}
METHOD_LABELS = {
    "occlusion": "遮挡转场", "match_graphic": "图形匹配", "match_action": "动作匹配",
    "whip": "甩镜", "eyeline": "视线转场", "sound_bridge": "声音先导", "medium_pass": "介质穿越",
    "cloud_pass": "穿云", "space_tear": "空间撕裂", "ink_bleed": "墨晕", "dissolve": "叠化",
}
KNOT_LABELS = {
    "action": "连续动作", "causal": "因果", "information": "信息", "form": "形态",
    "space": "动作线/空间", "scale": "尺度", "sound": "声音", "performance": "表演", "other": "其他",
}
CAPABILITY_LABELS = {"user_stated": "用户声明", "verified": "已核实", "unknown": "未知"}
FRAME_CONDITION_LABELS = {"start": "首帧", "end": "尾帧", "both": "首尾帧", "none": "无", "unknown": "未知"}


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"重复 JSON 键: {key}")
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f"非法 JSON 常量: {value}")


def load_project(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=_object, parse_constant=_constant)


def craft_checks(project, fail):
    """1.2 编舞要求。只检查可由结构证明的后果，不判断动作是否好看。"""
    beats = {x["id"]: x for x in project["beats"]}
    shots = {x["id"]: x for x in project["shots"]}
    marked = {mark: [x for x in project["beats"] if mark in x.get("marks", [])] for mark in MARKS}
    frames = project["keyframes"]

    for mark in MARKS:
        if not marked[mark]:
            fail("beats.marks", f"全场缺少 {mark} 标记节拍；1.2 要求关键转折、呼吸拍与对手变招各至少一处")

    for beat in marked["pivotal"]:
        inside = [x for x in frames if beat["start"] - EPS <= x["time_sec"] <= beat["end"] + EPS
                  and shots[x["shot_id"]].get("track") == beat.get("track")]
        times = {}
        for role in CONTACT_ROLES:
            picked = sorted(x["time_sec"] for x in inside if x["role"] == role)
            if not picked:
                fail("keyframes", f"关键转折 {beat['id']} 缺少 {role} 帧；决胜接点须有预备、接触与结果三帧")
            else:
                times[role] = picked
        # 同一角色可有多帧：全部预备帧早于全部接触帧，全部接触帧早于全部结果帧
        if len(times) == len(CONTACT_ROLES) and not (times["prep"][-1] < times["contact"][0] and times["contact"][-1] < times["result"][0]):
            fail("keyframes", f"关键转折 {beat['id']} 的预备、接触、结果帧时刻须严格递增")

    pivotal_windows = [(x["start"], x["end"]) for x in marked["pivotal"]]
    for beat in marked["breath"]:
        if "pivotal" in beat.get("marks", []):
            fail(f"beats.{beat['id']}.marks", "呼吸拍不能同时是关键转折")
        # 并行动作线各有节奏：只与同一动作线上的关键转折比较
        same_line = [(x["start"], x["end"]) for x in marked["pivotal"] if x.get("track") == beat.get("track")]
        for start, end in same_line:
            if beat["start"] < end - EPS and start < beat["end"] - EPS:
                fail(f"beats.{beat['id']}", "呼吸拍不得与关键转折窗口重叠；它是爆发前后被看清状态的停顿")
                break
    for beat in marked["adaptation"]:
        if not beat["requires"]:
            fail(f"beats.{beat['id']}.requires", "变招拍须登记它所回应的已完成前拍，否则不是适应而是预设剧本")

    segments = project["segments"]
    for previous, segment in zip(segments, segments[1:]):
        last = shots[previous["shot_ids"][-1]]
        boundary = last["end"]
        picked = [x for x in frames if x["role"] == "handoff" and abs(x["time_sec"] - boundary) <= EPS]
        if not picked:
            fail(f"segments.{segment['id']}", f"段界缺少 handoff 关键帧；{previous['id']} 与 {segment['id']} 的交接时刻须有可复现静图")
        elif not any(x["shot_id"] == last["id"] for x in picked):
            fail(f"segments.{segment['id']}", f"段界 handoff 帧须归属前段末镜 {last['id']}，作为末帧条件使用")

    if len(project["shots"]) > 1 and len({x["light"] for x in project["shots"]}) < 2:
        fail("shots.light", "全场光照登记完全相同；战局转折处须改变主光来源或归属")

    attrition = project["scene"]["attrition"]
    if pivotal_windows:
        earliest = min(start for start, _ in pivotal_windows)
        if not any(beats[x["from_beat"]]["end"] <= earliest + EPS for x in attrition if x["from_beat"] in beats):
            fail("scene.attrition", "没有任何战场痕迹在关键转折之前形成；地形须先被改变，才能约束后续选择")

    entries = project["cost"]
    if not any(x["irreversible"] for x in entries):
        fail("cost", "全部代价可撤销；全场至少一项不可逆支出")
    if len({x["owner"] for x in entries}) < 2:
        fail("cost", "代价集中在同一方；双方都要为本场付出可见支出")

    for item in project.get("knowledge", []):
        if "resolved_by" not in item:
            continue
        if item["resolved_by"] == item["from_beat"]:
            fail(f"knowledge.{item['id']}.resolved_by", "识破拍不能等于建立误判的同一拍")
        elif item["resolved_by"] in beats and item["from_beat"] in beats and beats[item["resolved_by"]]["start"] < beats[item["from_beat"]]["start"] - EPS:
            fail(f"knowledge.{item['id']}.resolved_by", "识破拍早于误判建立拍")


def validate(project):
    errors = []
    ids = set()

    def fail(path, text):
        errors.append(f"{path}: {text}")

    def obj(value, required, path, optional=()):
        if not isinstance(value, dict):
            fail(path, "必须是对象")
            return False
        missing = set(required) - value.keys()
        extra = value.keys() - set(required) - set(optional)
        if missing:
            fail(path, "缺少字段 " + ", ".join(sorted(missing)))
        if extra:
            fail(path, "未知字段 " + ", ".join(sorted(extra)))
        return not missing and not extra

    def text(value, path):
        if not isinstance(value, str) or not value.strip():
            fail(path, "必须是非空字符串")
            return False
        return True

    def number(value, path):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            fail(path, "必须是有限数字，不能是布尔值")
            return False
        try:
            valid = math.isfinite(value)
        except OverflowError:
            valid = False
        if not valid:
            fail(path, "必须是有限数字")
        return valid

    def strings(value, path, nonempty=False, unique=False):
        if not isinstance(value, list):
            fail(path, "必须是字符串数组")
            return False
        valid = True
        if nonempty and not value:
            fail(path, "数组不能为空")
            valid = False
        for i, item in enumerate(value):
            valid = text(item, f"{path}[{i}]") and valid
        if valid and unique and len(set(value)) != len(value):
            fail(path, "引用不得重复")
            valid = False
        return valid

    def identity(item, path):
        value = item.get("id")
        if text(value, path + ".id"):
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", value):
                fail(path + ".id", "ID格式错误")
            if value in ids:
                fail(path + ".id", "ID全场重复")
            ids.add(value)

    def group(name, fields, optional=()):
        value = project.get(name)
        if not isinstance(value, list) or not value:
            fail(name, "必须是非空对象数组")
            return []
        result = []
        for i, item in enumerate(value):
            path = f"{name}[{i}]"
            if obj(item, fields, path, optional):
                identity(item, path)
                result.append((path, item))
        return result

    if not obj(project, ROOT, "project", {"review", "cost", "knowledge"} | set(LAYER_FIELDS) | {WINDOW_PLAN}):
        return errors
    version = project["schema_version"]
    if version not in VERSIONS:
        fail("schema_version", "仅支持字符串版本 1.1、1.2、1.3 或 1.4；请升级旧版数据并编写镜头 execution 与段 prompt_context，不自动迁移自由文本")
        return errors
    craft = version in ("1.2", "1.3", "1.4")
    layered = version in ("1.3", "1.4")
    windowed = version == "1.4"
    if not craft:
        for key in ("cost", "knowledge"):
            if key in project:
                fail(key, "仅 1.2 支持该字段（1.3、1.4 继承）；1.1 数据不得混入 1.2 字段")
    if not layered:
        for key in LAYER_FIELDS:
            if key in project:
                fail(key, "仅 1.3 支持该字段（1.4 继承）；旧版数据须先用 migrate 升级到 1.4 再登记")
    if not windowed and WINDOW_PLAN in project:
        fail(WINDOW_PLAN, "仅 1.4 支持生成窗口规划；1.3 数据须先用 migrate 升级到 1.4")
    for key in ("title", "aspect_ratio", "style"):
        text(project[key], key)
    duration_ok = number(project["duration_sec"], "duration_sec")
    duration = project["duration_sec"] if duration_ok else 0
    if duration_ok and duration <= 0:
        fail("duration_sec", "必须大于零")
    for key in ("assumptions", "constraints"):
        strings(project[key], key)
    design = project["design"]
    if obj(design, {"goals", "rules", "turns", "outcome"}, "design", {"viewing_tasks"}):
        for key in ("goals", "rules", "turns"):
            strings(design[key], f"design.{key}", nonempty=True)
        text(design["outcome"], "design.outcome")
        if "viewing_tasks" in design:
            strings(design["viewing_tasks"], "design.viewing_tasks", nonempty=True)

    if "review" in project and obj(project["review"], {"scope", "fixed", "pending", "invalidated", "verification"}, "review", {"media_observations"}):
        text(project["review"]["scope"], "review.scope")
        text(project["review"]["verification"], "review.verification")
        for key in ("fixed", "pending", "invalidated"):
            strings(project["review"][key], "review." + key)
        if "media_observations" in project["review"]:
            observations = project["review"]["media_observations"]
            if not isinstance(observations, list):
                fail("review.media_observations", "必须是对象数组")
            else:
                for i, observation in enumerate(observations):
                    path = f"review.media_observations[{i}]"
                    if obj(observation, {"source", "kind", "observation", "limitations"}, path):
                        for key, value in observation.items():
                            text(value, path + "." + key)
                        if not isinstance(observation["kind"], str) or observation["kind"] not in {"image", "video", "audio"}:
                            fail(path + ".kind", "仅支持 image、video、audio")

    assets = group("assets", {"id", "kind", "name", "anchors", "states", "image_prompt"}, {"reference"})
    asset_map = {}
    printed = []  # (value, path)：资产名称、锚点与参考绑定会原样进入执行稿，与执行文本同样受检
    for path, item in assets:
        if isinstance(item["id"], str):
            asset_map[item["id"]] = item
        if not isinstance(item["kind"], str) or item["kind"] not in KINDS:
            fail(path + ".kind", "未知资产类型")
        for key in ("name", "image_prompt"):
            text(item[key], path + "." + key)
        if strings(item["anchors"], path + ".anchors", nonempty=True):
            printed += [(x, f"{path}.anchors[{i}]") for i, x in enumerate(item["anchors"])]
        strings(item["states"], path + ".states")
        printed.append((item["name"], path + ".name"))
        if "reference" in item and obj(item["reference"], {"source", "control", "keep", "exclude"}, path + ".reference"):
            for key, value in item["reference"].items():
                text(value, path + ".reference." + key)
                printed.append((value, path + ".reference." + key))

    scene = project["scene"]
    scene_fields = {"asset_id", "geography", "attrition"} if craft else {"asset_id", "geography"}
    if obj(scene, scene_fields, "scene"):
        text(scene["geography"], "scene.geography")
        if text(scene["asset_id"], "scene.asset_id") and asset_map.get(scene["asset_id"], {}).get("kind") != "scene":
            fail("scene.asset_id", "须引用场景资产")
        if craft:
            marks = scene["attrition"]
            if not isinstance(marks, list) or not marks:
                fail("scene.attrition", "1.2 须登记非空战场累积痕迹数组")
            else:
                for i, item in enumerate(marks):
                    path = f"scene.attrition[{i}]"
                    if obj(item, {"id", "mark", "from_beat", "consequence"}, path):
                        identity(item, path)
                        for key in ("mark", "from_beat", "consequence"):
                            text(item[key], path + "." + key)

    if errors:
        return errors

    def execution_text(value, path, kind="执行文本"):
        if text(value, path) and EXECUTION_TIME.search(unicodedata.normalize("NFKC", value)):
            fail(path, f"{kind}不得含阿拉伯数字秒码或冒号时码；时刻只允许写在 cues.start / cues.end 数值字段。计数（如“退三步”“两柄戟”）不受限制")

    for value, path in printed:
        if isinstance(value, str) and EXECUTION_TIME.search(unicodedata.normalize("NFKC", value)):
            fail(path, "进入执行稿的资产文本不得含阿拉伯数字秒码或冒号时码")
    layer_texts = list(printed)  # (value, path)：会进入可复制执行稿的文本，统一做 ID 扫描
    track_map = {}
    if layered and "tracks" in project:
        for path, item in group("tracks", {"id", "kind", "name", "time_relation"}):
            execution_text(item["name"], path + ".name", "动作线名称")
            execution_text(item["time_relation"], path + ".time_relation", "动作线时间关系")
            layer_texts += [(item["name"], path + ".name"), (item["time_relation"], path + ".time_relation")]
            if not isinstance(item["kind"], str) or item["kind"] not in TRACK_KINDS:
                fail(path + ".kind", "仅支持 world、inner")
            elif isinstance(item["id"], str):
                track_map[item["id"]] = item
        kinds = [x["kind"] for x in track_map.values()]
        if kinds.count("world") != 1:
            fail("tracks", "须恰好登记一条 world 世界线；内景、识海、梦境等意识空间登记为 inner")
        if "inner" not in kinds:
            fail("tracks", "只有世界线时省略 tracks；单线战斗不需要动作线登记")
    if errors:
        return errors
    tracked = bool(track_map)

    beat_fields = {"id", "start", "end", "actors", "action", "response", "result", "requires"}
    shot_fields = {"id", "start", "end", "beat_ids", "asset_ids", "opening_state", "camera", "effects", "sound", "end_state", "execution"}
    frame_fields = {"id", "shot_id", "time_sec", "asset_ids", "state", "prompt"}
    beat_optional = {"marks"} if craft else set()
    shot_optional = {"fallback"} if craft else set()
    if craft:
        shot_fields |= {"light", "risk"}
        frame_fields |= {"role"}
    if layered:
        beat_optional |= {"track"}
        shot_optional |= {"track", "outer_state"}
    beats = group("beats", beat_fields, beat_optional)
    shots = group("shots", shot_fields, shot_optional)
    segments = group("segments", {"id", "shot_ids", "opening_state", "closing_state", "prompt_context"})
    frames = group("keyframes", frame_fields)
    beat_map = {x["id"]: x for _, x in beats if isinstance(x["id"], str)}
    shot_map = {x["id"]: x for _, x in shots if isinstance(x["id"], str)}
    ranges = {}

    def interval(item, path):
        start_ok = number(item["start"], path + ".start")
        end_ok = number(item["end"], path + ".end")
        if start_ok and end_ok:
            start, end = item["start"], item["end"]
            if start < -EPS or end <= start or end > duration + EPS:
                fail(path, "时间须满足 0 <= start < end <= duration_sec")
            elif isinstance(item["id"], str):
                ranges[item["id"]] = (start, end)

    def refs(value, mapping, path, nonempty=True, actor=False):
        if not strings(value, path, nonempty=nonempty, unique=True):
            return
        for ref in value:
            if ref not in mapping:
                fail(path, "未知引用 " + ref)
            elif actor and mapping[ref]["kind"] not in ACTORS:
                fail(path, "行动主体类型不符 " + ref)

    for path, item in beats:
        interval(item, path)
        refs(item["actors"], asset_map, path + ".actors", actor=True)
        refs(item["requires"], beat_map, path + ".requires", nonempty=False)
        for key in ("action", "response", "result"):
            text(item[key], path + "." + key)
        if "marks" in item and strings(item["marks"], path + ".marks", nonempty=True, unique=True):
            for mark in item["marks"]:
                if mark not in MARKS:
                    fail(path + ".marks", "未知标记 " + mark + "；仅支持 " + ", ".join(MARKS))
    for path, item in shots:
        interval(item, path)
        refs(item["beat_ids"], beat_map, path + ".beat_ids")
        refs(item["asset_ids"], asset_map, path + ".asset_ids")
        for key in ("opening_state", "camera", "effects", "sound", "end_state"):
            text(item[key], path + "." + key)
        if craft:
            text(item["light"], path + ".light")
            if not isinstance(item["risk"], str) or item["risk"] not in RISKS:
                fail(path + ".risk", "仅支持 low、high")
            elif item["risk"] == "high":
                if "fallback" not in item:
                    fail(path + ".fallback", "高风险镜头须预授权保底构图")
                else:
                    text(item["fallback"], path + ".fallback")
            elif "fallback" in item:
                fail(path + ".fallback", "低风险镜头不登记保底构图；需要保底说明本镜应标 high")
        if layered:
            if tracked:
                if not isinstance(item.get("track"), str) or item["track"] not in track_map:
                    fail(path + ".track", "登记 tracks 后每个镜头须归属一条已登记动作线")
                elif track_map[item["track"]]["kind"] == "inner":
                    if "outer_state" not in item:
                        fail(path + ".outer_state", "内景镜头须登记同一时刻外层身体与世界状态；内景期间外界不暂停")
                    else:
                        text(item["outer_state"], path + ".outer_state")
                elif "outer_state" in item:
                    fail(path + ".outer_state", "世界线镜头本身就是外层状态，不登记 outer_state")
            else:
                for key in ("track", "outer_state"):
                    if key in item:
                        fail(path + "." + key, "未登记 tracks 时不得使用该字段")
    if layered:
        for path, item in beats:
            if tracked:
                if not isinstance(item.get("track"), str) or item["track"] not in track_map:
                    fail(path + ".track", "登记 tracks 后每个节拍须归属一条已登记动作线")
            elif "track" in item:
                fail(path + ".track", "未登记 tracks 时不得使用该字段")
        if tracked and not errors:
            for path, shot in shots:
                for ref in shot["beat_ids"]:
                    if beat_map[ref]["track"] != shot["track"]:
                        fail(path + ".beat_ids", f"节拍 {ref} 与本镜不在同一动作线；外层在内景期间的变化写入 outer_state")
    if errors:
        return errors

    execution_fields = EXECUTION_FIELDS | {"light"} if craft else EXECUTION_FIELDS
    for path, shot in shots:
        execution_path = path + ".execution"
        execution = shot["execution"]
        if craft and isinstance(shot.get("fallback"), str):
            execution_text(shot["fallback"], path + ".fallback")
        if not obj(execution, execution_fields, execution_path):
            continue
        for key in execution_fields - {"cues"}:
            execution_text(execution[key], execution_path + "." + key)
        cues = execution["cues"]
        if not isinstance(cues, list) or not cues:
            fail(execution_path + ".cues", "必须是非空对象数组")
            continue
        cursor = shot["start"]
        broken = False  # 某条 cue 结构错误后不再检查连续覆盖，避免连锁误报
        for i, cue in enumerate(cues):
            cue_path = f"{execution_path}.cues[{i}]"
            if not obj(cue, {"start", "end", "text"}, cue_path):
                broken = True
                continue
            execution_text(cue["text"], cue_path + ".text")
            start_ok = number(cue["start"], cue_path + ".start")
            end_ok = number(cue["end"], cue_path + ".end")
            if not (start_ok and end_ok):
                broken = True
            elif not broken:
                start, end = cue["start"], cue["end"]
                if end <= start or start < shot["start"] - EPS or end > shot["end"] + EPS:
                    fail(cue_path, "cue 须满足所属镜头 start <= cue.start < cue.end <= 镜头 end，不得超镜")
                if abs(start - cursor) > EPS:
                    fail(cue_path + ".start", "cues 须按序连续覆盖所属镜头，不得有缺口、重叠或顺序错误")
                cursor = end
        if not broken and abs(cursor - shot["end"]) > EPS:
            fail(execution_path + ".cues", "cues 须连续覆盖到所属镜头终点")

    # 状态连续按动作线检查：无 tracks 时全片是一条线；有 tracks 时各线内相邻镜头接续，
    # 内景结束后回到的世界线镜头须接上最后一个内景镜头登记的外层状态。
    last_on = {}
    outer_pending = None
    for path, shot in shots:
        line = shot.get("track") if tracked else None
        previous = last_on.get(line)
        if previous is not None:
            if previous["end_state"] != shot["opening_state"] and not (tracked and track_map[line]["kind"] == "world" and outer_pending is not None):
                fail(path + ".opening_state", "与前镜 end_state 必须逐字一致（同一动作线内的前镜；原世界状态，不含机位）")
            previous_execution, execution = previous["execution"], shot["execution"]
            if isinstance(previous_execution, dict) and isinstance(execution, dict):
                if "end_state" in previous_execution and "opening_state" in execution and previous_execution["end_state"] != execution["opening_state"]:
                    if not (tracked and track_map[line]["kind"] == "world" and outer_pending is not None):
                        fail(path + ".execution.opening_state", "与前镜 execution.end_state 必须逐字一致（同一动作线内的前镜）")
        if tracked and track_map[line]["kind"] == "inner":
            outer_pending = shot.get("outer_state")
        elif outer_pending is not None:
            if outer_pending != shot["opening_state"]:
                fail(path + ".opening_state", "回到世界线的首镜须与最后一个内景镜头的 outer_state 逐字一致；外层在内景期间已经变化")
            outer_pending = None
        last_on[line] = shot

    for path, item in beats:
        if isinstance(item["requires"], list):
            for ref in item["requires"]:
                if not isinstance(ref, str):
                    continue
                if ref == item["id"]:
                    fail(path + ".requires", "不得自依赖")
                if ref in ranges and isinstance(item["id"], str) and item["id"] in ranges and ranges[ref][1] > item["start"] + EPS:
                    fail(path + ".requires", "前置节拍尚未完成 " + ref)

    pending = {item["id"]: set(item["requires"]) for _, item in beats}
    ready = [key for key, dependencies in pending.items() if not dependencies]
    dependents = {key: [] for key in pending}
    for key, dependencies in pending.items():
        for dependency in dependencies:
            dependents[dependency].append(key)
    resolved = 0
    while ready:
        key = ready.pop()
        resolved += 1
        for dependent in dependents[key]:
            pending[dependent].discard(key)
            if not pending[dependent]:
                ready.append(dependent)
    if resolved != len(pending):
        fail("beats.requires", "完成依赖存在循环")

    cursor = 0
    for path, item in shots:
        if not isinstance(item["id"], str) or item["id"] not in ranges:
            continue
        if abs(item["start"] - cursor) > EPS:
            fail(path + ".start", "主镜头时间轴有缺口、重叠或顺序错误")
        cursor = item["end"]
    if shots and abs(cursor - duration) > EPS:
        fail("shots", "主镜头须覆盖到总时长")

    coverage = {key: [] for key in beat_map}
    for path, shot in shots:
        if not isinstance(shot["id"], str) or shot["id"] not in ranges or not isinstance(shot["beat_ids"], list):
            continue
        for ref in shot["beat_ids"]:
            if not isinstance(ref, str) or ref not in ranges or ref not in beat_map:
                continue
            start = max(shot["start"], beat_map[ref]["start"])
            end = min(shot["end"], beat_map[ref]["end"])
            if end <= start:
                fail(path + ".beat_ids", "节拍与镜头没有正时长交集 " + ref)
            else:
                coverage[ref].append((start, end))
    for ref, windows in coverage.items():
        if ref not in ranges:
            continue
        cursor = ranges[ref][0]
        for start, end in sorted(windows):
            if start > cursor + EPS:
                break
            cursor = max(cursor, end)
        if cursor < ranges[ref][1] - EPS:
            fail("beats." + ref, "引用镜头未完整覆盖节拍")

    assigned = []
    previous = previous_line = None
    for path, item in segments:
        refs(item["shot_ids"], shot_map, path + ".shot_ids")
        text(item["opening_state"], path + ".opening_state")
        text(item["closing_state"], path + ".closing_state")
        execution_text(item["prompt_context"], path + ".prompt_context")
        seq = item["shot_ids"]
        if isinstance(seq, list) and seq and all(isinstance(x, str) and x in shot_map for x in seq):
            assigned.extend(seq)
            if item["opening_state"] != shot_map[seq[0]]["opening_state"]:
                fail(path + ".opening_state", f"与首镜 {seq[0]} 的外层 opening_state 不一致；段状态对的是外层完整世界状态，不是 execution 的精简状态")
            if item["closing_state"] != shot_map[seq[-1]]["end_state"]:
                fail(path + ".closing_state", f"与末镜 {seq[-1]} 的外层 end_state 不一致；段状态对的是外层完整世界状态，不是 execution 的精简状态")
        # 有 tracks 时段界可能跨动作线；跨线接续由镜头级按线检查保证，同线段界仍须逐字一致
        known = isinstance(seq, list) and seq and all(isinstance(x, str) and x in shot_map for x in seq)
        line = shot_map[seq[0]].get("track") if known else None
        if previous is not None and (not tracked or line == previous_line) and previous != item["opening_state"]:
            fail(path + ".opening_state", "与前段终态不一致")
        previous = item["closing_state"]
        previous_line = shot_map[seq[-1]].get("track") if known else None
    if assigned != [x["id"] for _, x in shots]:
        fail("segments", "须按顺序恰好分配全部镜头一次")

    frame_counts = {key: 0 for key in shot_map}
    for path, item in frames:
        refs(item["asset_ids"], asset_map, path + ".asset_ids")
        text(item["state"], path + ".state")
        execution_text(item["prompt"], path + ".prompt", "静图提示词")
        if craft and (not isinstance(item["role"], str) or item["role"] not in ROLES):
            fail(path + ".role", "仅支持 " + ", ".join(sorted(ROLES)))
        numeric = number(item["time_sec"], path + ".time_sec")
        if not text(item["shot_id"], path + ".shot_id"):
            continue
        shot = shot_map.get(item["shot_id"])
        if shot is None:
            fail(path + ".shot_id", "未知镜头引用")
            continue
        frame_counts[item["shot_id"]] += 1
        if numeric and item["shot_id"] in ranges and not shot["start"] - EPS <= item["time_sec"] <= shot["end"] + EPS:
            fail(path + ".time_sec", "关键帧超出所属镜头")
        if isinstance(item["asset_ids"], list) and isinstance(shot["asset_ids"], list):
            for ref in item["asset_ids"]:
                if ref not in shot["asset_ids"]:
                    fail(path + ".asset_ids", "资产未在本镜登记 " + str(ref))
    boundary_shots = set()
    if craft:
        seq = [x for _, x in segments]
        for previous in seq[:-1]:
            if isinstance(previous.get("shot_ids"), list) and previous["shot_ids"] and isinstance(previous["shot_ids"][-1], str):
                boundary_shots.add(previous["shot_ids"][-1])
    for key, count in frame_counts.items():
        if not count:
            extra = "；该镜是段界所在的前段末镜，除本镜至少一帧外还须有一张 handoff 交接帧" if key in boundary_shots else ""
            fail("keyframes", "镜头缺少关键帧 " + key + extra)

    if craft:
        marks = project["scene"].get("attrition")
        if isinstance(marks, list):
            for i, item in enumerate(marks):
                if isinstance(item, dict) and isinstance(item.get("from_beat"), str) and item["from_beat"] not in beat_map:
                    fail(f"scene.attrition[{i}].from_beat", "未知节拍引用")
        entries = project.get("cost")
        if not isinstance(entries, list) or not entries:
            fail("cost", "1.2 须登记非空代价账目；战斗不得零支出收场")
        else:
            for i, item in enumerate(entries):
                path = f"cost[{i}]"
                if obj(item, {"id", "owner", "item", "from_beat", "irreversible", "consequence"}, path):
                    identity(item, path)
                    for key in ("item", "consequence"):
                        text(item[key], path + "." + key)
                    if text(item["owner"], path + ".owner") and asset_map.get(item["owner"], {}).get("kind") not in ACTORS:
                        fail(path + ".owner", "须引用行动主体资产")
                    if text(item["from_beat"], path + ".from_beat") and item["from_beat"] not in beat_map:
                        fail(path + ".from_beat", "未知节拍引用")
                    if not isinstance(item["irreversible"], bool):
                        fail(path + ".irreversible", "必须是布尔值")
        if "knowledge" in project:
            entries = project["knowledge"]
            if not isinstance(entries, list) or not entries:
                fail("knowledge", "登记时须为非空数组；无信息差则省略该字段")
            else:
                for i, item in enumerate(entries):
                    path = f"knowledge[{i}]"
                    if obj(item, {"id", "holder", "belief", "truth", "from_beat", "cue"}, path, {"resolved_by"}):
                        identity(item, path)
                        for key in ("belief", "truth", "cue"):
                            text(item[key], path + "." + key)
                        if text(item["holder"], path + ".holder") and asset_map.get(item["holder"], {}).get("kind") not in ACTORS:
                            fail(path + ".holder", "须引用行动主体资产")
                        for key in ("from_beat", "resolved_by"):
                            if key in item and text(item[key], path + "." + key) and item[key] not in beat_map:
                                fail(path + "." + key, "未知节拍引用")
                        if item["belief"] == item["truth"]:
                            fail(path + ".truth", "所知与实际逐字相同即无信息差；删除该项或写出真实差异")
    if layered and not errors:
        order = {x["id"]: i for i, (_, x) in enumerate(shots)}
        cost_map = {x["id"]: x for x in project.get("cost", []) if isinstance(x, dict) and isinstance(x.get("id"), str)}
        pivotal = {x["id"] for _, x in beats if "pivotal" in x.get("marks", [])}

        def shot_refs(value, path):
            if not strings(value, path, nonempty=True, unique=True):
                return []
            missing = [x for x in value if x not in shot_map]
            for ref in missing:
                fail(path, "未知镜头引用 " + ref)
            return [] if missing else sorted(value, key=order.get)

        if "vfx" in project:
            for path, item in group("vfx", {"id", "owner", "name", "layer", "scale", "function", "look", "lifecycle", "spends", "route", "shot_ids"}, {"asset_id"}):
                for key in ("function", "spends"):
                    text(item[key], path + "." + key)
                execution_text(item["name"], path + ".name", "特效名称")
                execution_text(item["look"], path + ".look", "特效外观")
                layer_texts += [(item["name"], path + ".name"), (item["look"], path + ".look")]
                if text(item["owner"], path + ".owner") and item["owner"] not in asset_map:
                    fail(path + ".owner", "须引用资产；特效必须有归属")
                if not isinstance(item["layer"], str) or item["layer"] not in LAYERS:
                    fail(path + ".layer", "仅支持 world、post")
                if not isinstance(item["scale"], str) or item["scale"] not in SCALES:
                    fail(path + ".scale", "仅支持 " + ", ".join(sorted(SCALES)))
                if not isinstance(item["route"], str) or item["route"] not in VFX_ROUTES:
                    fail(path + ".route", "仅支持 " + ", ".join(sorted(VFX_ROUTES)))
                elif item["route"] == "asset":
                    ref = item.get("asset_id")
                    if not isinstance(ref, str) or ref not in asset_map:
                        fail(path + ".asset_id", "资产化复用的特效须引用已登记资产，保证跨镜外观一致")
                elif "asset_id" in item:
                    fail(path + ".asset_id", "仅 route 为 asset 时登记 asset_id")
                phases = item["lifecycle"]
                if obj(phases, {"release"}, path + ".lifecycle", set(LIFECYCLE) - {"release"}):
                    for key, value in phases.items():
                        execution_text(value, path + ".lifecycle." + key, "特效阶段")
                        layer_texts.append((value, path + ".lifecycle." + key))
                    if item["layer"] == "post":
                        for key in ("contact", "residue"):
                            if key in phases:
                                fail(path + ".lifecycle." + key, "呈现层特效不进入世界，不能接触或留下残留；会改变世界的效果登记为 world")
                    elif "residue" not in phases and "fade" not in phases:
                        fail(path + ".lifecycle", "世界内特效须写残留或消退，说明它离开画面后留下什么")
                shot_refs(item["shot_ids"], path + ".shot_ids")

        form_shots = {}
        if "forms" in project:
            for path, item in group("forms", {"id", "actor", "from_asset", "to_asset", "beat_id", "shot_ids", "method", "ladder", "shared_anchors", "cost_id", "duration", "exit"}):
                for key in ("duration", "exit"):
                    text(item[key], path + "." + key)
                if text(item["actor"], path + ".actor") and asset_map.get(item["actor"], {}).get("kind") not in ACTORS:
                    fail(path + ".actor", "须引用行动主体资产")
                pair = []
                for key in ("from_asset", "to_asset"):
                    if text(item[key], path + "." + key):
                        if item[key] not in asset_map:
                            fail(path + "." + key, "未知资产引用")
                        else:
                            pair.append(asset_map[item[key]])
                if len(pair) == 2 and pair[0]["id"] == pair[1]["id"]:
                    fail(path + ".to_asset", "形态前后须是两套资产；同一资产内的状态变化写 states")
                if strings(item["shared_anchors"], path + ".shared_anchors", nonempty=True, unique=True):
                    layer_texts += [(x, f"{path}.shared_anchors[{i}]") for i, x in enumerate(item["shared_anchors"])]
                if isinstance(item["shared_anchors"], list) and all(isinstance(x, str) for x in item["shared_anchors"]) and len(pair) == 2:
                    for anchor in item["shared_anchors"]:
                        if anchor not in pair[0]["anchors"] or anchor not in pair[1]["anchors"]:
                            fail(path + ".shared_anchors", f"身份锚点须逐字出现在前后两套资产的 anchors 中：{anchor}")
                if strings(item["ladder"], path + ".ladder", nonempty=True):
                    for i, step in enumerate(item["ladder"]):
                        execution_text(step, f"{path}.ladder[{i}]", "形态阶梯")
                        layer_texts.append((step, f"{path}.ladder[{i}]"))
                    if len(item["ladder"]) < 3:
                        fail(path + ".ladder", "形态切换至少写征兆、覆盖或切换、落定三级")
                if text(item["beat_id"], path + ".beat_id"):
                    if item["beat_id"] not in beat_map:
                        fail(path + ".beat_id", "未知节拍引用")
                    elif item["beat_id"] not in pivotal:
                        fail(path + ".beat_id", "变身是战局转折，所在节拍须标 pivotal，并有预备、接触、结果三帧")
                if text(item["cost_id"], path + ".cost_id"):
                    entry = cost_map.get(item["cost_id"])
                    if entry is None:
                        fail(path + ".cost_id", "未知代价引用；变身须有代价")
                    elif entry.get("owner") != item["actor"]:
                        fail(path + ".cost_id", "变身代价须由变身者本人支出")
                listed = shot_refs(item["shot_ids"], path + ".shot_ids")
                for ref in listed:
                    if isinstance(item["beat_id"], str) and item["beat_id"] not in shot_map[ref]["beat_ids"]:
                        fail(path + ".shot_ids", f"镜头 {ref} 未引用变身节拍")
                    for asset in pair:
                        if asset["id"] not in shot_map[ref]["asset_ids"]:
                            fail(path + ".shot_ids", f"切换镜头 {ref} 须同时登记前后两套资产 {asset['id']}")
                if not isinstance(item["method"], str) or item["method"] not in FORM_METHODS:
                    fail(path + ".method", "仅支持 " + ", ".join(sorted(FORM_METHODS)))
                elif item["method"] == "morph":
                    for ref in listed:
                        if shot_map[ref].get("risk") != "high":
                            fail(path + ".method", f"连续形变难以保持身份，镜头 {ref} 须标 high 并给保底构图")
                for ref in listed:
                    form_shots[ref] = item

        if "transitions" in project:
            entries = group("transitions", {"id", "from_shot", "to_shot", "method", "layer", "keeps", "changes", "cut_condition", "route"}, {"occluder"})
            limit = 2 * max(1, math.ceil(duration / 30))
            if len(entries) > limit:
                fail("transitions", f"登记转场过密：本片最多 {limit} 处；默认硬切，特效转场只用在需要被记住的空间或状态跳变处")
            used = set()
            for path, item in entries:
                execution_text(item["cut_condition"], path + ".cut_condition", "切点条件")
                layer_texts.append((item["cut_condition"], path + ".cut_condition"))
                for key in ("keeps", "changes"):
                    if strings(item[key], path + "." + key, nonempty=True):
                        for i, value in enumerate(item[key]):
                            execution_text(value, f"{path}.{key}[{i}]", "转场说明")
                            layer_texts.append((value, f"{path}.{key}[{i}]"))
                ends = [item[key] for key in ("from_shot", "to_shot") if text(item[key], path + "." + key)]
                if len(ends) == 2:
                    if any(x not in shot_map for x in ends):
                        fail(path, "未知镜头引用")
                        continue
                    if order[ends[1]] != order[ends[0]] + 1:
                        fail(path + ".to_shot", "转场只发生在相邻镜头之间的切点上")
                    if ends[0] in used:
                        fail(path + ".from_shot", "同一切点只登记一种转场")
                    used.add(ends[0])
                method = item["method"]
                if not isinstance(method, str) or method not in METHODS:
                    fail(path + ".method", "仅支持 " + ", ".join(sorted(METHODS)) + "；硬切是默认，不登记")
                    continue
                if method in CARRIED:
                    if "occluder" not in item:
                        fail(path + ".occluder", "载体型转场须写清遮挡物或穿越介质及其来源")
                    else:
                        execution_text(item["occluder"], path + ".occluder", "遮挡物")
                        layer_texts.append((item["occluder"], path + ".occluder"))
                elif "occluder" in item:
                    fail(path + ".occluder", "仅遮挡、介质穿越、穿云、空间撕裂、墨晕登记遮挡物")
                if not isinstance(item["layer"], str) or item["layer"] not in LAYERS:
                    fail(path + ".layer", "仅支持 world、post")
                elif item["layer"] == "post" and len(ends) == 2:
                    a, b = shot_map[ends[0]], shot_map[ends[1]]
                    if tracked and a["track"] != b["track"]:
                        fail(path + ".layer", "跨动作线的进出是世界内事件（入定、神识离体），不能写成呈现层转场")
                    if ends[0] in form_shots and form_shots[ends[0]] is form_shots.get(ends[1]):
                        fail(path + ".layer", "形态切换内部的遮挡须是世界内的光、雾、茧或法相，不能用呈现层转场替代变身过程")
                if not isinstance(item["route"], str) or item["route"] not in TRANSITION_ROUTES:
                    fail(path + ".route", "仅支持 " + ", ".join(sorted(TRANSITION_ROUTES)))
                elif item["route"] == "bridge" and len(ends) == 2:
                    for ref in ends:
                        if shot_map[ref].get("risk") != "high":
                            fail(path + ".route", f"首尾帧桥接不保证可用，两侧镜头 {ref} 须标 high 并给保底构图")

    def check_window_plan():
        wp = project[WINDOW_PLAN]
        if not obj(wp, {"capability", "knots", "candidates", "windows"}, "window_plan", {"notes"}):
            return
        if "notes" in wp:
            text(wp["notes"], "window_plan.notes")

        cap = wp["capability"]
        max_window = None
        if obj(cap, {"source"}, "window_plan.capability",
               {"max_window_sec", "arbitrary_start", "frame_conditioning", "internal_cuts", "audio"}):
            source = cap["source"]
            if not isinstance(source, str) or source not in CAPABILITY_SOURCES:
                fail("window_plan.capability.source", "仅支持 " + ", ".join(sorted(CAPABILITY_SOURCES)))
            if "max_window_sec" in cap:
                if number(cap["max_window_sec"], "window_plan.capability.max_window_sec"):
                    if cap["max_window_sec"] <= 0:
                        fail("window_plan.capability.max_window_sec", "必须大于零")
                    else:
                        max_window = cap["max_window_sec"]
                    if source == "unknown":
                        fail("window_plan.capability.max_window_sec", "能力未知时不要写上限；省略它并按切点阶梯规划")
            for key in ("arbitrary_start", "internal_cuts", "audio"):
                if key in cap and not isinstance(cap[key], bool):
                    fail("window_plan.capability." + key, "必须是布尔值")
            if "frame_conditioning" in cap and (not isinstance(cap["frame_conditioning"], str) or cap["frame_conditioning"] not in FRAME_CONDITIONS):
                fail("window_plan.capability.frame_conditioning", "仅支持 " + ", ".join(sorted(FRAME_CONDITIONS)))

        knots = wp["knots"]
        knot_map = {}
        if not isinstance(knots, list) or not knots:
            fail("window_plan.knots", "登记 window_plan 时须为非空关联簇数组；每场至少标出真正会被拆坏的内容")
        else:
            for i, item in enumerate(knots):
                path = f"window_plan.knots[{i}]"
                if not obj(item, {"id", "shot_ids", "kind", "why"}, path):
                    continue
                identity(item, path)
                refs(item["shot_ids"], shot_map, path + ".shot_ids")
                if not isinstance(item["kind"], str) or item["kind"] not in KNOT_KINDS:
                    fail(path + ".kind", "仅支持 " + ", ".join(sorted(KNOT_KINDS)))
                text(item["why"], path + ".why")
                if isinstance(item["id"], str):
                    knot_map[item["id"]] = item

        candidates = wp["candidates"]
        cand_map = {}
        if not isinstance(candidates, list):
            fail("window_plan.candidates", "必须是对象数组；无内部边界时可为空数组")
        else:
            for i, item in enumerate(candidates):
                path = f"window_plan.candidates[{i}]"
                if not obj(item, {"id", "time_sec", "shot_id", "grade", "reason"}, path, {"seam"}):
                    continue
                identity(item, path)
                moment_ok = number(item["time_sec"], path + ".time_sec")
                shot_ok = text(item["shot_id"], path + ".shot_id")
                if shot_ok and item["shot_id"] not in shot_map:
                    fail(path + ".shot_id", "未知镜头引用")
                elif moment_ok and shot_ok:
                    shot = shot_map[item["shot_id"]]
                    if not shot["start"] - EPS <= item["time_sec"] <= shot["end"] + EPS:
                        fail(path + ".time_sec", "候选时刻须位于所属镜头闭区间")
                if not isinstance(item["grade"], str) or item["grade"] not in CANDIDATE_GRADES:
                    fail(path + ".grade", "仅支持 A、B、C；X 类位置不登记为候选")
                text(item["reason"], path + ".reason")
                if "seam" in item:
                    text(item["seam"], path + ".seam")
                if isinstance(item["id"], str) and moment_ok:
                    cand_map[item["id"]] = item

        frames_map = {x["id"]: x for _, x in frames if isinstance(x.get("id"), str)}
        shot_order = [x for _, x in shots]
        transition_pairs = {(x.get("from_shot"), x.get("to_shot")) for x in project.get("transitions", []) if isinstance(x, dict)}
        cost_map = {x["id"]: x for x in project.get("cost", []) if isinstance(x, dict) and isinstance(x.get("id"), str)}
        knowledge_map = {x["id"]: x for x in project.get("knowledge", []) if isinstance(x, dict) and isinstance(x.get("id"), str)}
        vfx_map = {x["id"]: x for x in project.get("vfx", []) if isinstance(x, dict) and isinstance(x.get("id"), str)}
        form_map = {x["id"]: x for x in project.get("forms", []) if isinstance(x, dict) and isinstance(x.get("id"), str)}
        attrition_map = {x["id"]: x for x in project["scene"].get("attrition", []) if isinstance(x, dict) and isinstance(x.get("id"), str)}

        windows = wp["windows"]
        win_map = {}
        if not isinstance(windows, list) or not windows:
            fail("window_plan.windows", "须为非空窗口数组")
            return
        for i, item in enumerate(windows):
            path = f"window_plan.windows[{i}]"
            if not obj(item, {"id", "start", "end", "shot_ids", "knot_ids", "opening_state",
                              "closing_state", "entry_frame", "exit_frame", "carries",
                              "fallback_splits", "risk"}, path, {"fallback"}):
                continue
            identity(item, path)
            start_ok = number(item["start"], path + ".start")
            end_ok = number(item["end"], path + ".end")
            if start_ok and end_ok:
                if item["start"] < -EPS or item["end"] <= item["start"] or item["end"] > duration + EPS:
                    fail(path, "时间须满足 0 <= start < end <= duration_sec")
            refs(item["shot_ids"], shot_map, path + ".shot_ids")
            refs(item["knot_ids"], knot_map, path + ".knot_ids", nonempty=False)
            for key in ("opening_state", "closing_state"):
                if text(item[key], path + "." + key):
                    execution_text(item[key], path + "." + key, "窗口状态")
                    layer_texts.append((item[key], path + "." + key))
            entry = text(item["entry_frame"], path + ".entry_frame")
            exit_ok = text(item["exit_frame"], path + ".exit_frame")
            if entry and item["entry_frame"] not in frames_map:
                fail(path + ".entry_frame", "未知关键帧引用")
            if exit_ok and item["exit_frame"] not in frames_map:
                fail(path + ".exit_frame", "未知关键帧引用")
            if entry and exit_ok and start_ok and end_ok and item["entry_frame"] in frames_map and item["exit_frame"] in frames_map:
                if abs(frames_map[item["entry_frame"]]["time_sec"] - item["start"]) > EPS:
                    fail(path + ".entry_frame", "入口帧时刻须等于窗口起点")
                if abs(frames_map[item["exit_frame"]]["time_sec"] - item["end"]) > EPS:
                    fail(path + ".exit_frame", "出口帧时刻须等于窗口终点")
            carries = item["carries"]
            if obj(carries, {"text"}, path + ".carries", set(CARRY_KEYS)):
                if text(carries["text"], path + ".carries.text"):
                    execution_text(carries["text"], path + ".carries.text", "接缝包")
                    layer_texts.append((carries["text"], path + ".carries.text"))
                for key in CARRY_KEYS:
                    if key not in carries:
                        continue
                    value = carries[key]
                    if not strings(value, f"{path}.carries.{key}", nonempty=True, unique=True):
                        continue
                    mapping = {"vfx": vfx_map, "forms": form_map, "costs": cost_map,
                               "knowledge": knowledge_map, "tracks": track_map,
                               "attrition": attrition_map}[key]
                    for ref in value:
                        if ref not in mapping:
                            fail(f"{path}.carries.{key}", f"未知引用 {ref}")
            splits = item["fallback_splits"]
            if strings(splits, path + ".fallback_splits", nonempty=False, unique=True):
                for ref in splits:
                    if ref not in cand_map:
                        fail(path + ".fallback_splits", "未知切点候选 " + ref)
                    elif start_ok and end_ok and not item["start"] + EPS < cand_map[ref]["time_sec"] < item["end"] - EPS:
                        fail(path + ".fallback_splits", "降级切点须位于窗口内部 " + ref)
            if not isinstance(item["risk"], str) or item["risk"] not in RISKS:
                fail(path + ".risk", "仅支持 low、high")
            elif item["risk"] == "high":
                if "fallback" not in item:
                    fail(path + ".fallback", "高风险窗口须写保底构图")
                elif text(item["fallback"], path + ".fallback"):
                    execution_text(item["fallback"], path + ".fallback", "保底构图")
                    layer_texts.append((item["fallback"], path + ".fallback"))
                if isinstance(splits, list) and not splits:
                    fail(path + ".fallback_splits", "高风险窗口须给可执行的降级切点")
            elif "fallback" in item:
                fail(path + ".fallback", "低风险窗口不登记保底构图；需要保底说明该窗应标 high")
            if isinstance(item["id"], str):
                win_map[item["id"]] = item
        numeric = all(isinstance(window.get("start"), (int, float)) and not isinstance(window.get("start"), bool)
                      and isinstance(window.get("end"), (int, float)) and not isinstance(window.get("end"), bool)
                      for window in windows)
        if numeric:
            cursor = 0
            for item in windows:
                if abs(item["start"] - cursor) > EPS:
                    fail("window_plan.windows", "窗口须按序连续覆盖全片，不得有缺口、重叠或顺序错误")
                    break
                cursor = item["end"]
            if windows and abs(cursor - duration) > EPS:
                fail("window_plan.windows", "最后一个窗口须结束于总时长")
        if errors:
            return

        assigned = {key: [] for key in knot_map}
        for index, item in enumerate(windows):
            path = f"window_plan.windows[{index}]"
            expected = [shot["id"] for shot in shot_order
                        if min(item["end"], shot["end"]) - max(item["start"], shot["start"]) > EPS]
            if isinstance(item["shot_ids"], list) and item["shot_ids"] != expected:
                fail(path + ".shot_ids", "须按顺序列出与窗口有正时长交集的全部镜头；窗口可从镜头中部起止")
            if isinstance(item["knot_ids"], list):
                for knot_id in item["knot_ids"]:
                    if knot_id in assigned:
                        assigned[knot_id].append(item)
            if tracked and isinstance(item["shot_ids"], list):
                for left_id, right_id in zip(item["shot_ids"], item["shot_ids"][1:]):
                    left_shot, right_shot = shot_map.get(left_id), shot_map.get(right_id)
                    if left_shot and right_shot and left_shot.get("track") != right_shot.get("track") \
                            and (left_id, right_id) not in transition_pairs:
                        fail(path + ".shot_ids", "同一窗口内切换动作线须有世界内转场；不能只靠硬切")
            if index > 0:
                previous = windows[index - 1]
                left_shot = shot_map[previous["shot_ids"][-1]]
                right_shot = shot_map[item["shot_ids"][0]]
                if not tracked or left_shot.get("track") == right_shot.get("track"):
                    if previous["closing_state"] != item["opening_state"]:
                        fail(path + ".opening_state", "同一动作线内，前窗出口与后窗入口须逐字相等")
                elif (left_shot["id"], right_shot["id"]) not in transition_pairs:
                    fail(path + ".start", "跨动作线的窗口边界须有世界内转场作载体；不能只靠硬切")
                boundary_transition = next(
                    (t for t in project.get("transitions", [])
                     if isinstance(t, dict) and t.get("from_shot") == left_shot["id"] and t.get("to_shot") == right_shot["id"]),
                    None,
                )
                if boundary_transition is not None and boundary_transition.get("layer") == "post":
                    fail(path + ".start", "窗口接缝不能用呈现层转场；下一窗不知道它存在，接缝会跳")
                if previous["exit_frame"] != item["entry_frame"]:
                    fail(path + ".entry_frame", "内部边界两侧须共用同一张交接帧；前窗出口即后窗入口")
                shared = frames_map.get(item["entry_frame"])
                if shared is not None and shared.get("role") != "handoff":
                    fail(path + ".entry_frame", "内部边界帧须为 handoff；它同时作为前窗末帧与后窗首帧条件")
                matches = [c for c in cand_map.values() if abs(c["time_sec"] - item["start"]) <= EPS]
                if not matches:
                    fail(path + ".start", "内部边界须引用一个已登记的切点候选")
                elif len(matches) > 1:
                    fail(path + ".start", "同一边界只能有一个切点候选")
                else:
                    candidate = matches[0]
                    if candidate["grade"] == "C":
                        if item["risk"] != "high":
                            fail(path + ".risk", "C 级边界由后窗承担风险，该窗须标 high")
                        if not item.get("fallback") or not item["fallback_splits"]:
                            fail(path + ".fallback", "C 级边界须写保底构图与非空降级切点")
        for knot_id, found in assigned.items():
            if len(found) != 1:
                fail(f"window_plan.knots.{knot_id}", "每个关联簇须恰好落在一个窗口内；拆簇须改设计，不硬拆")
            elif found:
                window = found[0]
                knot = knot_map[knot_id]
                if not set(knot["shot_ids"]).issubset(set(window["shot_ids"])):
                    fail(f"window_plan.knots.{knot_id}", "关联簇的镜头须全部落在同一个窗口内")
                spans = [shot_map[x] for x in knot["shot_ids"] if x in shot_map]
                if spans:
                    knot_start = min(x["start"] for x in spans)
                    knot_end = max(x["end"] for x in spans)
                    if knot_start < window["start"] - EPS or knot_end > window["end"] + EPS:
                        fail(f"window_plan.knots.{knot_id}", "关联簇内容跨越窗口边界；簇必须完整落在窗口时间范围内")

        # 窗口边界落在镜头中部时，必须对齐该镜 execution 的 cue 边界，否则执行稿会切在半句动作上。
        for index, window in enumerate(windows):
            for key, moment in (("start", window["start"]), ("end", window["end"])):
                holder = next((shot for shot in shot_order if shot["start"] + EPS < moment < shot["end"] - EPS), None)
                if holder is None:
                    continue
                execution = holder.get("execution")
                cues = execution.get("cues", []) if isinstance(execution, dict) else []
                aligned = any(
                    isinstance(cue, dict)
                    and (abs(cue.get("start", -1) - moment) <= EPS or abs(cue.get("end", -1) - moment) <= EPS)
                    for cue in cues
                )
                if not aligned:
                    fail(f"window_plan.windows[{index}].{key}",
                         "窗口边界落在镜头中部时须对齐该镜 cue 边界；否则执行稿会切在半句动作上")

        if max_window is not None:
            for index, item in enumerate(windows):
                if item["end"] - item["start"] > max_window + EPS:
                    fail(f"window_plan.windows[{index}]", "窗口超过声明的 max_window_sec")
            for knot_id, knot in knot_map.items():
                spans = [shot_map[x] for x in knot["shot_ids"] if x in shot_map]
                if spans:
                    span = max(x["end"] for x in spans) - min(x["start"] for x in spans)
                    if span > max_window + EPS:
                        fail(f"window_plan.knots.{knot_id}",
                             "关联簇跨度超过窗口上限；须改设计（遮挡、切镜、压缩征兆），不硬拆")

        for index, item in enumerate(windows):
            if not item["fallback_splits"]:
                continue
            points = [item["start"]] + sorted(cand_map[x]["time_sec"] for x in item["fallback_splits"] if x in cand_map) + [item["end"]]
            if max_window is not None:
                for left, right in zip(points, points[1:]):
                    if right - left > max_window + EPS:
                        fail(f"window_plan.windows[{index}].fallback_splits",
                             "降级切点切完仍有分段超过 max_window_sec")

        def merged_spans(ids):
            spans = [(shot_map[x]["start"], shot_map[x]["end"]) for x in ids if x in shot_map]
            merged = []
            for start, end in sorted(spans):
                if merged and start <= merged[-1][1] + EPS:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], end))
                else:
                    merged.append((start, end))
            return merged

        def covers(ids, moment):
            return any(start - EPS <= moment < end - EPS for start, end in merged_spans(ids))

        for index, item in enumerate(windows[1:], 1):
            previous = windows[index - 1]
            moment = item["start"]
            required = {"vfx": [], "forms": [], "costs": [], "knowledge": [], "tracks": [], "attrition": []}
            for cost in cost_map.values():
                beat = beat_map.get(cost.get("from_beat"))
                if cost.get("irreversible") is True and beat and beat["start"] < moment - EPS:
                    required["costs"].append(cost["id"])
            for know in knowledge_map.values():
                beat = beat_map.get(know.get("from_beat"))
                resolved = beat_map.get(know.get("resolved_by")) if know.get("resolved_by") else None
                if beat and beat["start"] < moment - EPS and (resolved is None or resolved["end"] > moment + EPS):
                    required["knowledge"].append(know["id"])
            for mark in attrition_map.values():
                beat = beat_map.get(mark.get("from_beat"))
                if beat and beat["start"] < moment - EPS:
                    required["attrition"].append(mark["id"])
            for effect in vfx_map.values():
                if effect.get("layer") == "world" and covers(effect.get("shot_ids", []), moment):
                    required["vfx"].append(effect["id"])
                elif effect.get("layer") == "post":
                    spans = merged_spans(effect.get("shot_ids", []))
                    if spans and spans[0][0] < moment - EPS and spans[-1][1] > moment + EPS:
                        fail("window_plan.windows", "呈现层特效不能跨窗口边界；下一窗不知道它存在，接缝会跳")
            for form in form_map.values():
                spans = merged_spans(form.get("shot_ids", []))
                if spans and spans[0][0] < moment - EPS and spans[-1][1] > moment + EPS:
                    if form.get("method") in ("occlusion", "morph"):
                        fail("window_plan.windows", "形态切换不得跨窗口边界；遮挡或连续形变须整簇同窗")
                    elif form.get("id") not in item["carries"].get("forms", []):
                        required["forms"].append(form["id"])
            if tracked:
                left = shot_map[previous["shot_ids"][-1]].get("track") if previous["shot_ids"] else None
                right = shot_map[item["shot_ids"][0]].get("track") if item["shot_ids"] else None
                if left and right and left != right:
                    required["tracks"] = [left, right]
            missing = []
            for key, values in required.items():
                carried = set(item["carries"].get(key, []))
                for value in values:
                    if value not in carried:
                        missing.append(f"{key}:{value}")
            if missing:
                fail(f"window_plan.windows[{index}].carries",
                     "接缝包缺少跨界项 " + ", ".join(missing[:4]) + "；下一窗不知道这些状态就会错")

    if windowed and WINDOW_PLAN in project and not errors:
        check_window_plan()

    # 扫描全部已登记 ID（含 B03 这类短 ID），按标识符边界匹配，不把普通单词里的子串误判为 ID
    leaked = sorted(ids)
    if leaked:
        pattern = re.compile(r"(?<![A-Za-z0-9_-])(?:" + "|".join(map(re.escape, sorted(leaked, key=len, reverse=True))) + r")(?![A-Za-z0-9_-])")

        def scan(value, path):
            if not isinstance(value, str):
                return
            hit = sorted(set(pattern.findall(value)))
            if hit:
                fail(path, "不得含内部 ID " + ", ".join(hit[:3]) + "；执行稿、段上下文与静图提示词用名称而非工程标识")
        for path, shot in shots:
            execution = shot["execution"]
            if isinstance(execution, dict):
                keys = ("opening_state", "end_state", "camera", "effects", "sound") + (("light",) if craft else ())
                for key in keys:
                    scan(execution.get(key), f"{path}.execution.{key}")
                if isinstance(execution.get("cues"), list):
                    for i, cue in enumerate(execution["cues"]):
                        if isinstance(cue, dict):
                            scan(cue.get("text"), f"{path}.execution.cues[{i}].text")
            if craft:
                scan(shot.get("fallback"), path + ".fallback")
        for path, segment in segments:
            scan(segment.get("prompt_context"), path + ".prompt_context")
        for path, frame in frames:
            scan(frame.get("prompt"), path + ".prompt")
        for value, path in layer_texts:
            scan(value, path)

    if craft and not errors:
        craft_checks(project, fail)
    return errors


ROLE_LABELS = {
    "single": "｜单帧",
    "prep": "｜预备帧",
    "contact": "｜接触帧",
    "result": "｜结果帧",
    "handoff": "｜段界交接帧，可直接用作前段末帧与后段首帧条件",
}


def _time(value):
    result = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if result == "-0" else result


def _clause(value):
    """去掉句末标点，供渲染时再接自己的标点，避免出现“。。”。"""
    return value.rstrip().rstrip("。；;.，,")


def _bullets(items):
    return "\n".join("- " + x for x in items) if items else "- 无新增项。"


def render(project):
    assets = project["assets"]
    beats = {x["id"]: x for x in project["beats"]}
    shots = {x["id"]: x for x in project["shots"]}
    design = project["design"]
    design_text = f"# {project['title']}：战斗设计\n\n总时长 {_time(project['duration_sec'])} 秒；画幅 {project['aspect_ratio']}。\n\n画风：{project['style']}\n\n"
    for label, items in (("双方目标", design["goals"]), ("本场规则", design["rules"]), ("战术变化", design["turns"]), ("硬约束", project["constraints"]), ("补充假设", project["assumptions"])):
        design_text += f"## {label}\n\n{_bullets(items)}\n\n"
    if "viewing_tasks" in design:
        design_text += "## 观看任务\n\n" + _bullets(design["viewing_tasks"]) + "\n\n"
    design_text += "## 结局\n\n" + design["outcome"] + "\n"
    if "cost" in project:
        design_text += "\n## 代价账目\n\n每项支出登记归属、起始节拍与后续限制；不可逆项在终态及之后每处引用中保留。\n\n"
        for entry in project["cost"]:
            kind = "不可逆" if entry["irreversible"] else "可恢复"
            design_text += f"- {entry['id']}｜{entry['owner']} 支出 {entry['item']}（{kind}，起于 {entry['from_beat']}）：{entry['consequence']}\n"
    if "knowledge" in project:
        design_text += "\n## 所知与实际\n\n分开记录人物判断与真实状态；观众线索写在 cue 列。\n\n"
        for entry in project["knowledge"]:
            resolved = entry.get("resolved_by", "本场未识破")
            design_text += f"- {entry['id']}｜{entry['holder']} 以为：{entry['belief']}\n  实际：{entry['truth']}\n  建立于 {entry['from_beat']}，识破于 {resolved}；观众线索：{entry['cue']}\n"
    if "tracks" in project:
        design_text += "\n## 动作线\n\n成片仍是单条镜头时间轴；各线只在自己的镜头里接续状态，内景镜头另登记同一时刻的外层状态。\n\n"
        for track in project["tracks"]:
            design_text += f"- {track['id']}｜{track['name']}（{TRACK_LABELS[track['kind']]}）：{track['time_relation']}\n"
    if "forms" in project:
        design_text += "\n## 形态切换\n\n变身是战局转折，不提供无敌时间；切换过程中仍可被打断。\n\n"
        for form in project["forms"]:
            design_text += f"- {form['id']}｜{form['actor']}：{form['from_asset']} → {form['to_asset']}，{FORM_LABELS[form['method']]}，起于 {form['beat_id']}，代价 {form['cost_id']}\n  阶梯：{' → '.join(map(_clause, form['ladder']))}\n  共享身份锚点：{'；'.join(form['shared_anchors'])}\n  持续：{form['duration']}\n  退出：{form['exit']}\n"
    asset_text = "# 本场资产与图像提示词\n\n"
    for asset in assets:
        asset_text += f"## {asset['id']} · {asset['name']}（{asset['kind']}）\n\n稳定锚点：\n\n{_bullets(asset['anchors'])}\n\n必要状态：\n\n{_bullets(asset['states'])}\n\n图像提示词：{asset['image_prompt']}\n\n"
        if "reference" in asset:
            ref = asset["reference"]
            asset_text += f"素材来源：{ref['source']}\n\n控制：{ref['control']}\n\n继承：{ref['keep']}\n\n排除：{ref['exclude']}\n\n"
    if "vfx" in project:
        asset_text += "## 签名特效\n\n同一特效跨镜保持外观；世界内特效会接触、残留并改变状态，呈现层特效只改变观看方式。\n\n"
        for item in project["vfx"]:
            phases = "；".join(f"{LIFECYCLE_LABELS[key]}：{_clause(item['lifecycle'][key])}" for key in LIFECYCLE if key in item["lifecycle"])
            reuse = f"，复用资产 {item['asset_id']}" if "asset_id" in item else ""
            asset_text += f"### {item['id']} · {item['name']}\n\n归属：{item['owner']}；{LAYER_LABELS[item['layer']]}；尺度 {SCALE_LABELS[item['scale']]}；制作路线 {VFX_ROUTE_LABELS[item['route']]}{reuse}。出现镜头：{', '.join(item['shot_ids'])}。\n\n叙事功能：{item['function']}\n\n外观：{item['look']}\n\n生命周期：{phases}\n\n支出与留下：{item['spends']}\n\n"
    asset_text += "## 战场地理\n\n" + project["scene"]["geography"] + "\n"
    if "attrition" in project["scene"]:
        asset_text += "\n## 战场累积痕迹\n\n痕迹一旦形成即保留，并与后续效果互动、限制后续路线。\n\n"
        for entry in project["scene"]["attrition"]:
            asset_text += f"- {entry['id']}｜{entry['mark']}（起于 {entry['from_beat']}）：{entry['consequence']}\n"

    def shot_text(shot, offset=0):
        result = f"### {shot['id']} · {_time(shot['start'] - offset)}–{_time(shot['end'] - offset)}秒\n\n全场时间：{_time(shot['start'])}–{_time(shot['end'])}秒。资产：{', '.join(shot['asset_ids'])}。\n\n"
        if windows_by_shot:
            containers = windows_by_shot.get(shot["id"], [])
            if containers:
                labels = "、".join(f"{window['id']}（{_time(window['start'])}–{_time(window['end'])} 秒）" for window in containers)
                result += f"生成窗口：{labels}。\n\n"
        result += f"起态：{shot['opening_state']}\n\n"
        for ref in shot["beat_ids"]:
            beat = beats[ref]
            start = max(shot["start"], beat["start"])
            end = min(shot["end"], beat["end"])
            marks = "｜标记 " + ", ".join(beat["marks"]) if beat.get("marks") else ""
            result += f"节拍 {ref}（主体 {', '.join(beat['actors'])}，全场定义 {_time(beat['start'])}–{_time(beat['end'])}秒；本镜覆盖 {_time(start-offset)}–{_time(end-offset)}秒{marks}）：\n\n"
            if beat["start"] < shot["start"] or beat["end"] > shot["end"]:
                result += "此拍跨镜；以下为完整动作定义，本镜只呈现覆盖窗口内进程，承接既有相位，不重新起手或重复计伤。\n\n"
            result += f"行动：{beat['action']}\n\n回应：{beat['response']}\n\n结果：{beat['result']}\n\n完成依赖：{', '.join(beat['requires']) or '无'}。\n\n"
        frame_ids = [f"{x['id']}（{x['role']}）" if "role" in x else x["id"] for x in project["keyframes"] if x["shot_id"] == shot["id"]]
        result += f"摄影：{shot['camera']}\n\n特效：{shot['effects']}\n\n"
        if "light" in shot:
            result += f"光照与归属：{shot['light']}\n\n"
        result += f"声音：{shot['sound']}\n\n"
        if "risk" in shot:
            label = "高" if shot["risk"] == "high" else "低"
            result += f"生成风险：{label}。"
            result += f"保底构图：{shot['fallback']}\n\n" if "fallback" in shot else "无需保底构图。\n\n"
        if "track" in shot:
            result += f"动作线：{tracks[shot['track']]['name']}（{TRACK_LABELS[tracks[shot['track']]['kind']]}）。\n\n"
            if "outer_state" in shot:
                result += f"同一时刻外层状态：{shot['outer_state']}\n\n"
        for item in project.get("vfx", []):
            if shot["id"] in item["shot_ids"]:
                result += f"签名特效 {item['id']}（{item['name']}，{LAYER_LABELS[item['layer']]}）在本镜出现。\n\n"
        for form in project.get("forms", []):
            if shot["id"] in form["shot_ids"]:
                result += f"形态切换 {form['id']}：{FORM_LABELS[form['method']]}，{form['from_asset']} → {form['to_asset']}。\n\n"
        result += f"关联关键帧：{', '.join(frame_ids)}。\n\n终态：{shot['end_state']}\n\n"
        if shot["id"] in transitions:
            result += transition_text(transitions[shot["id"]], True)
        return result

    def transition_text(item, internal, head=None):
        head = head or (f"转场 {item['id']} → {item['to_shot']}" if internal else "转场至下一镜")
        result = f"{head}：{METHOD_LABELS[item['method']]}（{LAYER_LABELS[item['layer']]}）。"
        if "occluder" in item:
            result += f"遮挡物或介质：{_clause(item['occluder'])}。"
        result += f"切点条件：{item['cut_condition']}\n\n不变：{'；'.join(map(_clause, item['keeps']))}。\n\n变化：{'；'.join(map(_clause, item['changes']))}。\n\n"
        if internal:
            result += f"制作路线：{TRANSITION_ROUTE_LABELS[item['route']]}。\n\n"
        return result

    tracks = {x["id"]: x for x in project.get("tracks", [])}
    transitions = {x["from_shot"]: x for x in project.get("transitions", [])}
    window_plan = project.get(WINDOW_PLAN)
    windows_by_shot = {}
    if window_plan:
        for window in window_plan["windows"]:
            for shot_id in window["shot_ids"]:
                windows_by_shot.setdefault(shot_id, []).append(window)
    frame_map = {x["id"]: x for x in project["keyframes"]}
    candidate_map = {x["id"]: x for x in window_plan["candidates"]} if window_plan else {}
    shot_number = {x["id"]: i for i, x in enumerate(project["shots"], 1)}

    def window_plan_text():
        cap = window_plan["capability"]
        bits = [f"能力来源：{CAPABILITY_LABELS.get(cap['source'], cap['source'])}"]
        if "max_window_sec" in cap:
            bits.append(f"能力上限 {_time(cap['max_window_sec'])} 秒")
        if "arbitrary_start" in cap:
            bits.append("可任意起点" if cap["arbitrary_start"] else "仅顺序生成")
        if "frame_conditioning" in cap:
            bits.append("帧条件：" + FRAME_CONDITION_LABELS.get(cap["frame_conditioning"], cap["frame_conditioning"]))
        if "internal_cuts" in cap:
            bits.append("允许窗口内剪辑" if cap["internal_cuts"] else "单镜连续生成")
        if "audio" in cap:
            bits.append("含音频" if cap["audio"] else "不含音频")
        text = "## 生成窗口规划\n\n" + "；".join(bits) + "。\n\n"
        text += "### 关联簇\n\n"
        for knot in window_plan["knots"]:
            text += f"- {knot['id']}｜{KNOT_LABELS.get(knot['kind'], knot['kind'])}｜镜头 {', '.join(knot['shot_ids'])}｜{knot['why']}\n"
        text += "\n### 切点候选\n\n"
        for candidate in window_plan["candidates"]:
            seam = f"｜接缝：{candidate['seam']}" if "seam" in candidate else ""
            text += f"- {candidate['id']}｜{_time(candidate['time_sec'])} 秒｜{candidate['shot_id']}｜{candidate['grade']} 级｜{candidate['reason']}{seam}\n"
        text += "\n### 窗口\n\n"
        for window in window_plan["windows"]:
            text += f"- {window['id']}｜{_time(window['start'])}–{_time(window['end'])} 秒｜镜头 {', '.join(window['shot_ids'])}｜含簇 {', '.join(window['knot_ids']) or '无'}\n"
            text += f"  入口帧：{window['entry_frame']}（{_time(window['start'])} 秒）；出口帧：{window['exit_frame']}（{_time(window['end'])} 秒）\n"
            text += f"  入口状态：{window['opening_state']}\n  出口状态：{window['closing_state']}\n"
            carries = window["carries"]
            parts = []
            for key, label in (("costs", "代价"), ("knowledge", "所知"), ("vfx", "特效"),
                               ("forms", "形态"), ("tracks", "动作线"), ("attrition", "痕迹")):
                if carries.get(key):
                    parts.append(f"{label} {', '.join(carries[key])}")
            prefix = "；".join(parts) + "。" if parts else ""
            text += f"  接缝包：{prefix}{carries['text']}\n"
            text += f"  风险：{window['risk']}。"
            if "fallback" in window:
                text += f"保底构图：{window['fallback']}。"
            if window["fallback_splits"]:
                text += f"降级切点：{', '.join(window['fallback_splits'])}。"
            text += "\n"
        if "notes" in window_plan:
            text += "\n### 判断记录\n\n" + window_plan["notes"] + "\n"
        return text + "\n"

    def window_video():
        cap = window_plan["capability"]
        result = "# 通用导演执行文本\n\n按生成窗口组织；每窗可独立复制。窗口内的镜头是剪辑点，不是重新起手。本稿未适配特定平台语法。\n\n"
        for index, window in enumerate(window_plan["windows"], 1):
            window_shots = [shots[key] for key in window["shot_ids"]]
            first, last = window_shots[0], window_shots[-1]
            offset = window["start"]
            result += f"## 生成窗口 {index}（成片 {_time(window['start'])}–{_time(window['end'])} 秒）\n\n"
            result += f"含镜头 {shot_number[first['id']]}–{shot_number[last['id']]}。"
            if "max_window_sec" in cap:
                result += f"本窗能力上限 {_time(cap['max_window_sec'])} 秒。"
            result += "\n\n"
            result += f"入口静帧：{frame_map[window['entry_frame']]['prompt']}\n\n"
            result += f"出口静帧：{frame_map[window['exit_frame']]['prompt']}\n\n"
            result += f"接缝包：{window['carries']['text']}\n\n"
            contexts = []
            for segment in project["segments"]:
                if set(segment["shot_ids"]) & set(window["shot_ids"]) and segment["prompt_context"] not in contexts:
                    contexts.append(segment["prompt_context"])
            result += "本窗规则与场景：" + "；".join(contexts) + "\n\n"
            used_assets = {key for shot in window_shots for key in shot["asset_ids"]}
            result += "资产锚点：\n\n"
            for asset in assets:
                if asset["id"] not in used_assets:
                    continue
                result += f"- {asset['name']}：{'；'.join(asset['anchors'])}。\n"
                if "reference" in asset:
                    binding = asset["reference"]
                    result += f"  素材来源：{binding['source']}；控制：{binding['control']}；继承：{binding['keep']}；排除：{binding['exclude']}。\n"
            window_ids = set(window["shot_ids"])
            signatures = [x for x in project.get("vfx", []) if window_ids & set(x["shot_ids"])]
            if signatures:
                result += "\n签名特效（跨窗口外观保持一致）：\n\n"
                for item in signatures:
                    phases = "；".join(f"{LIFECYCLE_LABELS[key]}：{_clause(item['lifecycle'][key])}" for key in LIFECYCLE if key in item["lifecycle"])
                    result += f"- {item['name']}：{_clause(item['look'])}。{phases}。\n"
            for form in project.get("forms", []):
                if window_ids & set(form["shot_ids"]):
                    result += f"\n形态切换阶梯：{' → '.join(map(_clause, form['ladder']))}。切换中不提供无敌时间，身份锚点保持：{'；'.join(form['shared_anchors'])}。\n"
            result += f"\n本窗起态：{window['opening_state']}\n\n"
            for shot_index, shot in enumerate(window_shots, 1):
                execution = shot["execution"]
                first_shot = shot_index == 1
                last_shot = shot is last
                result += f"### 剪辑点 {shot_index}（本窗 {_time(shot['start'] - offset)}–{_time(shot['end'] - offset)} 秒）\n\n"
                if not first_shot:
                    result += f"起态：{execution['opening_state']}\n\n"
                for cue in execution["cues"]:
                    cue_start = max(cue["start"], window["start"])
                    cue_end = min(cue["end"], window["end"])
                    if cue_end - cue_start <= EPS:
                        continue
                    result += f"{_time(cue_start - offset)}–{_time(cue_end - offset)}秒：{cue['text']}\n\n"
                result += f"摄影：{execution['camera']}\n\n特效：{execution['effects']}\n\n"
                if "light" in execution:
                    result += f"光照：{execution['light']}\n\n"
                result += f"声音：{execution['sound']}\n\n"
                if shot.get("risk") == "high":
                    result += f"本镜生成风险高。若一次生成未得到可用结果，改用保底构图，世界状态不变：{shot['fallback']}\n\n"
                if not last_shot:
                    result += f"终态：{execution['end_state']}\n\n"
                if shot["id"] in transitions and shot is not last:
                    result += transition_text(transitions[shot["id"]], False)
            result += f"本窗终态与承接：{window['closing_state']}\n\n"
            if last["id"] in transitions and index < len(window_plan["windows"]):
                result += transition_text(transitions[last["id"]], False, "本窗与下一窗之间的转场")
            if window["risk"] == "high":
                result += f"本窗生成风险高。若一次生成未得到可用结果，改用保底构图，世界状态不变：{window['fallback']}\n\n"
                if window["fallback_splits"]:
                    split_times = [f"{_time(candidate_map[key]['time_sec'])} 秒" for key in window["fallback_splits"] if key in candidate_map]
                    result += "降级切点：" + "；".join(split_times) + "。切分后每段仍按原入口与出口条件生成。\n\n"
            result += "返修卡：只改本窗时，入口与出口静帧、接缝包不变；若改关键相位，同步相邻窗与本窗帧。\n\n"
        return result

    board = "# 完整分镜\n\n动作拍可以并行；跨镜动作按观察窗口接续。未登记转场的切点一律硬切。\n\n"
    if window_plan:
        board += window_plan_text()
    board += "".join(shot_text(x) for x in project["shots"])
    window_frame_notes = {}
    if window_plan:
        for window in window_plan["windows"]:
            entry, exit_frame = window["entry_frame"], window["exit_frame"]
            if entry == exit_frame:
                window_frame_notes.setdefault(entry, set()).add("窗口入口、出口")
            else:
                window_frame_notes.setdefault(entry, set()).add("窗口入口")
                window_frame_notes.setdefault(exit_frame, set()).add("窗口出口")
    frame_text = "# 关键帧提示词\n\n"
    for frame in project["keyframes"]:
        segment = next(x for x in project["segments"] if frame["shot_id"] in x["shot_ids"])
        offset = shots[segment["shot_ids"][0]]["start"]
        role = ROLE_LABELS.get(frame.get("role"), "")
        notes = ""
        if frame["id"] in window_frame_notes:
            labels = window_frame_notes[frame["id"]]
            notes = "｜窗口入口、出口" if labels == {"窗口入口", "窗口出口"} else "｜" + "、".join(sorted(labels))
        frame_text += f"## {frame['id']} · {frame['shot_id']} · 全场 {_time(frame['time_sec'])} 秒{role}{notes}\n\n制作段 {segment['id']}，段内 {_time(frame['time_sec']-offset)} 秒。\n\n资产：{', '.join(frame['asset_ids'])}。\n\n瞬间状态：{frame['state']}\n\n静图提示词：{frame['prompt']}\n\n"
    video = "# 通用导演执行文本\n\n每段可独立复制；段内时间为编排意图，不是逐帧执行保证。本稿未适配特定平台语法。\n\n"
    for index, segment in enumerate(project["segments"], 1):
        segment_shots = [shots[key] for key in segment["shot_ids"]]
        first, last = segment_shots[0], segment_shots[-1]
        offset = first["start"]
        used_assets = {key for shot in segment_shots for key in shot["asset_ids"]}
        video += f"## 制作段 {index}\n\n画幅：{project['aspect_ratio']}。画风：{_clause(project['style'])}。\n\n本段规则与场景：{segment['prompt_context']}\n\n资产锚点：\n\n"
        for asset in assets:
            if asset["id"] not in used_assets:
                continue
            video += f"- {asset['name']}：{'；'.join(asset['anchors'])}。\n"
            if "reference" in asset:
                binding = asset["reference"]
                video += f"  素材来源：{binding['source']}；控制：{binding['control']}；继承：{binding['keep']}；排除：{binding['exclude']}。\n"
        segment_ids = set(segment["shot_ids"])
        signatures = [x for x in project.get("vfx", []) if segment_ids & set(x["shot_ids"])]
        if signatures:
            video += "\n签名特效（跨镜外观保持一致）：\n\n"
            for item in signatures:
                phases = "；".join(f"{LIFECYCLE_LABELS[key]}：{_clause(item['lifecycle'][key])}" for key in LIFECYCLE if key in item["lifecycle"])
                video += f"- {item['name']}：{_clause(item['look'])}。{phases}。\n"
        for form in project.get("forms", []):
            if segment_ids & set(form["shot_ids"]):
                video += f"\n形态切换阶梯：{' → '.join(map(_clause, form['ladder']))}。切换中不提供无敌时间，身份锚点保持：{'；'.join(form['shared_anchors'])}。\n"
        video += f"\n本段起态：{first['execution']['opening_state']}\n\n"
        for shot_index, shot in enumerate(segment_shots, 1):
            execution = shot["execution"]
            video += f"### 镜头 {shot_index}\n\n起态：{execution['opening_state']}\n\n"
            for cue in execution["cues"]:
                video += f"{_time(cue['start'] - offset)}–{_time(cue['end'] - offset)}秒：{cue['text']}\n\n"
            video += f"摄影：{execution['camera']}\n\n特效：{execution['effects']}\n\n"
            if "light" in execution:
                video += f"光照：{execution['light']}\n\n"
            video += f"声音：{execution['sound']}\n\n"
            if shot.get("risk") == "high":
                video += f"本镜生成风险高。若一次生成未得到可用结果，改用保底构图，世界状态不变：{shot['fallback']}\n\n"
            video += f"终态：{execution['end_state']}\n\n"
            if shot["id"] in transitions and shot is not last:
                video += transition_text(transitions[shot["id"]], False)
        video += f"本段终态与承接：{last['execution']['end_state']}\n\n"
        if last["id"] in transitions:
            video += transition_text(transitions[last["id"]], False, "本段与下段之间的转场")
        handoff = [x for x in project["keyframes"] if x.get("role") == "handoff" and abs(x["time_sec"] - last["end"]) <= EPS]
        if handoff and index < len(project["segments"]):
            video += f"段界交接静图（本段末帧，亦为下段首帧条件）：{handoff[0]['prompt']}\n\n"
    if window_plan:
        video = window_video()
    review = "# 检查与承接\n\n- structural_status: pass\n- semantic_status: needs_review\n\n结构通过只说明数据满足交付契约。需逐项审阅能力边界、前因与反制、空间与受力、串并行动作耗时、静图时刻、镜外持续状态和视觉清晰度。作者登记的审阅与媒体观察不构成工具自动判定通过。\n\n## 制作段接点\n\n"
    for segment in project["segments"]:
        review += f"### {segment['id']}\n\n起态：{segment['opening_state']}\n\n终态：{segment['closing_state']}\n\n"
    if window_plan:
        cap = window_plan["capability"]
        review += "## 窗口规划（结构已查簇归属、边界候选、接缝包与降级切点）\n\n"
        review += f"- 能力来源：{CAPABILITY_LABELS.get(cap['source'], cap['source'])}"
        if "max_window_sec" in cap:
            review += f"；能力上限 {_time(cap['max_window_sec'])} 秒"
        review += "\n"
        for knot in window_plan["knots"]:
            review += f"- 关联簇 {knot['id']}（{KNOT_LABELS.get(knot['kind'], knot['kind'])}）：镜头 {', '.join(knot['shot_ids'])}；{knot['why']}\n"
        for window in window_plan["windows"]:
            review += f"- 窗口 {window['id']}：{_time(window['start'])}–{_time(window['end'])} 秒，镜头 {', '.join(window['shot_ids'])}，簇 {', '.join(window['knot_ids']) or '无'}，风险 {window['risk']}"
            if window["fallback_splits"]:
                review += f"，降级切点 {', '.join(window['fallback_splits'])}"
            review += "\n"
        review += "\n簇是否真实成立、A 级切点是否稳定、接缝包是否足够、窗口长度是否由内容驱动，属语义审阅。\n\n"
    if "cost" in project:
        review += "## 代价结算（结构已查归属、起拍与不可逆项存在）\n\n"
        for entry in project["cost"]:
            review += f"- {entry['owner']}：{entry['item']}，{'不可逆' if entry['irreversible'] else '可恢复'}；{entry['consequence']}\n"
        review += "\n不可逆项是否在终态与后续引用中真的保留，属语义审阅。\n\n"
    if "knowledge" in project:
        review += "## 信息差结算\n\n"
        for entry in project["knowledge"]:
            review += f"- {entry['holder']}：以为「{entry['belief']}」，实际「{entry['truth']}」；{'识破于 ' + entry['resolved_by'] if 'resolved_by' in entry else '本场未识破'}。\n"
        review += "\n识破线索是否可回溯、主客观视角是否分明，属语义审阅。\n\n"
    if any(key in project for key in LAYER_FIELDS):
        review += "## 特效、形态、动作线与转场（结构已查引用、层级与风险）\n\n"
        for item in project.get("vfx", []):
            review += f"- 特效 {item['name']}：{_clause(item['function'])}；支出与留下：{item['spends']}\n"
        for form in project.get("forms", []):
            review += f"- 形态切换 {form['id']}：节拍 {form['beat_id']} 已标 pivotal，代价 {form['cost_id']}；退出：{form['exit']}\n"
        for track in project.get("tracks", []):
            review += f"- 动作线 {track['name']}：{track['time_relation']}\n"
        for item in project.get("transitions", []):
            review += f"- 转场 {item['from_shot']} → {item['to_shot']}：{METHOD_LABELS[item['method']]}，{LAYER_LABELS[item['layer']]}\n"
        review += "\n特效是否被看懂、是否喧宾夺主、内景期间外层危机是否被观众记住、转场是否必要，属语义审阅。\n\n"
    if "review" in project:
        record = project["review"]
        review += f"## 作者登记的语义审阅（脚本未复核）\n\n范围：{record['scope']}\n\n已修复：\n\n{_bullets(record['fixed'])}\n\n仍需确认：\n\n{_bullets(record['pending'])}\n\n失效与更新：\n\n{_bullets(record['invalidated'])}\n\n验证范围：{record['verification']}\n\n"
    else:
        review += "## 语义审阅尚未登记\n\n本文件仅有结构结果与接点；完整交付前请补范围、已修复、未决项、失效更新和实际验证范围，不得将此骨架称为完成语义审阅。\n\n"
    observations = project.get("review", {}).get("media_observations", [])
    review += "## 作者登记的媒体观察（脚本未复核）\n\n"
    if observations:
        for observation in observations:
            review += f"来源：{observation['source']}\n\n类型：{observation['kind']}\n\n作者观察：{observation['observation']}\n\n观察局限：{observation['limitations']}\n\n"
    else:
        review += "未登记媒体观察；不能据此推断是否生成或是否已观看。\n\n"
    # 嵌入分镜时去掉审阅稿自己的一级标题，其余标题降一级，挂在“## 审阅记录”之下
    body = review.split("\n\n", 1)[1]
    board += "## 审阅记录\n\n" + re.sub(r"^(#+) ", lambda m: "#" * min(len(m.group(1)) + 1, 6) + " ", body, flags=re.M)
    return {"project.json": json.dumps(project, ensure_ascii=False, indent=2, allow_nan=False) + "\n", "01-design.md": design_text, "02-assets.md": asset_text, "03-storyboard.md": board, "04-keyframes.md": frame_text, "05-video-prompts.md": video, "06-review.md": review}


def export_bundle(project, target):
    errors = validate(project)
    if errors:
        raise ValueError("\n".join(errors))
    documents = render(project)
    target = Path(target).absolute()
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"目标已存在，不覆盖: {target}")
    if not target.parent.is_dir():
        raise FileNotFoundError(f"父目录不存在: {target.parent}")
    staging = Path(tempfile.mkdtemp(prefix=".combat-plan-", dir=target.parent))
    try:
        for name, content in documents.items():
            # 暂存目录由 mkdtemp 新建且为空；统一写 LF，跨平台导出逐字节一致
            (staging / name).write_text(content, encoding="utf-8", newline="\n")
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"目标已存在，不覆盖: {target}")
        if os.name == "nt":
            os.rename(staging, target)
        else:
            # POSIX rename may replace an empty directory; reserve before publishing.
            target.mkdir()
            try:
                for source in staging.iterdir():
                    os.rename(source, target / source.name)
            except BaseException:
                shutil.rmtree(target)
                raise
            staging.rmdir()
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return target


LAYER_MIGRATION_TODO = (
    "需要并行意识空间（内景、识海、梦境、幻阵）时登记 tracks，并为每个节拍与镜头写 track、为内景镜头写 outer_state",
    "为反复出现或承担叙事功能的特效登记 vfx：归属、层级、尺度、功能、外观、生命周期、支出与制作路线",
    "存在变身、法相、化形时登记 forms：前后两套资产、共享身份锚点、遮挡阶梯、代价、持续与退出；所在节拍须为 pivotal",
    "只为需要被记住的空间或状态跳变登记 transitions；其余切点保持硬切",
)
WINDOW_MIGRATION_TODO = (
    "为每场登记 window_plan：先标关联簇与切点候选，再定窗口；不默认任何时长上限",
    "按用户声明或已核实的平台能力填 capability；上限未知时省略 max_window_sec，用切点阶梯",
    "为每个内部边界补候选与共用 handoff 帧；为高风险窗补保底构图与非空降级切点",
    "跨界的不可逆代价、所知、世界内特效、形态、痕迹与动作线写进 carries；窗口状态与接缝包文本不得含时码或内部 ID",
)
MIGRATION_TODO = LAYER_MIGRATION_TODO + WINDOW_MIGRATION_TODO


def migrate(project):
    """1.2/1.3 → 1.4 结构迁移：只改版本号，不生成任何自由文本。返回新数据与需手写清单。"""
    errors = validate(project)
    if errors:
        raise ValueError("源数据未通过校验，先修复再迁移：\n" + "\n".join(errors))
    version = project["schema_version"]
    if version == "1.4":
        raise ValueError("已是 1.4，无需迁移")
    if version not in ("1.2", "1.3"):
        raise ValueError("migrate 只接受 1.2 或 1.3 数据；1.1 须先手写 1.2 的编舞字段（light、risk、role、marks、attrition、cost）")
    result = copy.deepcopy(project)
    if version == "1.2":
        result["schema_version"] = "1.3"
        errors = validate(result)
        if errors:
            raise ValueError("迁移到 1.3 未通过校验：\n" + "\n".join(errors))
        todo = list(MIGRATION_TODO)
    else:
        todo = list(WINDOW_MIGRATION_TODO)
    result["schema_version"] = "1.4"
    errors = validate(result)
    if errors:
        raise ValueError("迁移结果未通过校验：\n" + "\n".join(errors))
    return result, todo


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "export", "migrate"))
    parser.add_argument("project", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    # 参数错误先于读取文件报告，退出码 2
    if args.command == "migrate" and args.out is None:
        parser.error("migrate 需要 --out，且不覆盖源文件或已存在文件")
    if args.command == "export" and args.out is None:
        parser.error("export 需要 --out")
    if args.command == "validate" and args.out is not None:
        parser.error("validate 不使用 --out")
    # 结果含中文；控制台编码不是 UTF-8 时也不能因打印失败掩盖真实校验结果
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        project = load_project(args.project)
        if args.command == "migrate":
            migrated, todo = migrate(project)
            # 先在内存完成序列化与编码，失败时不留下空目标文件
            payload = (json.dumps(migrated, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
            target = args.out.absolute()
            if target.exists() or target.is_symlink():
                raise FileExistsError(f"目标已存在，不覆盖: {target}")
            if not target.parent.is_dir():
                raise FileNotFoundError(f"父目录不存在: {target.parent}")
            with open(target, "xb") as handle:
                try:
                    handle.write(payload)
                except BaseException:
                    handle.close()
                    target.unlink()
                    raise
            print(json.dumps({"structural_status": "pass", "semantic_status": "needs_review", "output": str(target), "schema_version": "1.4", "manual": todo}, ensure_ascii=False, indent=2))
            return 0
        errors = validate(project)
        if errors:
            print(json.dumps({"structural_status": "fail", "semantic_status": "needs_review", "errors": errors}, ensure_ascii=False, indent=2))
            return 1
        result = {"structural_status": "pass", "semantic_status": "needs_review"}
        if args.command == "export":
            result["output"] = str(export_bundle(project, args.out))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RecursionError) as exc:
        print(json.dumps({"structural_status": "fail", "semantic_status": "needs_review", "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
