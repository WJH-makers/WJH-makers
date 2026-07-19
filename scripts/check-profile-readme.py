#!/usr/bin/env python3
"""Profile README 健康检查：AUTO 标记齐全 + 自动化文件在位 + 本地引用不悬空。

与 scripts/generate_profile_readme.py 的 MARKERS 对齐。跑法：
  python scripts/check-profile-readme.py
"""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
readme = root / "README.md"
if not readme.exists():
    raise SystemExit("README.md is missing")
text = readme.read_text(encoding="utf-8")

# 1) 生成器依赖的 AUTO 标记必须成对齐全
required_markers = [
    "<!-- AUTO:PROJECTS:START -->",
    "<!-- AUTO:PROJECTS:END -->",
    "<!-- AUTO:LANGS:START -->",
    "<!-- AUTO:LANGS:END -->",
    "<!-- AUTO:RECENT:START -->",
    "<!-- AUTO:RECENT:END -->",
    "<!-- AUTO:META:START -->",
    "<!-- AUTO:META:END -->",
]
missing = [m for m in required_markers if m not in text]
if missing:
    raise SystemExit("README missing AUTO markers: " + ", ".join(missing))

# 2) 自动化关键文件在位
for rel in ("config/profile.yml", "scripts/generate_profile_readme.py"):
    if not (root / rel).exists():
        raise SystemExit(f"{rel} is missing")

# 3) 本地引用（相对路径的 src/href/srcset）不能悬空；外链与 mailto 跳过
local_refs = set()
for match in re.finditer(r'(?:src|href|srcset)="([^"#]+)"', text):
    value = match.group(1)
    if value.startswith(("http://", "https://", "mailto:")):
        continue
    local_refs.add(value.split("?")[0])
missing_paths = [ref for ref in sorted(local_refs) if not (root / ref).exists()]
if missing_paths:
    raise SystemExit("README references missing local files: " + ", ".join(missing_paths))

print("Profile README health check passed.")
