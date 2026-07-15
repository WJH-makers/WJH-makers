#!/usr/bin/env python3
"""
Generate AUTO sections in profile README from GitHub API + config/profile.yml.

Usage:
  python scripts/generate_profile_readme.py
  python scripts/generate_profile_readme.py --dry-run
  python scripts/generate_profile_readme.py --check   # exit 1 if README stale

Env:
  GITHUB_TOKEN / GH_TOKEN  optional, higher rate limit
  PROFILE_USERNAME         override username from config
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
CONFIG = ROOT / "config" / "profile.yml"

MARKERS = {
    "projects": (
        "<!-- AUTO:PROJECTS:START -->",
        "<!-- AUTO:PROJECTS:END -->",
    ),
    "recent": (
        "<!-- AUTO:RECENT:START -->",
        "<!-- AUTO:RECENT:END -->",
    ),
    "meta": (
        "<!-- AUTO:META:START -->",
        "<!-- AUTO:META:END -->",
    ),
}


def load_config() -> dict:
    text = CONFIG.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
    except ImportError:
        # Minimal YAML subset for this file (no nested lists of maps beyond overrides)
        data = _minimal_yaml(text)
    if not isinstance(data, dict):
        raise SystemExit("config/profile.yml must be a mapping")
    return data


def _minimal_yaml(text: str) -> dict:
    """Fallback parser for our flat-ish profile.yml without PyYAML."""
    # Prefer json if someone converted; else require pyyaml for full fidelity
    raise SystemExit(
        "PyYAML is required. Install: pip install pyyaml\n"
        "Or in CI: pip install -r scripts/requirements.txt"
    )


def gh_get(url: str, token: str | None) -> object:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "WJH-makers-profile-generator",
            "X-GitHub-Api-Version": "2022-11-28",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"GitHub API {e.code} for {url}: {body[:300]}") from e


def fetch_repos(username: str, token: str | None) -> list[dict]:
    repos: list[dict] = []
    page = 1
    while page <= 10:
        q = urllib.parse.urlencode(
            {
                "per_page": 100,
                "page": page,
                "type": "owner",
                "sort": "pushed",
                "direction": "desc",
            }
        )
        batch = gh_get(
            f"https://api.github.com/users/{username}/repos?{q}",
            token,
        )
        if not isinstance(batch, list) or not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


def esc_cell(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def lang_tech(repo: dict) -> str:
    lang = repo.get("language") or ""
    topics = repo.get("topics") or []
    # Prefer language + up to 3 topics not repeating language
    parts = []
    if lang:
        parts.append(lang)
    for t in topics:
        t2 = t.replace("-", " ")
        if lang and t2.lower() == lang.lower():
            continue
        if t2 not in parts:
            parts.append(t2)
        if len(parts) >= 4:
            break
    return " · ".join(parts) if parts else "—"


def skill_for(name: str, repo: dict, overrides: dict) -> str:
    o = overrides.get(name) or {}
    if o.get("skill"):
        return str(o["skill"])
    desc = o.get("description") or repo.get("description") or ""
    desc = esc_cell(str(desc))
    if desc:
        return desc[:80] + ("…" if len(desc) > 80 else "")
    return "公开项目"


def description_for(name: str, repo: dict, overrides: dict) -> str:
    o = overrides.get(name) or {}
    if o.get("description"):
        return esc_cell(str(o["description"]))
    return esc_cell(repo.get("description") or "（无 description，可在仓库设置里补一句）")


def select_projects(repos: list[dict], cfg: dict) -> list[dict]:
    exclude = set(cfg.get("exclude") or [])
    featured = list(cfg.get("featured") or [])
    max_n = int(cfg.get("max_projects") or 12)
    overrides = cfg.get("overrides") or {}

    by_name = {
        r["name"]: r
        for r in repos
        if not r.get("fork")
        and not r.get("private")
        and not r.get("archived")
        and r["name"] not in exclude
    }

    ordered: list[dict] = []
    seen: set[str] = set()
    for name in featured:
        if name in by_name and name not in seen:
            ordered.append(by_name[name])
            seen.add(name)
    # rest by pushed_at
    rest = sorted(
        (r for n, r in by_name.items() if n not in seen),
        key=lambda r: r.get("pushed_at") or "",
        reverse=True,
    )
    ordered.extend(rest)
    ordered = ordered[:max_n]

    # attach display fields
    for r in ordered:
        name = r["name"]
        r["_tech"] = lang_tech(r)
        r["_skill"] = skill_for(name, r, overrides)
        r["_desc"] = description_for(name, r, overrides)
    return ordered


def render_projects(projects: list[dict]) -> str:
    lines = [
        "| 项目 | 技术 | 说明 / 练到的能力 |",
        "|---|---|---|",
    ]
    for r in projects:
        name = r["name"]
        url = r.get("html_url") or f"https://github.com/WJH-makers/{name}"
        home = r.get("homepage") or ""
        title = f"[{name}]({url})"
        if home and str(home).startswith("http"):
            title += f" · [site]({home})"
        lines.append(
            f"| {title} | {esc_cell(r['_tech'])} | {esc_cell(r['_skill'])} |"
        )
    lines.append("")
    lines.append(
        "<sub>本表由 <code>scripts/generate_profile_readme.py</code> 根据公开仓库 API "
        "+ <code>config/profile.yml</code> 自动生成。新仓库写好 description/topics 即可入表。</sub>"
    )
    return "\n".join(lines)


def render_recent(repos: list[dict], cfg: dict) -> str:
    exclude = set(cfg.get("exclude") or [])
    n = int(cfg.get("recent_count") or 6)
    items = [
        r
        for r in repos
        if not r.get("fork")
        and not r.get("private")
        and r["name"] not in exclude
    ][:n]
    if not items:
        return "_暂无公开动态_"
    lines = []
    for r in items:
        name = r["name"]
        url = r.get("html_url") or f"https://github.com/WJH-makers/{name}"
        when = (r.get("pushed_at") or "")[:10]
        desc = esc_cell(r.get("description") or "")
        bit = f"- **[{name}]({url})** · `{when}`"
        if desc:
            bit += f" — {desc[:100]}"
        lines.append(bit)
    return "\n".join(lines)


def render_meta(projects: list[dict], repos: list[dict]) -> str:
    public = [
        r
        for r in repos
        if not r.get("fork") and not r.get("private")
    ]
    langs: dict[str, int] = {}
    for r in public:
        lang = r.get("language")
        if lang:
            langs[lang] = langs.get(lang, 0) + 1
    top_langs = ", ".join(
        f"{k}×{v}"
        for k, v in sorted(langs.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"<sub>自动同步 · {now} · 公开非 fork 仓库 **{len(public)}** 个 · "
        f"表内展示 **{len(projects)}** 个 · 语言分布：{top_langs or '—'}</sub>"
    )


def replace_block(text: str, start: str, end: str, body: str) -> str:
    pattern = re.compile(
        re.escape(start) + r".*?" + re.escape(end),
        re.DOTALL,
    )
    replacement = f"{start}\n{body}\n{end}"
    if not pattern.search(text):
        raise SystemExit(f"README missing markers:\n  {start}\n  {end}")
    return pattern.sub(replacement, text, count=1)


def generate(readme_text: str, cfg: dict, token: str | None) -> str:
    username = os.environ.get("PROFILE_USERNAME") or cfg.get("username") or "WJH-makers"
    repos = fetch_repos(username, token)
    projects = select_projects(repos, cfg)
    text = readme_text
    text = replace_block(
        text, *MARKERS["projects"], render_projects(projects)
    )
    text = replace_block(text, *MARKERS["recent"], render_recent(repos, cfg))
    text = replace_block(text, *MARKERS["meta"], render_meta(projects, repos))
    if not text.endswith("\n"):
        text += "\n"
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="print to stdout only")
    ap.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if README would change (CI drift check)",
    )
    args = ap.parse_args()

    if not README.exists():
        raise SystemExit("README.md missing")
    if not CONFIG.exists():
        raise SystemExit("config/profile.yml missing")

    cfg = load_config()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    original = README.read_text(encoding="utf-8")
    updated = generate(original, cfg, token)

    if args.check:
        if original != updated:
            print("README is stale — run: python scripts/generate_profile_readme.py")
            return 1
        print("README is up to date with GitHub API + profile.yml")
        return 0

    if args.dry_run:
        sys.stdout.write(updated)
        return 0

    if original == updated:
        print("No changes.")
        return 0

    README.write_text(updated, encoding="utf-8", newline="\n")
    print(f"Updated {README.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
