#!/usr/bin/env python3
"""
write_log.py — 往 Notion 日志库写一条操作记录（按 scheme 约定格式）。

CLI 用法：
  python wiki_lint/write_log.py \\
    --op 摄入 \\
    --title "Reddit方法论帖子" \\
    --detail "摄入 Reddit 方法论，新建摘要页，更新内容营销总览" \\
    [--wiki  "notion-url-or-id,…"] \\
    [--source "notion-url-or-id,…"]

--op 可选值：摄入 / 查询 / 复检 / 维护 / Schema更新 / 合并 / 删除

模块用法：
  from write_log import write_log
  write_log(op="复检", title="定时复检", detail="…")
"""

import argparse
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests

# 默认日志库 = x scheme 日志库（向后兼容）。
# lint.py 会按各 scheme 显式传入对应的 log_db_id。
LOG_DB_ID = "36a8335c5101826296aa816dd77513f6"
BJ = timezone(timedelta(hours=8))

VALID_OPS = ["摄入", "查询", "复检", "维护", "Schema更新", "合并", "删除"]


def _extract_id(url_or_id: str) -> str:
    clean = re.sub(r"[^0-9a-fA-F]", "", url_or_id.split("?")[0].split("/")[-1])
    if len(clean) == 32:
        return f"{clean[:8]}-{clean[8:12]}-{clean[12:16]}-{clean[16:20]}-{clean[20:]}"
    if re.fullmatch(r"[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", url_or_id.strip()):
        return url_or_id.strip()
    return url_or_id.strip()


def write_log(
    op: str,
    title: str,
    detail: str,
    date: str | None = None,
    wiki_pages: list[str] | None = None,
    source_pages: list[str] | None = None,
    notion_token: str | None = None,
    log_db_id: str | None = None,
) -> None:
    token = notion_token or os.environ.get("NOTION_TOKEN", "")
    if not token:
        raise RuntimeError("NOTION_TOKEN 未设置")

    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    today = date or datetime.now(BJ).strftime("%Y-%m-%d")
    entry = f"[{op}] {title}"

    props: dict = {
        "条目": {"title": [{"text": {"content": entry}}]},
        "操作": {"select": {"name": op}},
        "日期": {"date": {"start": today}},
        "详情": {"rich_text": [{"text": {"content": detail[:2000]}}]},
    }

    if wiki_pages:
        ids = [_extract_id(u) for u in wiki_pages if u.strip()]
        if ids:
            props["关联维基页"] = {"relation": [{"id": i} for i in ids]}

    if source_pages:
        ids = [_extract_id(u) for u in source_pages if u.strip()]
        if ids:
            props["相关源"] = {"relation": [{"id": i} for i in ids]}

    payload = {"parent": {"database_id": log_db_id or LOG_DB_ID}, "properties": props}
    r = requests.post(
        "https://api.notion.com/v1/pages",
        headers=headers,
        json=payload,
    )
    r.raise_for_status()
    print(f"✅ 日志已写入：{entry}  |  {detail[:60]}{'…' if len(detail)>60 else ''}")


def main() -> None:
    parser = argparse.ArgumentParser(description="往 Notion 日志库写一条操作记录")
    parser.add_argument("--op", required=True, choices=VALID_OPS)
    parser.add_argument("--title", required=True)
    parser.add_argument("--detail", required=True)
    parser.add_argument("--date")
    parser.add_argument("--wiki")
    parser.add_argument("--source")
    args = parser.parse_args()

    wiki   = [u.strip() for u in args.wiki.split(",")]   if args.wiki   else None
    source = [u.strip() for u in args.source.split(",")] if args.source else None

    try:
        write_log(
            op=args.op,
            title=args.title,
            detail=args.detail,
            date=args.date,
            wiki_pages=wiki,
            source_pages=source,
        )
    except Exception as e:
        print(f"❌ 日志写入失败：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
