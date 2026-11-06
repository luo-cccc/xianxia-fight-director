#!/usr/bin/env python3
"""Validate and render a platform-independent single-battle plan."""

import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

EPS = 1e-6
EXECUTION_FIELDS = {"opening_state", "end_state", "camera", "effects", "sound", "cues"}
EXECUTION_TIME = re.compile(r"[0-9]+(?:\.[0-9]+)?\s*秒|[0-9]+(?:[:：][0-9]{1,2}){1,2}(?:\.[0-9]+)?")
KINDS = {"character", "creature", "scene", "prop", "formation", "manifestation"}
ACTORS = {"character", "creature", "manifestation"}
ROOT = {"schema_version", "title", "duration_sec", "aspect_ratio", "style", "assumptions", "constraints", "design", "assets", "scene", "beats", "shots", "segments", "keyframes"}
VERSIONS = ("1.1", "1.2")
MARKS = ("pivotal", "breath", "adaptation")
ROLES = {"single", "prep", "contact", "result", "handoff"}
RISKS = {"low", "high"}
CONTACT_ROLES = ("prep", "contact", "result")


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
        inside = [x for x in frames if beat["start"] - EPS <= x["time_sec"] <= beat["end"] + EPS]
        times = {}
        for role in CONTACT_ROLES:
            picked = sorted(x["time_sec"] for x in inside if x["role"] == role)
            if not picked:
                fail("keyframes", f"关键转折 {beat['id']} 缺少 {role} 帧；决胜接点须有预备、接触与结果三帧")
            else:
                times[role] = picked[0]
        if len(times) == len(CONTACT_ROLES) and not times["prep"] < times["contact"] < times["result"]:
            fail("keyframes", f"关键转折 {beat['id']} 的预备、接触、结果帧时刻须严格递增")

    pivotal_windows = [(x["start"], x["end"]) for x in marked["pivotal"]]
    for beat in marked["breath"]:
        if "pivotal" in beat.get("marks", []):
            fail(f"beats.{beat['id']}.marks", "呼吸拍不能同时是关键转折")
        for start, end in pivotal_windows:
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
        elif any(x["shot_id"] != last["id"] for x in picked):
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

    if not obj(project, ROOT, "project", {"review", "cost", "knowledge"}):
        return errors
    version = project["schema_version"]
    if version not in VERSIONS:
        fail("schema_version", "仅支持字符串版本 1.1 或 1.2；请升级旧版数据并编写镜头 execution 与段 prompt_context，不自动迁移自由文本")
    craft = version == "1.2"
    if not craft:
        for key in ("cost", "knowledge"):
            if key in project:
                fail(key, "仅 1.2 支持该字段；1.1 数据不得混入 1.2 字段")
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
    for path, item in assets:
        if isinstance(item["id"], str):
            asset_map[item["id"]] = item
        if not isinstance(item["kind"], str) or item["kind"] not in KINDS:
            fail(path + ".kind", "未知资产类型")
        for key in ("name", "image_prompt"):
            text(item[key], path + "." + key)
        strings(item["anchors"], path + ".anchors", nonempty=True)
        strings(item["states"], path + ".states")
        if "reference" in item and obj(item["reference"], {"source", "control", "keep", "exclude"}, path + ".reference"):
            for key, value in item["reference"].items():
                text(value, path + ".reference." + key)

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

    beat_fields = {"id", "start", "end", "actors", "action", "response", "result", "requires"}
    shot_fields = {"id", "start", "end", "beat_ids", "asset_ids", "opening_state", "camera", "effects", "sound", "end_state", "execution"}
    frame_fields = {"id", "shot_id", "time_sec", "asset_ids", "state", "prompt"}
    if craft:
        shot_fields |= {"light", "risk"}
        frame_fields |= {"role"}
    beats = group("beats", beat_fields, {"marks"} if craft else ())
    shots = group("shots", shot_fields, {"fallback"} if craft else ())
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
            if start < 0 or end <= start or end > duration + EPS:
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
    if errors:
        return errors

    def execution_text(value, path, kind="执行文本"):
        if text(value, path) and EXECUTION_TIME.search(value):
            fail(path, f"{kind}不得含阿拉伯数字秒码或冒号时码；时刻只允许写在 cues.start / cues.end 数值字段。计数（如“退三步”“两柄戟”）不受限制")

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
        for i, cue in enumerate(cues):
            cue_path = f"{execution_path}.cues[{i}]"
            if not obj(cue, {"start", "end", "text"}, cue_path):
                continue
            execution_text(cue["text"], cue_path + ".text")
            start_ok = number(cue["start"], cue_path + ".start")
            end_ok = number(cue["end"], cue_path + ".end")
            if start_ok and end_ok:
                start, end = cue["start"], cue["end"]
                if end <= start or start < shot["start"] - EPS or end > shot["end"] + EPS:
                    fail(cue_path, "cue 须满足所属镜头 start <= cue.start < cue.end <= 镜头 end，不得超镜")
                if abs(start - cursor) > EPS:
                    fail(cue_path + ".start", "cues 须按序连续覆盖所属镜头，不得有缺口、重叠或顺序错误")
                cursor = end
        if abs(cursor - shot["end"]) > EPS:
            fail(execution_path + ".cues", "cues 须连续覆盖到所属镜头终点")

    for (_, previous), (path, shot) in zip(shots, shots[1:]):
        if previous["end_state"] != shot["opening_state"]:
            fail(path + ".opening_state", "与前镜 end_state 必须逐字一致（原世界状态，不含机位）")
        previous_execution, execution = previous["execution"], shot["execution"]
        if isinstance(previous_execution, dict) and isinstance(execution, dict):
            if "end_state" in previous_execution and "opening_state" in execution and previous_execution["end_state"] != execution["opening_state"]:
                fail(path + ".execution.opening_state", "与前镜 execution.end_state 必须逐字一致")

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
    previous = None
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
        if previous is not None and previous != item["opening_state"]:
            fail(path + ".opening_state", "与前段终态不一致")
        previous = item["closing_state"]
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
            if isinstance(previous.get("shot_ids"), list) and previous["shot_ids"]:
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
    leaked = sorted(x for x in ids if len(x) >= 4)
    if leaked:
        def scan(value, path):
            if not isinstance(value, str):
                return
            hit = [x for x in leaked if x in value]
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
    return f"{value:.6f}".rstrip("0").rstrip(".")


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
    asset_text = "# 本场资产与图像提示词\n\n"
    for asset in assets:
        asset_text += f"## {asset['id']} · {asset['name']}（{asset['kind']}）\n\n稳定锚点：\n\n{_bullets(asset['anchors'])}\n\n必要状态：\n\n{_bullets(asset['states'])}\n\n图像提示词：{asset['image_prompt']}\n\n"
        if "reference" in asset:
            ref = asset["reference"]
            asset_text += f"素材来源：{ref['source']}\n\n控制：{ref['control']}\n\n继承：{ref['keep']}\n\n排除：{ref['exclude']}\n\n"
    asset_text += "## 战场地理\n\n" + project["scene"]["geography"] + "\n"
    if "attrition" in project["scene"]:
        asset_text += "\n## 战场累积痕迹\n\n痕迹一旦形成即保留，并与后续效果互动、限制后续路线。\n\n"
        for entry in project["scene"]["attrition"]:
            asset_text += f"- {entry['id']}｜{entry['mark']}（起于 {entry['from_beat']}）：{entry['consequence']}\n"

    def shot_text(shot, offset=0):
        result = f"### {shot['id']} · {_time(shot['start'] - offset)}–{_time(shot['end'] - offset)}秒\n\n全场时间：{_time(shot['start'])}–{_time(shot['end'])}秒。资产：{', '.join(shot['asset_ids'])}。\n\n起态：{shot['opening_state']}\n\n"
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
        return result + f"关联关键帧：{', '.join(frame_ids)}。\n\n终态：{shot['end_state']}\n\n"

    board = "# 完整分镜\n\n动作拍可以并行；跨镜动作按观察窗口接续。\n\n" + "".join(shot_text(x) for x in project["shots"])
    frame_text = "# 关键帧提示词\n\n"
    for frame in project["keyframes"]:
        segment = next(x for x in project["segments"] if frame["shot_id"] in x["shot_ids"])
        offset = shots[segment["shot_ids"][0]]["start"]
        role = ROLE_LABELS.get(frame.get("role"), "")
        frame_text += f"## {frame['id']} · {frame['shot_id']} · 全场 {_time(frame['time_sec'])} 秒{role}\n\n制作段 {segment['id']}，段内 {_time(frame['time_sec']-offset)} 秒。\n\n资产：{', '.join(frame['asset_ids'])}。\n\n瞬间状态：{frame['state']}\n\n静图提示词：{frame['prompt']}\n\n"
    video = "# 通用导演执行文本\n\n每段可独立复制；段内时间为编排意图，不是逐帧执行保证。本稿未适配特定平台语法。\n\n"
    for index, segment in enumerate(project["segments"], 1):
        segment_shots = [shots[key] for key in segment["shot_ids"]]
        first, last = segment_shots[0], segment_shots[-1]
        offset = first["start"]
        used_assets = {key for shot in segment_shots for key in shot["asset_ids"]}
        video += f"## 制作段 {index}\n\n画幅：{project['aspect_ratio']}。画风：{project['style']}。\n\n本段规则与场景：{segment['prompt_context']}\n\n资产锚点：\n\n"
        for asset in assets:
            if asset["id"] not in used_assets:
                continue
            video += f"- {asset['name']}：{'；'.join(asset['anchors'])}。\n"
            if "reference" in asset:
                binding = asset["reference"]
                video += f"  素材来源：{binding['source']}；控制：{binding['control']}；继承：{binding['keep']}；排除：{binding['exclude']}。\n"
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
        video += f"本段终态与承接：{last['execution']['end_state']}\n\n"
        handoff = [x for x in project["keyframes"] if x.get("role") == "handoff" and abs(x["time_sec"] - last["end"]) <= EPS]
        if handoff and index < len(project["segments"]):
            video += f"段界交接静图（本段末帧，亦为下段首帧条件）：{handoff[0]['prompt']}\n\n"
    review = "# 检查与承接\n\n- structural_status: pass\n- semantic_status: needs_review\n\n结构通过只说明数据满足交付契约。需逐项审阅能力边界、前因与反制、空间与受力、串并行动作耗时、静图时刻、镜外持续状态和视觉清晰度。作者登记的审阅与媒体观察不构成工具自动判定通过。\n\n## 制作段接点\n\n"
    for segment in project["segments"]:
        review += f"### {segment['id']}\n\n起态：{segment['opening_state']}\n\n终态：{segment['closing_state']}\n\n"
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
    board += "## 审阅记录\n\n" + review
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
            (staging / name).write_text(content, encoding="utf-8")
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "export"))
    parser.add_argument("project", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        project = load_project(args.project)
        errors = validate(project)
        if errors:
            print(json.dumps({"structural_status": "fail", "semantic_status": "needs_review", "errors": errors}, ensure_ascii=False, indent=2))
            return 1
        result = {"structural_status": "pass", "semantic_status": "needs_review"}
        if args.command == "export":
            if args.out is None:
                parser.error("export 需要 --out")
            result["output"] = str(export_bundle(project, args.out))
        elif args.out is not None:
            parser.error("validate 不使用 --out")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RecursionError) as exc:
        print(json.dumps({"structural_status": "fail", "semantic_status": "needs_review", "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
