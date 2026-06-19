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
  from wiki_lint.write_log import write_log
  write_log(op="复检", title="定时复检", detail="…")
"""

import argparse
import os
import re
import sys
from datetime import datetime, timedelta, timezone

from notion_client import Client

LOG_DB_ID = "36a8335c5101826296aa816dd77513f6"
BJ = timezone(timedelta(hours=8))

VALID_OPS = ["摄入", "查询", "复检", "维护", "Schema更新", "合并", "删除"]


def _extract_id(url_or_id: str) -> str:
    """从 Notion URL 或原始 ID 提取 32 位十六进制 page ID。"""
    # 去掉连字符后的 32 位 hex
    clean = re.sub(r"[^0-9a-fA-F]", "", url_or_id.split("?")[0].split("/")[-1])
    if len(clean) == 32:
        return f"{clean[:8]}-{clean[8:12]}-{clean[12:16]}-{clean[16:20]}-{clean[20:]}"
    # 已是带连字符的 UUID
    if re.fullmatch(r"[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", url_or_id.strip()):
        return url_or_id.strip()
    return url_or_id.strip()  # 原样返回，让 Notion API 报错


def write_log(
    op: str,
    title: str,
    detail: str,
    date: str | None = None,
    wiki_pages: list[str] | None = None,
    source_pages: list[str] | None = None,
    notion_token: str | None = None,
) -> None:
    """
    写一条 Notion 日志记录。

    Args:
        op:           操作类型，见 VALID_OPS
        title:        操作摘要（不含 [前缀]，函数自动添加）
        detail:       一句话说明：做了什么，结果是什么
        date:         日期字符串 YYYY-MM-DD，默认北京时间今天
        wiki_pages:   关联维基页 URL/ID 列表（可选）
        source_pages: 相关源 URL/ID 列表（可选）
        notion_token: 显式传入 token，默认读 NOTION_TOKEN 环境变量
    """
    token = notion_token or os.environ.get("NOTION_TOKEN", "")
    if not token:
        raise RuntimeError("NOTION_TOKEN 未设置")

    notion = Client(auth=token)
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

    notion.pages.create(parent={"database_id": LOG_DB_ID}, properties=props)
    print(f"✅ 日志已写入：{entry}  |  {detail[:60]}{'…' if len(detail)>60 else ''}")


def main() -> None:
    parser = argparse.ArgumentParser(description="往 Notion 日志库写一条操作记录")
    parser.add_argument("--op", required=True, choices=VALID_OPS,
                        help="操作类型")
    parser.add_argument("--title", required=True,
                        help="操作摘要（脚本自动加 [操作] 前缀）")
    parser.add_argument("--detail", required=True,
                        help="一句话说明：做了什么，结果是什么")
    parser.add_argument("--date",
                        help="日期 YYYY-MM-DD，默认北京时间今天")
    parser.add_argument("--wiki",
                        help="关联维基页 URL 或 ID，逗号分隔（可选）")
    parser.add_argument("--source",
                        help="相关源 URL 或 ID，逗号分隔（可选）")
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
