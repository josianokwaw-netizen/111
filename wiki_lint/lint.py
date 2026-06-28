#!/usr/bin/env python3
"""
Wiki Lint — 按各自 scheme 约定扫描两套 Notion 三库，每天定时运行。

本脚本同时复检两套独立的知识系统，每套都依据自己的 scheme 约定：
  • x scheme   — https://app.notion.com/p/9db8335c510182f0bb2d01918f8b6f13
  • 小咪 scheme — https://app.notion.com/p/3808335c510181ab91bce0d212f58457
每套系统各有独立的「源库 / 维基库 / 日志库」，复检结果分别写回各自的日志库，
并汇总成一份报告供 GitHub Actions 发 Issue 存档。

Lint复检清单（完全按 scheme 约定）：
  ── 维基层 ──
  1. 孤儿页     — 无「依据源」且无「相关页」→ 自动标记 `待复检`
  2. 过时页     — 信号分<2，或非「过时」状态但3个月未更新 → 自动标记 `过时`
  3. 缺一句话摘要 — 「一句话摘要」为空（scheme 必填字段）
  4. 未解决矛盾  — 页面标记含「⚠️有矛盾」
  5. 待合并页   — 页面标记含「📥待合并」
  6. 内容相似页  — 页面标记含「🔁内容相似」
  7. 存疑页     — 页面标记含「❓存疑」
  8. 高频缺页   — Gemini 分析摘要/综合页，找高频但无独立实体/概念页的术语
  ── 源库层 ──
  9. 长期待摄入  — 状态=待摄入 且 加入超过7天
  10. 孤儿源    — 状态=已摄入 但无「相关维基页」关联
  ── 错字层 ──
  11. 错字页    — Gemini 扫描标题+摘要+正文，找中文错别字（需 GEMINI_API_KEY）

仅报告，不自动改写 Notion 状态。请按报告建议手动处理。
写入日志：完成后往各自 scheme 的 Notion 日志库写一条「复检」记录。
发现问题 → exit(1)，供 GitHub Actions 触发 Issue 通知。
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import requests

from write_log import write_log

# ── 配置 ──────────────────────────────────────────────────────────────────

NOTION_TOKEN   = os.environ["NOTION_TOKEN"]
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# 两套独立知识系统，各自依据自己的 scheme 约定复检。
# 每套含独立的 源库 / 维基库 / 日志库，复检结果写回各自的日志库。
SCHEMES = [
    {
        "name": "x scheme",
        "scheme_url": "https://app.notion.com/p/9db8335c510182f0bb2d01918f8b6f13",
        "wiki_db": "3cb8335c510183e5839681992705faaa",
        "source_db": "d748335c510182ea885201b572eddef4",
        "log_db": "36a8335c5101826296aa816dd77513f6",
    },
    {
        "name": "小咪 scheme",
        "scheme_url": "https://app.notion.com/p/3808335c510181ab91bce0d212f58457",
        "wiki_db": "e1b8335c5101836bb60f81286f082229",
        "source_db": "ec28335c510183d2a1ba01d62798874b",
        "log_db": "da58335c510183eeaaa281337dca11d4",
    },
]

BJ        = timezone(timedelta(hours=8))
NOW       = datetime.now(BJ)
CUTOFF_90 = NOW - timedelta(days=90)
CUTOFF_7  = NOW - timedelta(days=7)

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


# ── Notion REST API 封装 ──────────────────────────────────────────────────

def query_all(db_id: str) -> list[dict]:
    pages, cursor = [], None
    while True:
        payload: dict = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        r = requests.post(
            f"https://api.notion.com/v1/databases/{db_id}/query",
            headers=NOTION_HEADERS,
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
        pages.extend(data["results"])
        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]
    return pages



# ── 属性工具函数 ───────────────────────────────────────────────────────────

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


def status_of(page: dict, field: str) -> str:
    """兼容 Notion Status 类型（源库）和 Select 类型（维基库）。"""
    p = _prop(page, field)
    if p.get("type") == "status":
        v = p.get("status")
        return v["name"] if v else ""
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


def created_time_of(page: dict, field: str = "加入时间") -> datetime:
    p = _prop(page, field)
    if p.get("type") == "created_time":
        t = p.get("created_time", "")
    else:
        t = page.get("created_time", "1970-01-01T00:00:00.000Z")
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
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = (
            f"以下是知识维基的页面列表（格式：[类型] 标题：摘要）：\n\n{corpus}\n\n"
            f"已有独立「实体」或「概念」页：{existing}\n\n"
            "请找出上述内容中反复出现（≥ 3 次）、但尚无独立实体/概念页的术语/人物/工具/框架。\n"
            "只列最重要的 3–5 个，每行一个，格式：「概念名」（约 N 次）\n"
            "不要解释，不要多余文字。"
        )
        resp = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
        )
        lines = [
            ln.strip()
            for ln in resp.text.strip().splitlines()
            if ln.strip() and "」" in ln
        ]
        return lines[:5]
    except Exception as e:
        return [f"（Gemini 分析失败：{e}）"]


# ── 错字检查：抓正文 + Gemini 找错别字（可选） ────────────────────────────

def fetch_page_text(page_id: str, max_chars: int = 1500) -> str:
    """抓取页面正文纯文本（best-effort，递归一层子块，含表格单元格）。"""
    out: list[str] = []

    def total() -> int:
        return sum(len(x) for x in out)

    def walk(block_id: str, depth: int) -> None:
        if depth > 3 or total() > max_chars:
            return
        cursor = None
        while True:
            params: dict = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            try:
                r = requests.get(
                    f"https://api.notion.com/v1/blocks/{block_id}/children",
                    headers=NOTION_HEADERS,
                    params=params,
                )
                r.raise_for_status()
            except Exception:
                return
            data = r.json()
            for b in data.get("results", []):
                bt = b.get("type", "")
                payload = b.get(bt, {})
                for rt in payload.get("rich_text", []):
                    out.append(rt.get("plain_text", ""))
                # 表格行的文字藏在 cells 里
                if bt == "table_row":
                    for cell in payload.get("cells", []):
                        for rt in cell:
                            out.append(rt.get("plain_text", ""))
                if b.get("has_children"):
                    walk(b["id"], depth + 1)
                if total() > max_chars:
                    return
            if not data.get("has_more"):
                break
            cursor = data["next_cursor"]

    walk(page_id, 0)
    return "".join(out)[:max_chars]


def find_typos(entries: list[tuple[str, str, str]]) -> list[tuple]:
    """entries: [(标题, url, 待检文本)]，返回 [(标题, url, '错→正；错→正')]。"""
    if not GEMINI_API_KEY or not entries:
        return []

    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        return [("（错字检查初始化失败）", "", str(e))]

    results: list[tuple] = []
    BATCH = 12
    for i in range(0, len(entries), BATCH):
        chunk = entries[i:i + BATCH]
        numbered = []
        for idx, (t, _u, txt) in enumerate(chunk):
            body = f"{t}。{txt}".replace("\n", " ")[:1200]
            numbered.append(f"[{idx}] {body}")
        prompt = (
            "下面每行是一个条目，格式 [序号] 文本（中文知识库的标题+正文）。\n"
            "请只挑出**明显的中文错别字 / 同音异形错字 / 多余乱码字**，"
            "不要纠正风格、标点、繁简、专有名词或英文。\n"
            "对每个含错字的条目输出一行，格式：`序号|错字→正字；错字→正字`；"
            "没有错字的条目不要输出。不要解释、不要多余文字。\n\n"
            + "\n".join(numbered)
        )
        try:
            resp = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
            )
            for ln in resp.text.strip().splitlines():
                ln = ln.strip()
                if "|" not in ln or "→" not in ln:
                    continue
                pre, corr = ln.split("|", 1)
                try:
                    k = int(pre.strip().strip("[]"))
                except ValueError:
                    continue
                if 0 <= k < len(chunk):
                    t, u, _ = chunk[k]
                    results.append((t, u, corr.strip()))
        except Exception as e:
            results.append((f"（批次 {i // BATCH} 分析失败）", "", str(e)))
    return results


# ── 主检查逻辑 ────────────────────────────────────────────────────────────

def run_lint(cfg: dict) -> tuple[str, int, int, int]:
    # ── 维基库 ───────────────────────────────────────────────────────────
    wiki_pages = query_all(cfg["wiki_db"])
    total_wiki = len(wiki_pages)

    orphans: list[tuple]        = []
    outdated: list[tuple]       = []
    no_summary: list[tuple]     = []
    contradictions: list[tuple] = []
    to_merge: list[tuple]       = []
    similar: list[tuple]        = []
    uncertain: list[tuple]      = []

    # 先收集所有问题，再统一自动标记（过时优先于孤儿）
    page_issues: list[dict] = []

    for p in wiki_pages:
        t       = title_of(p)
        pid     = p["id"]
        url     = p.get("url", "")
        score   = number_of(p, "信号分")
        status  = select_of(p, "状态")
        marks   = multi_of(p, "页面标记")
        has_src = relation_any(p, "依据源")
        has_rel = relation_any(p, "相关页")
        summary = text_of(p, "一句话摘要")
        le      = last_edited(p)

        is_orphan = not has_src and not has_rel

        outdated_reasons: list[str] = []
        if score is not None and score < 2:
            outdated_reasons.append(f"信号分={score}")
        if status != "过时" and le < CUTOFF_90:
            outdated_reasons.append(f"3个月未更新（{le.strftime('%Y-%m-%d')}）")
        is_outdated = bool(outdated_reasons)

        if is_orphan:
            orphans.append((t, url, status or "—"))
        if is_outdated:
            outdated.append((t, url, "、".join(outdated_reasons)))
        if not summary.strip():
            no_summary.append((t, url, select_of(p, "页面类型") or "—"))
        if "⚠️有矛盾" in marks:
            contradictions.append((t, url))
        if "📥待合并" in marks:
            to_merge.append((t, url))
        if "🔁内容相似" in marks:
            similar.append((t, url))
        if "❓存疑" in marks:
            uncertain.append((t, url))

        # 不再自动写回 Notion，仅收集用于报告

    # 8. Gemini 高频缺页
    missing = find_missing_concepts(wiki_pages)

    # ── 源库 ─────────────────────────────────────────────────────────────
    source_pages: list[dict] = []
    try:
        source_pages = query_all(cfg["source_db"])
    except Exception as e:
        print(f"⚠️ 源库查询失败：{e}", file=sys.stderr)

    pending_old: list[tuple]    = []
    orphan_sources: list[tuple] = []

    for s in source_pages:
        t_s    = title_of(s)
        url_s  = s.get("url", "")
        st     = status_of(s, "状态")
        has_wk = relation_any(s, "相关维基页")
        ct     = created_time_of(s)

        # 9. 长期待摄入（超7天）
        if st == "待摄入" and ct < CUTOFF_7:
            pending_old.append((t_s, url_s, f"加入于 {ct.strftime('%Y-%m-%d')}"))

        # 10. 孤儿源（已摄入但无关联维基页）
        if st == "已摄入" and not has_wk:
            orphan_sources.append((t_s, url_s, "已摄入但无关联维基页"))

    # 11. 错字检查（仅在配置 Gemini 时抓正文并送检，避免无谓的 API 调用）
    typos: list[tuple] = []
    if GEMINI_API_KEY:
        typo_entries: list[tuple[str, str, str]] = []
        for p in wiki_pages:
            txt = f"{text_of(p, '一句话摘要')} {fetch_page_text(p['id'])}"
            typo_entries.append((title_of(p), p.get("url", ""), txt))
        for s in source_pages:
            txt = f"{text_of(s, '备注')} {fetch_page_text(s['id'])}"
            typo_entries.append((title_of(s), s.get("url", ""), txt))
        typos = find_typos(typo_entries)

    # ── 构建报告 ─────────────────────────────────────────────────────────
    total_wiki_issues = (
        len(orphans) + len(outdated) + len(no_summary)
        + len(contradictions) + len(to_merge) + len(similar) + len(uncertain)
    )
    total_source_issues = len(pending_old) + len(orphan_sources)
    total_issues = total_wiki_issues + total_source_issues + len(typos)

    lines = [
        f"# 🔍 {cfg['name']} · Lint 报告 · {NOW.strftime('%Y年%m月%d日')}",
        f"扫描维基页：**{total_wiki}** 个 | 源：**{len(source_pages)}** 个 | "
        f"发现问题：**{total_issues}** 个",
        "",
        "---",
        "",
        "## 📖 维基层检查",
    ]

    def section(header: str, items: list, advice: str) -> None:
        lines.append(f"\n### {header}（{len(items)} 个）")
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
        "手动补充「依据源」或「相关页」关联；确认无用则在 Notion 改为`过时`",
    )
    section(
        "2. 过时页（信号分<2 或3个月未更新）",
        outdated,
        "更新内容后手动恢复为`活跃`，或确认过时后在 Notion 改为`过时`",
    )
    section(
        "3. 缺一句话摘要（scheme 必填字段）",
        no_summary,
        "填写「一句话摘要」字段，方便索引扫读",
    )
    section(
        "4. 未解决矛盾（⚠️有矛盾）",
        contradictions,
        "在综合页补充「我的判断」后取消标记；否则进入 Wiki 首页活矛盾表追踪",
    )
    section(
        "5. 待合并页（📥待合并）",
        to_merge,
        "合并后删除多余页，更新所有关联页的「相关页」字段",
    )
    section(
        "6. 内容相似页（🔁内容相似）",
        similar,
        "判断是否合并；若保留两页则在「关系说明」字段说明差异",
    )
    section(
        "7. 存疑页（❓存疑）",
        uncertain,
        "确认存疑内容后取消标记或修正；无法确认则升级为「⚠️有矛盾」",
    )

    if missing:
        lines.append(f"\n### 8. 高频概念缺页（Gemini 分析，共 {len(missing)} 条）")
        for c in missing:
            lines.append(f"- {c}")
        lines.append("\n> 建议：新建对应实体或概念页并回链至相关摘要/综合页")
    else:
        lines.append("\n### 8. 高频概念缺页（Gemini 分析）")
        lines.append("✅ 无（或未配置 GEMINI_API_KEY）")

    # ── 活矛盾表（未解决矛盾汇总，供 Wiki 首页维护参考） ──────────────────
    if contradictions:
        lines.append("\n---\n\n## ⚠️ 活矛盾表（需在 Wiki 首页维护）")
        lines.append("以下页面标记了「⚠️有矛盾」但尚未写明「我的判断」，请逐一处理：")
        for name, url in contradictions:
            lines.append(f"- [ ] [{name}]({url})")
        lines.append(
            "\n> 处理方式：在综合页写明「我的判断」后取消 ⚠️有矛盾 标记；"
            "如无综合页则先新建。全部处理完后删除本表条目。"
        )

    lines += [
        "",
        "---",
        "",
        "## 📚 源库层检查",
    ]

    def source_section(header: str, items: list, advice: str) -> None:
        lines.append(f"\n### {header}（{len(items)} 个）")
        if items:
            for row in items:
                name, url = row[0], row[1]
                note = f" — {row[2]}" if len(row) > 2 and row[2] else ""
                lines.append(f"- [{name}]({url}){note}")
            lines.append(f"\n> 建议：{advice}")
        else:
            lines.append("✅ 无")

    source_section(
        "9. 长期待摄入（超7天未处理）",
        pending_old,
        "决定走 Ingest 流程或从队列移除",
    )
    source_section(
        "10. 孤儿源（已摄入但无关联维基页）",
        orphan_sources,
        "补充「相关维基页」关联；或确认是否需要补建摘要页",
    )

    lines += [
        "",
        "---",
        "",
        "## ✏️ 错字层检查",
    ]
    if not GEMINI_API_KEY:
        lines.append("\n### 11. 错字页（Gemini 扫描标题+摘要+正文）")
        lines.append("⏭️ 跳过（未配置 GEMINI_API_KEY）")
    else:
        lines.append(f"\n### 11. 错字页（Gemini 扫描标题+摘要+正文）（{len(typos)} 个）")
        if typos:
            for name, url, corr in typos:
                link = f"[{name}]({url})" if url else name
                lines.append(f"- {link} — {corr}")
            lines.append("\n> 建议：在 Notion 逐处订正错别字；专有名词/英文误报可忽略")
        else:
            lines.append("✅ 无")

    lines += [
        "",
        "---",
        "*仅报告，不自动改写 Notion 状态。请按建议手动处理后在 Notion 更新状态。*",
        "*由 GitHub Actions 自动生成 · "
        f"scheme: [{cfg['name']}]({cfg['scheme_url']}) · 数据来源 Notion 三库*",
    ]
    return "\n".join(lines), total_issues, total_wiki


# ── 入口 ───────────────────────────────────────────────────────────────────

def main() -> None:
    reports: list[str] = []
    grand_total = 0

    for cfg in SCHEMES:
        try:
            report, total_issues, page_count = run_lint(cfg)
        except Exception as e:
            grand_total += 1  # 让 CI 标红，便于发现某套系统复检失败
            reports.append(
                f"# 🔍 {cfg['name']} · Lint 报告 · {NOW.strftime('%Y年%m月%d日')}\n"
                f"⚠️ 复检失败：{e}"
            )
            print(f"⚠️ [{cfg['name']}] 复检失败：{e}", file=sys.stderr)
            continue

        reports.append(report)
        grand_total += total_issues

        # 复检结果写回各自 scheme 的日志库
        try:
            write_log(
                op="复检",
                title=f"{NOW.strftime('%Y-%m-%d')} 定时复检",
                detail=(
                    f"[{cfg['name']}] 扫描 {page_count} 个维基页，发现 {total_issues} 个问题"
                ),
                log_db_id=cfg["log_db"],
            )
        except Exception as e:
            print(
                f"\n⚠️ [{cfg['name']}] Notion 日志写入失败：{e}",
                file=sys.stderr,
            )

    # 汇总两套系统的报告，供 GitHub Actions 发同一条 Issue 存档
    print("\n\n" + ("\n\n" + "=" * 60 + "\n\n").join(reports))

    sys.exit(1 if grand_total > 0 else 0)


if __name__ == "__main__":
    main()
