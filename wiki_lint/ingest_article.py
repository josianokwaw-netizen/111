#!/usr/bin/env python3
"""
ingest_article.py — 从 letta/pending_ingest.json 读取文章，
按 x scheme 规范写入 Notion 三库（源库 + 维基库 + 日志库）。

执行流程：
  1. 在源库创建一条源记录（原文保留在页面正文）
  2. 在维基库为每个知识点创建/更新分类页
  3. 更新源记录，关联所有维基页
  4. 在日志库写操作记录
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

# ── 配置 ──────────────────────────────────────────────────────────────────
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
BJ = timezone(timedelta(hours=8))

# x scheme 三库 ID
SOURCE_DB = "d748335c-5101-82ea-8852-01b572eddef4"
WIKI_DB   = "3cb8335c-5101-83e5-8396-81992705faaa"
LOG_DB    = "36a8335c-5101-8262-96aa-816dd77513f6"

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

INGEST_FILE = os.path.join(os.path.dirname(__file__), "..", "letta", "pending_ingest.json")


# ── Notion REST 封装 ──────────────────────────────────────────────────────

def create_page(payload: dict) -> dict:
    r = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=payload)
    if not r.ok:
        print(f"  ❌ create_page {r.status_code}: {r.text[:500]}", file=sys.stderr)
    r.raise_for_status()
    return r.json()


def update_page(page_id: str, props: dict) -> dict:
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=HEADERS,
        json={"properties": props},
    )
    if not r.ok:
        print(f"  ❌ update_page {r.status_code}: {r.text[:500]}", file=sys.stderr)
    r.raise_for_status()
    return r.json()


def append_blocks(page_id: str, blocks: list) -> None:
    """分批写入（Notion 单次最多100块）。"""
    for i in range(0, len(blocks), 90):
        chunk = blocks[i:i+90]
        r = requests.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=HEADERS,
            json={"children": chunk},
        )
        r.raise_for_status()
        time.sleep(0.3)


# ── 块构造器 ─────────────────────────────────────────────────────────────

def h1(text: str) -> dict:
    return {"object": "block", "type": "heading_1",
            "heading_1": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]}}


def h2(text: str) -> dict:
    return {"object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]}}


def para(text: str) -> dict:
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]}}


def bullet(text: str) -> dict:
    return {"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]}}


def divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def md_to_blocks(markdown: str) -> list:
    """把 markdown 文本转为 Notion 块列表（简单实现）。"""
    blocks = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("## "):
            blocks.append(h2(stripped[3:]))
        elif stripped.startswith("# "):
            blocks.append(h1(stripped[2:]))
        elif stripped.startswith("- ") or stripped.startswith("* "):
            blocks.append(bullet(stripped[2:]))
        elif stripped.startswith("| "):
            blocks.append(para(stripped))
        else:
            # 超过2000字符需分段
            while len(stripped) > 1900:
                blocks.append(para(stripped[:1900]))
                stripped = stripped[1900:]
            if stripped:
                blocks.append(para(stripped))
    return blocks


# ── 主流程 ────────────────────────────────────────────────────────────────

def main() -> None:
    with open(INGEST_FILE, encoding="utf-8") as f:
        data = json.load(f)

    title       = data["title"]
    summary     = data["summary"]
    full_text   = data["full_text"]
    wiki_items  = data["wiki_items"]   # list of {title, type, summary, content}
    today       = datetime.now(BJ).strftime("%Y-%m-%d")

    print(f"▶ 摄入：{title}")

    # ── 1. 创建源记录 ──────────────────────────────────────────────────────
    source_props = {
        "名称": {"title": [{"text": {"content": title}}]},
        "状态": {"status": {"name": "已摄入"}},
        "加入时间": {"date": {"start": today}},
        "一句话摘要": {"rich_text": [{"text": {"content": summary[:2000]}}]},
    }
    source_page = create_page({
        "parent": {"database_id": SOURCE_DB},
        "properties": source_props,
    })
    source_id  = source_page["id"]
    source_url = source_page.get("url", "")
    print(f"  ✅ 源库页面创建: {source_url}")

    # 写入原文正文
    source_blocks = [h1("原文"), divider()] + md_to_blocks(full_text)
    append_blocks(source_id, source_blocks)
    print(f"  ✅ 原文写入完成（{len(source_blocks)} 块）")

    # ── 2. 创建维基页 ──────────────────────────────────────────────────────
    wiki_ids = []
    wiki_urls = []

    for item in wiki_items:
        wiki_props = {
            "名称": {"title": [{"text": {"content": item["title"]}}]},
            "页面类型":  {"select": {"name": item["type"]}},
            "一句话摘要": {"rich_text": [{"text": {"content": item["summary"][:2000]}}]},
            "依据源": {"relation": [{"id": source_id}]},
        }
        wp = create_page({
            "parent": {"database_id": WIKI_DB},
            "properties": wiki_props,
        })
        wid  = wp["id"]
        wurl = wp.get("url", "")
        wiki_ids.append(wid)
        wiki_urls.append(wurl)
        print(f"  ✅ 维基页创建: [{item['type']}] {item['title']}  {wurl}")

        # 写入内容
        if item.get("content"):
            wblocks = md_to_blocks(item["content"])
            if wblocks:
                append_blocks(wid, wblocks)
        time.sleep(0.3)

    # ── 3. 更新源记录：关联维基页 ──────────────────────────────────────────
    update_page(source_id, {
        "相关维基页": {"relation": [{"id": i} for i in wiki_ids]},
    })
    print(f"  ✅ 源记录关联 {len(wiki_ids)} 个维基页")

    # ── 4. 写日志 ──────────────────────────────────────────────────────────
    detail = f"摄入研究报告「{title}」，新建{len(wiki_items)}个维基页，原文已保留在源库"
    log_props = {
        "条目":   {"title": [{"text": {"content": f"[摄入] {title}"}}]},
        "操作":   {"select": {"name": "摄入"}},
        "日期":   {"date": {"start": today}},
        "详情":   {"rich_text": [{"text": {"content": detail[:2000]}}]},
        "关联维基页": {"relation": [{"id": i} for i in wiki_ids]},
        "相关源":     {"relation": [{"id": source_id}]},
    }
    log_page = create_page({"parent": {"database_id": LOG_DB}, "properties": log_props})
    print(f"  ✅ 日志已写入: {log_page.get('url', '')}")

    # ── 完成摘要 ──────────────────────────────────────────────────────────
    print("\n========== 摄入完成 ==========")
    print(f"源库页面:  {source_url}")
    for i, (item, url) in enumerate(zip(wiki_items, wiki_urls)):
        print(f"维基页 {i+1}: [{item['type']}] {item['title']}")
        print(f"          {url}")


if __name__ == "__main__":
    main()
