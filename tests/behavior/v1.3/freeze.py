"""Freeze SHA-256 fingerprints of the rule files used by the v1.3 controlled trial."""

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]


def main():
    names = ["SKILL.md"] + sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "references").glob("*.md"))
    digests = {}
    for name in names:
        digests[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    record = {
        "note": "v1.3 受控试用开始时冻结的规则指纹；试用期间这些文件未被改动。重跑本脚本可核对。",
        "files": digests,
    }
    target = pathlib.Path(__file__).with_name("skill-manifest.json")
    if "--check" in sys.argv:
        existing = json.loads(target.read_text(encoding="utf-8"))
        drift = [k for k, v in digests.items() if existing["files"].get(k) != v]
        print("drift:", drift or "none")
        return 1 if drift else 0
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, digest in digests.items():
        print(digest[:12], name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
