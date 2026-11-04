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

    if not obj(project, ROOT, "project", {"review"}):
        return errors
    if project["schema_version"] != "1.1":
        fail("schema_version", "仅支持字符串版本 1.1；请升级旧版数据并编写镜头 execution 与段 prompt_context，不自动迁移自由文本")
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
    if obj(scene, {"asset_id", "geography"}, "scene"):
        text(scene["geography"], "scene.geography")
        if text(scene["asset_id"], "scene.asset_id") and asset_map.get(scene["asset_id"], {}).get("kind") != "scene":
            fail("scene.asset_id", "须引用场景资产")

    if errors:
        return errors

    beats = group("beats", {"id", "start", "end", "actors", "action", "response", "result", "requires"})
    shots = group("shots", {"id", "start", "end", "beat_ids", "asset_ids", "opening_state", "camera", "effects", "sound", "end_state", "execution"})
    segments = group("segments", {"id", "shot_ids", "opening_state", "closing_state", "prompt_context"})
    frames = group("keyframes", {"id", "shot_id", "time_sec", "asset_ids", "state", "prompt"})
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
    for path, item in shots:
        interval(item, path)
        refs(item["beat_ids"], beat_map, path + ".beat_ids")
        refs(item["asset_ids"], asset_map, path + ".asset_ids")
        for key in ("opening_state", "camera", "effects", "sound", "end_state"):
            text(item[key], path + "." + key)
    if errors:
        return errors

    def execution_text(value, path):
        if text(value, path) and EXECUTION_TIME.search(value):
            fail(path, "执行文本不得含时间语法；时刻只允许写在 cues.start / cues.end 数值字段")

    for path, shot in shots:
        execution_path = path + ".execution"
        execution = shot["execution"]
        if not obj(execution, EXECUTION_FIELDS, execution_path):
            continue
        for key in EXECUTION_FIELDS - {"cues"}:
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
                fail(path + ".opening_state", "与首镜起态不一致")
            if item["closing_state"] != shot_map[seq[-1]]["end_state"]:
                fail(path + ".closing_state", "与末镜终态不一致")
        if previous is not None and previous != item["opening_state"]:
            fail(path + ".opening_state", "与前段终态不一致")
        previous = item["closing_state"]
    if assigned != [x["id"] for _, x in shots]:
        fail("segments", "须按顺序恰好分配全部镜头一次")

    frame_counts = {key: 0 for key in shot_map}
    for path, item in frames:
        refs(item["asset_ids"], asset_map, path + ".asset_ids")
        for key in ("state", "prompt"):
            text(item[key], path + "." + key)
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
    for key, count in frame_counts.items():
        if not count:
            fail("keyframes", "镜头缺少关键帧 " + key)
    return errors


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
    asset_text = "# 本场资产与图像提示词\n\n"
    for asset in assets:
        asset_text += f"## {asset['id']} · {asset['name']}（{asset['kind']}）\n\n稳定锚点：\n\n{_bullets(asset['anchors'])}\n\n必要状态：\n\n{_bullets(asset['states'])}\n\n图像提示词：{asset['image_prompt']}\n\n"
        if "reference" in asset:
            ref = asset["reference"]
            asset_text += f"素材来源：{ref['source']}\n\n控制：{ref['control']}\n\n继承：{ref['keep']}\n\n排除：{ref['exclude']}\n\n"
    asset_text += "## 战场地理\n\n" + project["scene"]["geography"] + "\n"

    def shot_text(shot, offset=0):
        result = f"### {shot['id']} · {_time(shot['start'] - offset)}–{_time(shot['end'] - offset)}秒\n\n全场时间：{_time(shot['start'])}–{_time(shot['end'])}秒。资产：{', '.join(shot['asset_ids'])}。\n\n起态：{shot['opening_state']}\n\n"
        for ref in shot["beat_ids"]:
            beat = beats[ref]
            start = max(shot["start"], beat["start"])
            end = min(shot["end"], beat["end"])
            result += f"节拍 {ref}（主体 {', '.join(beat['actors'])}，全场定义 {_time(beat['start'])}–{_time(beat['end'])}秒；本镜覆盖 {_time(start-offset)}–{_time(end-offset)}秒）：\n\n"
            if beat["start"] < shot["start"] or beat["end"] > shot["end"]:
                result += "此拍跨镜；以下为完整动作定义，本镜只呈现覆盖窗口内进程，承接既有相位，不重新起手或重复计伤。\n\n"
            result += f"行动：{beat['action']}\n\n回应：{beat['response']}\n\n结果：{beat['result']}\n\n完成依赖：{', '.join(beat['requires']) or '无'}。\n\n"
        frame_ids = [x["id"] for x in project["keyframes"] if x["shot_id"] == shot["id"]]
        return result + f"摄影：{shot['camera']}\n\n特效：{shot['effects']}\n\n声音：{shot['sound']}\n\n关联关键帧：{', '.join(frame_ids)}。\n\n终态：{shot['end_state']}\n\n"

    board = "# 完整分镜\n\n动作拍可以并行；跨镜动作按观察窗口接续。\n\n" + "".join(shot_text(x) for x in project["shots"])
    frame_text = "# 关键帧提示词\n\n"
    for frame in project["keyframes"]:
        segment = next(x for x in project["segments"] if frame["shot_id"] in x["shot_ids"])
        offset = shots[segment["shot_ids"][0]]["start"]
        frame_text += f"## {frame['id']} · {frame['shot_id']} · 全场 {_time(frame['time_sec'])} 秒\n\n制作段 {segment['id']}，段内 {_time(frame['time_sec']-offset)} 秒。\n\n资产：{', '.join(frame['asset_ids'])}。\n\n瞬间状态：{frame['state']}\n\n静图提示词：{frame['prompt']}\n\n"
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
            video += f"摄影：{execution['camera']}\n\n特效：{execution['effects']}\n\n声音：{execution['sound']}\n\n终态：{execution['end_state']}\n\n"
        video += f"本段终态与承接：{last['execution']['end_state']}\n\n"
    review = "# 检查与承接\n\n- structural_status: pass\n- semantic_status: needs_review\n\n结构通过只说明数据满足交付契约。需逐项审阅能力边界、前因与反制、空间与受力、串并行动作耗时、静图时刻、镜外持续状态和视觉清晰度。作者登记的审阅与媒体观察不构成工具自动判定通过。\n\n## 制作段接点\n\n"
    for segment in project["segments"]:
        review += f"### {segment['id']}\n\n起态：{segment['opening_state']}\n\n终态：{segment['closing_state']}\n\n"
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
