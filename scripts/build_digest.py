#!/usr/bin/env python3
"""构建 AI 早报 digest.md。

数据来源：
  - AI Hot   (aihot.virxact.com 公开 API)  —— 主新闻体
  - BestBlogs (RSS, AI 精选, 24h 窗口 + 去重)
  - AIGC Weekly · 归藏 (Atom, 去重，发布当天出现一次)
  - TW93 博客 (RSS, 去重)

输出：
  digest.md            —— issue 正文（无内容时为空文件）
  data/feeds/new_ids.txt —— 本次新纳入的去重 ID（由 workflow 合并进 seen.txt）
"""
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta

import requests
import feedparser

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 aihot-skill/0.3.0")

BJ = timezone(timedelta(hours=8))
NOW_UTC = datetime.now(timezone.utc)
NOW_BJ = NOW_UTC.astimezone(BJ)

STATE_FILE  = "data/feeds/seen.txt"
NEWIDS_FILE = "data/feeds/new_ids.txt"
DIGEST_FILE = "digest.md"

os.makedirs("data/feeds", exist_ok=True)

# ── 读取去重记录 ─────────────────────────────────────────────
seen = set()
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, encoding="utf-8") as f:
        seen = {l.strip() for l in f if l.strip()}

new_ids = []

# ── 1. AI Hot 公开 API ───────────────────────────────────────
def _json(url):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        if not r.ok:
            return []
        d = r.json()
        return d if isinstance(d, list) else d.get("items", d.get("data", []))
    except Exception as ex:
        print(f"WARN aihot {url}: {ex}")
        return []

aihot_items = _json("https://aihot.virxact.com/api/public/daily")
if not aihot_items:
    aihot_items = _json("https://aihot.virxact.com/api/public/items?mode=selected&since=1")
aihot_items = aihot_items or []

CAT_MAP = {
    "model":    "🤖 模型发布",
    "product":  "📦 产品动态",
    "industry": "🏭 行业新闻",
    "paper":    "📄 论文前沿",
    "tutorial": "💡 实用技巧",
    "tool":     "🛠️ 工具资讯",
    "research": "🔬 研究动态",
}

# ── 2. RSS / Atom 信息源 ─────────────────────────────────────
RSS_SOURCES = [
    {"name": "BestBlogs 精选",
     "url":  "https://www.bestblogs.dev/zh/feeds/rss?category=ai&featured=y&language=all",
     "mode": "window", "hours": 24, "limit": 4},
    {"name": "AIGC Weekly · 归藏",
     "url":  "https://quaily.com/op7418/feed/atom",
     "mode": "dedup", "max_age_days": 14, "limit": 2},
    {"name": "TW93 博客",
     "url":  "https://tw93.fun/feed.xml",
     "mode": "dedup", "max_age_days": 30, "limit": 2},
]

def entry_time(e):
    t = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
    if t:
        return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
    return None

def strip_html(text, n=160):
    text = re.sub(r"<[^>]+>", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:n] + ("…" if len(text) > n else "")

blog_groups = []  # [(source_name, [(entry, eid, et), ...]), ...]
for src in RSS_SOURCES:
    try:
        feed = feedparser.parse(src["url"], agent=UA)
    except Exception as ex:
        print(f"WARN feed {src['name']}: {ex}")
        continue
    if getattr(feed, "bozo", 0) and not feed.entries:
        print(f"WARN feed {src['name']} 解析为空 / bozo")
        continue

    picked = []
    for e in feed.entries:
        link = e.get("link") or ""
        if not link:
            continue
        eid = f"{src['name']}::{e.get('id') or link}"
        et = entry_time(e)

        if src["mode"] == "window":
            if et is None or et < NOW_UTC - timedelta(hours=src["hours"]):
                continue
            if eid in seen:
                continue
        else:  # dedup
            if eid in seen:
                continue
            if et is not None and et < NOW_UTC - timedelta(days=src["max_age_days"]):
                continue

        picked.append((e, eid, et))
        if len(picked) >= src["limit"]:
            break

    if picked:
        blog_groups.append((src["name"], picked))
        new_ids.extend(eid for _, eid, _ in picked)
        print(f"  {src['name']}: 纳入 {len(picked)} 条")

# ── 3. 无内容则写空文件并退出 ────────────────────────────────
if not aihot_items and not blog_groups:
    open(DIGEST_FILE, "w", encoding="utf-8").write("")
    open(NEWIDS_FILE, "w", encoding="utf-8").write("")
    print("今日无内容。")
    sys.exit(0)

# ── 4. 组装 Markdown ─────────────────────────────────────────
lines = [f"# 🌅 AI 早报 · {NOW_BJ.strftime('%Y年%m月%d日')}\n"]

highlights = [it["title"].strip() for it in aihot_items[:2] if it.get("title")]
if not highlights:
    for _name, picked in blog_groups:
        highlights.append(picked[0][0].get("title", "").strip())
        break
if highlights:
    lines.append(f"> **今日看点：** {'，'.join(highlights)}\n")
lines.append("---\n")

# 4a. AI Hot 分类（最多 12 条）
groups = {}
for item in aihot_items[:24]:
    label = CAT_MAP.get(item.get("category", "other"), "📰 其他")
    groups.setdefault(label, []).append(item)

count = 0
for label, grp in groups.items():
    if count >= 12:
        break
    lines.append(f"## {label}\n")
    for item in grp:
        if count >= 12:
            break
        title   = (item.get("title") or "").strip()
        summary = (item.get("summary") or item.get("description") or "").strip()
        url     = item.get("url") or item.get("link") or ""
        pub     = item.get("published_at") or item.get("created_at") or ""
        try:
            t = datetime.fromisoformat(pub.replace("Z", "+00:00")).astimezone(BJ).strftime("%H:%M")
        except Exception:
            t = ""
        lines.append(f"**{title}**{'  `' + t + '`' if t else ''}")
        if summary:
            lines.append(f"> {summary[:150]}{'...' if len(summary) > 150 else ''}")
        if url:
            lines.append(f"[→ 阅读原文]({url})\n")
        count += 1

# 4b. 博客 / 深度阅读
if blog_groups:
    lines.append("## 📚 深度阅读 / 博客精选\n")
    for name, picked in blog_groups:
        lines.append(f"### {name}\n")
        for e, _eid, et in picked:
            title   = (e.get("title") or "").strip()
            link    = e.get("link") or ""
            summary = strip_html(e.get("summary") or e.get("description") or "")
            t = et.astimezone(BJ).strftime("%m-%d") if et else ""
            lines.append(f"**{title}**{'  `' + t + '`' if t else ''}")
            if summary:
                lines.append(f"> {summary}")
            if link:
                lines.append(f"[→ 阅读原文]({link})\n")

lines += ["---",
          "*由 GitHub Actions 自动生成 · 数据来源 aihot.virxact.com / bestblogs.dev / "
          "quaily.com(op7418) / tw93.fun*"]

open(DIGEST_FILE, "w", encoding="utf-8").write("\n".join(lines))
open(NEWIDS_FILE, "w", encoding="utf-8").write("\n".join(new_ids))
print(f"digest 生成：aihot {min(count, len(aihot_items))} 条 / "
      f"博客 {sum(len(p) for _, p in blog_groups)} 条 / 新增去重 ID {len(new_ids)} 个")
