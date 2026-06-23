#!/usr/bin/env python3
"""
Wiki Search — 在 Notion 维基库中关键词搜索（客户端全文匹配）。

用法：
  python search.py <关键词> [关键词2 ...]      # 搜所有库（词取交集）
  python search.py --wiki x <词>               # 只搜 x scheme
  python search.py --wiki xiaomi <词>          # 只搜 小咪
  python search.py --wiki invest <词>          # 只搜 投资
  python search.py --type 概念 <词>            # 按页面类型过滤

示例：
  python search.py 量化 选股
  python search.py --wiki x Building in Public
  python search.py --type 总览 AI
"""

import os
import sys
import requests

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

WIKIS = {
    "x": {"name": "x scheme", "db": "3cb8335c510183e5839681992705faaa"},
    "xiaomi": {"name": "小咪", "db": "e1b8335c5101836bb60f81286f082229"},
    "invest": {"name": "投资", "db": "1aaf457a389f439880a18255de0089d9"},
}


def query_all_pages(db_id):
    results = []
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        r = requests.post(
            f"https://api.notion.com/v1/databases/{db_id}/query",
            headers=HEADERS,
            json=body,
        )
        if r.status_code != 200:
            print(f"  API错误 {r.status_code}: {r.text[:120]}", file=sys.stderr)
            break
        data = r.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return results


def extract_text(prop, prop_type="rich_text"):
    if prop_type == "title":
        parts = prop.get("title", [])
    else:
        parts = prop.get("rich_text", [])
    return "".join(p.get("plain_text", "") for p in parts)


def extract_select(prop):
    sel = prop.get("select")
    return sel["name"] if sel else ""


def search_wiki(wiki_key, terms, type_filter=None):
    info = WIKIS[wiki_key]
    pages = query_all_pages(info["db"])
    matches = []
    for page in pages:
        props = page.get("properties", {})
        title = extract_text(props.get("标题", {}), "title")
        summary = extract_text(props.get("一句话摘要", {}), "rich_text")
        page_type = extract_select(props.get("页面类型", {}))
        goal = extract_select(props.get("目标对齐", {}))
        status = extract_select(props.get("状态", {}))
        url = page.get("url", "")

        if not title:
            continue
        if type_filter and page_type != type_filter:
            continue

        search_text = (title + " " + summary).lower()
        if all(t.lower() in search_text for t in terms):
            matches.append({
                "wiki": info["name"],
                "title": title,
                "type": page_type,
                "goal": goal,
                "status": status,
                "summary": summary[:100],
                "url": url,
            })
    return matches


def main():
    if not NOTION_TOKEN:
        print("错误：NOTION_TOKEN 未设置", file=sys.stderr)
        sys.exit(1)

    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    wiki_filter = None
    type_filter = None
    terms = []

    i = 0
    while i < len(args):
        if args[i] == "--wiki" and i + 1 < len(args):
            wiki_filter = args[i + 1]
            i += 2
        elif args[i] == "--type" and i + 1 < len(args):
            type_filter = args[i + 1]
            i += 2
        else:
            terms.append(args[i])
            i += 1

    if not terms:
        print("错误：请提供搜索关键词")
        sys.exit(1)

    wikis_to_search = (
        {wiki_filter: WIKIS[wiki_filter]}
        if wiki_filter and wiki_filter in WIKIS
        else WIKIS
    )

    all_results = []
    for key in wikis_to_search:
        all_results.extend(search_wiki(key, terms, type_filter))

    if not all_results:
        print(f'未找到包含「{"·".join(terms)}」的页面')
        return

    print(f'\n共找到 {len(all_results)} 个匹配页面（关键词：{"·".join(terms)}）：\n')
    for r in all_results:
        status_badge = f" [{r['status']}]" if r["status"] else ""
        type_badge = f"《{r['type']}》" if r["type"] else ""
        goal_badge = f" [{r['goal']}]" if r["goal"] else ""
        print(f"[{r['wiki']}]{status_badge} {r['title']} {type_badge}{goal_badge}")
        if r["summary"]:
            print(f"  {r['summary']}")
        print(f"  {r['url']}\n")


if __name__ == "__main__":
    main()
