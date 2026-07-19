#!/usr/bin/env python3
"""
Generate AUTO sections in profile README from GitHub API + config/profile.yml.

AUTO blocks produced:
  PROJECTS  — 项目按方向分组的表（config.groups 决定分组与顺序）
  LANGS     — 语言分布 Unicode 条形（公开非 fork 仓库主语言计数）
  RECENT    — 最近 push 的公开仓库
  META      — 自动同步元信息（时间 / 仓库数）

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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
CONFIG = ROOT / "config" / "profile.yml"

MARKERS = {
    "projects": (
        "<!-- AUTO:PROJECTS:START -->",
        "<!-- AUTO:PROJECTS:END -->",
    ),
    "langs": (
        "<!-- AUTO:LANGS:START -->",
        "<!-- AUTO:LANGS:END -->",
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
        raise SystemExit(
            "PyYAML is required. Install: pip install pyyaml\n"
            "Or in CI: pip install -r scripts/requirements.txt"
        )
    if not isinstance(data, dict):
        raise SystemExit("config/profile.yml must be a mapping")
    return data


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
    parts: list[str] = []
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
    return esc_cell(repo.get("description") or "")


def public_repos(repos: list[dict]) -> list[dict]:
    """公开、非 fork、未归档 —— 代表本人真实产出（不套项目表 exclude）。"""
    return [
        r
        for r in repos
        if not r.get("fork") and not r.get("private") and not r.get("archived")
    ]


def curated_by_name(repos: list[dict], cfg: dict) -> dict[str, dict]:
    """进入项目表候选：公开非 fork 非归档，且不在 exclude。"""
    exclude = set(cfg.get("exclude") or [])
    return {r["name"]: r for r in public_repos(repos) if r["name"] not in exclude}


def group_projects(by_name: dict[str, dict], cfg: dict) -> list[tuple[str, str, list[dict]]]:
    """返回 [(title, blurb, [repo,...]), ...]；未分组仓库归入「🗂 其它」。"""
    overrides = cfg.get("overrides") or {}
    groups_cfg = cfg.get("groups") or []
    used: set[str] = set()
    out: list[tuple[str, str, list[dict]]] = []

    def attach(r: dict) -> dict:
        name = r["name"]
        r["_tech"] = lang_tech(r)
        r["_skill"] = skill_for(name, r, overrides)
        return r

    for g in groups_cfg:
        items: list[dict] = []
        for nm in g.get("repos") or []:
            if nm in by_name and nm not in used:
                items.append(attach(by_name[nm]))
                used.add(nm)
        if items:
            title = str(g.get("title") or g.get("key") or "项目")
            out.append((title, str(g.get("blurb") or ""), items))

    rest = [
        attach(by_name[nm])
        for nm in sorted(
            by_name,
            key=lambda n: by_name[n].get("pushed_at") or "",
            reverse=True,
        )
        if nm not in used
    ]
    if rest:
        out.append(("🗂 其它", "", rest))
    return out


def render_projects(grouped: list[tuple[str, str, list[dict]]], max_n: int) -> str:
    out: list[str] = []
    count = 0
    for title, blurb, items in grouped:
        rows: list[str] = []
        for r in items:
            if count >= max_n:
                break
            name = r["name"]
            url = r.get("html_url") or f"https://github.com/WJH-makers/{name}"
            home = r.get("homepage") or ""
            link = f"[{name}]({url})"
            if home and str(home).startswith("http"):
                link += f" · [↗]({home})"
            rows.append(f"| {link} | {esc_cell(r['_tech'])} | {esc_cell(r['_skill'])} |")
            count += 1
        if not rows:
            continue
        head = f"**{esc_cell(title)}**"
        if blurb:
            head += f"　<sub>{esc_cell(blurb)}</sub>"
        out.append(head)
        out.append("")
        out.append("| 项目 | 技术栈 | 练到的能力 |")
        out.append("|---|---|---|")
        out.extend(rows)
        out.append("")
    out.append(
        "<sub>本区块由 <code>scripts/generate_profile_readme.py</code> 依公开仓库 API "
        "+ <code>config/profile.yml</code> 自动生成 · 新仓库写好 description / topics "
        "并在 config 里归组即可入表。</sub>"
    )
    return "\n".join(out)


def render_langs(pub: list[dict], cfg: dict) -> str:
    n = int(cfg.get("lang_bar_count") or 8)
    counts: dict[str, int] = {}
    for r in pub:
        lang = r.get("language")
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return "_暂无语言数据_"
    total = sum(counts.values())
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]
    max_c = max(c for _, c in top)
    width = 22
    label_w = max(len(k) for k, _ in top)
    lines = ["```text"]
    for lang, c in top:
        filled = max(1, round(width * c / max_c))
        bar = "█" * filled + "░" * (width - filled)
        pct = 100.0 * c / total
        lines.append(f"{lang:<{label_w}}  {bar}  {c:>2} repo · {pct:4.1f}%")
    lines.append("```")
    return "\n".join(lines)


def render_recent(repos: list[dict], cfg: dict) -> str:
    exclude = set(cfg.get("exclude") or [])
    overrides = cfg.get("overrides") or {}
    n = int(cfg.get("recent_count") or 6)
    items = [
        r
        for r in repos
        if not r.get("fork") and not r.get("private") and r["name"] not in exclude
    ][:n]
    if not items:
        return "_暂无公开动态_"
    lines = []
    for r in items:
        name = r["name"]
        url = r.get("html_url") or f"https://github.com/WJH-makers/{name}"
        when = (r.get("pushed_at") or "")[:10]
        desc = description_for(name, r, overrides)
        bit = f"- **[{name}]({url})**　<sub>`{when}`</sub>"
        if desc:
            bit += f" — {desc[:100]}"
        lines.append(bit)
    return "\n".join(lines)


def render_meta(grouped: list[tuple[str, str, list[dict]]], pub: list[dict]) -> str:
    langs: dict[str, int] = {}
    for r in pub:
        lang = r.get("language")
        if lang:
            langs[lang] = langs.get(lang, 0) + 1
    top_langs = ", ".join(
        f"{k}×{v}"
        for k, v in sorted(langs.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    )
    shown = sum(len(items) for _, _, items in grouped)
    return (
        f"<sub>🤖 项目 / 语言 / 动态由 GitHub Actions 依公开仓库自动同步 · "
        f"公开非 fork 仓库 <b>{len(pub)}</b> 个 · 项目表展示 <b>{shown}</b> 个 · "
        f"语言分布：{top_langs or '—'}</sub>"
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
    pub = public_repos(repos)
    by_name = curated_by_name(repos, cfg)
    grouped = group_projects(by_name, cfg)
    max_n = int(cfg.get("max_projects") or 20)

    text = readme_text
    text = replace_block(text, *MARKERS["projects"], render_projects(grouped, max_n))
    text = replace_block(text, *MARKERS["langs"], render_langs(pub, cfg))
    text = replace_block(text, *MARKERS["recent"], render_recent(repos, cfg))
    text = replace_block(text, *MARKERS["meta"], render_meta(grouped, pub))
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
