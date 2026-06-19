#!/usr/bin/env python3
"""
Wiki Lint — 按照 scheme 约定扫描 Notion 维基库，每周一运行。

检查项（对应 scheme Lint 复检清单）：
  1. 孤儿页     — 无「依据源」且无「相关页」关联
  2. 过时页     — 信号分 < 2，或「活跃」状态但 90 天未更新
  3. 未解决矛盾  — 页面标记含「⚠️有矛盾」
  4. 待合并页   — 页面标记含「📥待合并」
  5. 高频缺页   — Gemini 分析一句话摘要，找高频但无独立页的概念（需 GEMINI_API_KEY）

完成后往 Notion 日志库写一条「复检」记录。
发现问题 → exit(1)，供 GitHub Actions 触发 Issue 通知。
"""

import os
import sys
from datetime import datetime, timedelta, timezone

from notion_client import Client

# ── 配置 ──────────────────────────────────────────────────────────────────

NOTION_TOKEN   = os.environ["NOTION_TOKEN"]
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

WIKI_DB_ID = "3cb8335c510183e5839681992705faaa"
LOG_DB_ID  = "36a8335c5101826296aa816dd77513f6"

BJ        = timezone(timedelta(hours=8))
NOW       = datetime.now(BJ)
CUTOFF_90 = NOW - timedelta(days=90)

notion = Client(auth=NOTION_TOKEN)


# ── Notion 工具函数 ────────────────────────────────────────────────────────

def query_all(db_id: str) -> list[dict]:
    pages, cursor = [], None
    while True:
        r = notion.databases.query(
            database_id=db_id, start_cursor=cursor, page_size=100
        )
        pages.extend(r["results"])
        if not r.get("has_more"):
            break
        cursor = r["next_cursor"]
    return pages


def _prop(page: dict, field: str) -> dict:
    return page["properties"].get(field, {})


def title_of(page: dict) -> str:
    for p in page["properties"].values():
        if p.get("type") == "title":
            return "".join(t["plain_text"] for t in p.get("title", []))
    return "(无标题)"


def select_of(page: dict, field: str) -> str:
    p = _prop(page, field)
    if p.get("type") == "select":
        v = p.get("select")
        return v["name"] if v else ""
    return ""


def multi_of(page: dict, field: str) -> list[str]:
    p = _prop(page, field)
    if p.get("type") == "multi_select":
        return [v["name"] for v in p.get("multi_select", [])]
    return []


def number_of(page: dict, field: str) -> float | None:
    p = _prop(page, field)
    return p.get("number") if p.get("type") == "number" else None


def text_of(page: dict, field: str) -> str:
    p = _prop(page, field)
    if p.get("type") == "rich_text":
        return "".join(t["plain_text"] for t in p.get("rich_text", []))
    return ""


def relation_any(page: dict, field: str) -> bool:
    """该关联字段是否有至少一个关联（含 has_more 截断的情况）。"""
    p = _prop(page, field)
    if p.get("type") != "relation":
        return False
    return bool(p.get("relation")) or bool(p.get("has_more"))


def last_edited(page: dict) -> datetime:
    p = _prop(page, "最近更新")
    if p.get("type") == "last_edited_time":
        t = p.get("last_edited_time", "")
    else:
        t = page.get("last_edited_time", "1970-01-01T00:00:00.000Z")
    return datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(BJ)


# ── Gemini：高频缺页分析（可选） ──────────────────────────────────────────

def find_missing_concepts(pages: list[dict]) -> list[str]:
    if not GEMINI_API_KEY:
        return []

    entity_titles = {
        title_of(p) for p in pages
        if select_of(p, "页面类型") in {"实体", "概念"}
    }

    corpus_lines = []
    for p in pages:
        pt = select_of(p, "页面类型")
        if pt not in {"摘要", "综合", "总览"}:
            continue
        t = title_of(p)
        s = text_of(p, "一句话摘要")
        if t or s:
            corpus_lines.append(f"[{pt}] {t}：{s}")

    if not corpus_lines:
        return []

    corpus   = "\n".join(corpus_lines[:200])
    existing = "、".join(list(entity_titles)[:40]) or "（无）"

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = (
            f"以下是知识维基的页面列表（格式：[类型] 标题：摘要）：\n\n{corpus}\n\n"
            f"已有独立「实体」或「概念」页：{existing}\n\n"
            "请找出上述内容中反复出现（≥ 3 次）、但尚无独立实体/概念页的术语/人物/工具/框架。\n"
            "只列最重要的 3–5 个，每行一个，格式：「概念名」（约 N 次）\n"
            "不要解释，不要多余文字。"
        )
        resp  = model.generate_content(prompt)
        lines = [
            l.strip()
            for l in resp.text.strip().splitlines()
            if l.strip() and "」" in l
        ]
        return lines[:5]
    except Exception as e:
        return [f"（Gemini 分析失败：{e}）"]


# ── 主检查逻辑 ────────────────────────────────────────────────────────────

def run_lint() -> tuple[str, int, int]:
    pages = query_all(WIKI_DB_ID)
    total = len(pages)

    orphans: list[tuple]        = []
    outdated: list[tuple]       = []
    contradictions: list[tuple] = []
    to_merge: list[tuple]       = []

    for p in pages:
        t       = title_of(p)
        url     = p.get("url", "")
        score   = number_of(p, "信号分")
        status  = select_of(p, "状态")
        marks   = multi_of(p, "页面标记")
        has_src = relation_any(p, "依据源")
        has_rel = relation_any(p, "相关页")
        le      = last_edited(p)

        # 1. 孤儿页
        if not has_src and not has_rel:
            orphans.append((t, url, status or "—"))

        # 2. 过时页
        reasons = []
        if score is not None and score < 2:
            reasons.append(f"信号分={score}")
        if status == "活跃" and le < CUTOFF_90:
            reasons.append(f"90天未更新（{le.strftime('%Y-%m-%d')}）")
        if reasons:
            outdated.append((t, url, "、".join(reasons)))

        # 3. 未解决矛盾
        if "⚠️有矛盾" in marks:
            contradictions.append((t, url))

        # 4. 待合并
        if "📥待合并" in marks:
            to_merge.append((t, url))

    # 5. Gemini 高频缺页
    missing = find_missing_concepts(pages)

    # ── 构建报告 ────────────────────────────────────────────────────────
    total_issues = (
        len(orphans) + len(outdated) + len(contradictions) + len(to_merge)
    )
    lines = [
        f"# 🔍 Wiki Lint 报告 · {NOW.strftime('%Y年%m月%d日')}",
        f"扫描维基页：**{total}** 个 | 发现问题：**{total_issues}** 个",
        "",
        "---",
    ]

    def section(header: str, items: list, advice: str) -> None:
        lines.append(f"\n## {header}（{len(items)} 个）")
        if items:
            for row in items:
                name, url = row[0], row[1]
                note = f" — {row[2]}" if len(row) > 2 and row[2] else ""
                lines.append(f"- [{name}]({url}){note}")
            lines.append(f"\n> 建议：{advice}")
        else:
            lines.append("✅ 无")

    section(
        "1. 孤儿页（无依据源 & 无相关页）",
        orphans,
        "补充「依据源」或「相关页」关联；确认无用则将状态改为`过时`",
    )
    section(
        "2. 过时页",
        outdated,
        "更新内容或将状态改为`过时`",
    )
    section(
        "3. 未解决矛盾（页面标记含 ⚠️有矛盾）",
        contradictions,
        "确认对应综合页已含「我的判断」后取消标记；否则在综合页补充判断",
    )
    section(
        "4. 待合并页（页面标记含 📥待合并）",
        to_merge,
        "合并后删除多余页，并更新所有关联页的「相关页」字段",
    )

    if missing:
        lines.append(f"\n## 5. 高频概念缺页（Gemini 分析，共 {len(missing)} 条）")
        for c in missing:
            lines.append(f"- {c}")
        lines.append("\n> 建议：考虑新建对应实体或概念页并回链")

    lines += [
        "",
        "---",
        "*由 GitHub Actions 自动生成 · 数据来源 Notion 维基库*",
    ]
    return "\n".join(lines), total_issues, total


# ── Notion 日志写入 ──────────────────────────────────────────────────────

def write_log(total_issues: int, page_count: int) -> None:
    summary = f"扫描 {page_count} 个维基页，发现 {total_issues} 个问题"
    notion.pages.create(
        parent={"database_id": LOG_DB_ID},
        properties={
            "条目": {
                "title": [{"text": {"content": f"[Lint] {NOW.strftime('%Y-%m-%d')} 定时复检"}}]
            },
            "操作": {"select": {"name": "复检"}},
            "日期":  {"date": {"start": NOW.strftime("%Y-%m-%d")}},
            "详情":  {"rich_text": [{"text": {"content": summary}}]},
        },
    )


# ── 入口 ───────────────────────────────────────────────────────────────────

def main() -> None:
    report, total_issues, page_count = run_lint()
    print(report)

    try:
        write_log(total_issues, page_count)
        print("\n✅ 日志已写入 Notion（操作：复检）", file=sys.stderr)
    except Exception as e:
        print(f"\n⚠️ Notion 日志写入失败：{e}", file=sys.stderr)

    sys.exit(1 if total_issues > 0 else 0)


if __name__ == "__main__":
    main()
