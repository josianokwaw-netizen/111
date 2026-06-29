#!/usr/bin/env python3
"""把 digest.md 直接写入 Notion 源库（与 aihot-data-store 同一数据库）。

环境变量：
  NOTION_TOKEN        必填，Notion 集成 token
  NOTION_DATABASE_ID  目标数据库（默认沿用源库 ID）
  ISSUE_URL           issue 链接（写入「链接」属性，可空）
  ISSUE_TITLE         页面标题（可空，缺省取 digest 首个 # 标题）
  DIGEST_FILE         digest 路径，默认 digest.md

未配置 NOTION_TOKEN 或 digest 为空时安全跳过（退出码 0）。
"""
import os
import re
import sys

import requests

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID  = os.environ.get("NOTION_DATABASE_ID", "d748335c510182ea885201b572eddef4")
ISSUE_URL    = os.environ.get("ISSUE_URL", "").strip()
ISSUE_TITLE  = os.environ.get("ISSUE_TITLE", "").strip()
DIGEST_FILE  = os.environ.get("DIGEST_FILE", "digest.md")

if not NOTION_TOKEN:
    print("未配置 NOTION_TOKEN，跳过 Notion 推送。")
    sys.exit(0)

if not os.path.exists(DIGEST_FILE) or os.path.getsize(DIGEST_FILE) == 0:
    print("digest 为空，跳过 Notion 推送。")
    sys.exit(0)

with open(DIGEST_FILE, encoding="utf-8") as f:
    md = f.read()

if not ISSUE_TITLE:
    m = re.search(r"^#\s+(.+)$", md, re.M)
    ISSUE_TITLE = m.group(1).strip() if m else "🌅 AI 早报"

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def parse_inline(text):
    """行内 **bold** / [text](url) → Notion rich_text 数组。"""
    parts = []
    pattern = re.compile(r'(\*\*[^*]+?\*\*|\[.+?\]\(.+?\))')
    for seg in pattern.split(text):
        if not seg:
            continue
        bold_m = re.fullmatch(r'\*\*(.+?)\*\*', seg)
        link_m = re.fullmatch(r'\[(.+?)\]\((.+?)\)', seg)
        if bold_m:
            parts.append({'type': 'text',
                          'text': {'content': bold_m.group(1)[:2000]},
                          'annotations': {'bold': True}})
        elif link_m:
            parts.append({'type': 'text',
                          'text': {'content': link_m.group(1)[:2000],
                                   'link': {'url': link_m.group(2)}}})
        else:
            parts.append({'type': 'text', 'text': {'content': seg[:2000]}})
    return parts or [{'type': 'text', 'text': {'content': text[:2000]}}]


def md_to_blocks(md_text):
    blocks = []
    for line in (md_text or '').split('\n'):
        s = line.strip()
        if not s:
            continue
        if s.startswith('### '):
            blocks.append({'object': 'block', 'type': 'heading_3',
                           'heading_3': {'rich_text': parse_inline(s[4:])}})
        elif s.startswith('## '):
            blocks.append({'object': 'block', 'type': 'heading_2',
                           'heading_2': {'rich_text': parse_inline(s[3:])}})
        elif s.startswith('# '):
            blocks.append({'object': 'block', 'type': 'heading_1',
                           'heading_1': {'rich_text': parse_inline(s[2:])}})
        elif s.startswith('> '):
            blocks.append({'object': 'block', 'type': 'quote',
                           'quote': {'rich_text': parse_inline(s[2:])}})
        elif s == '---':
            blocks.append({'object': 'block', 'type': 'divider', 'divider': {}})
        else:
            blocks.append({'object': 'block', 'type': 'paragraph',
                           'paragraph': {'rich_text': parse_inline(s)}})
    return blocks


blocks = md_to_blocks(md)

page_data = {
    'parent': {'database_id': DATABASE_ID},
    'properties': {
        '标题':      {'title': [{'text': {'content': ISSUE_TITLE[:2000]}}]},
        '状态':      {'status': {'name': '待摄入'}},
        '类型':      {'select': {'name': '笔记'}},
        '主题':      {'multi_select': [{'name': 'AI投资'}, {'name': '宏观趋势'}]},
        '平台':      {'select': {'name': '其他'}},
        '作者/账号':  {'rich_text': [{'text': {'content': 'aihot / GitHub Actions'}}]},
    },
    'children': blocks[:100],
}
if ISSUE_URL:
    page_data['properties']['链接'] = {'url': ISSUE_URL}

r = requests.post('https://api.notion.com/v1/pages', headers=headers, json=page_data)
if r.status_code not in (200, 201):
    print(f"ERROR 创建 Notion 页面失败: {r.status_code} — {r.text[:400]}")
    sys.exit(1)

page_id = r.json()['id']

# 超过 100 个 block 分批追加
for start in range(100, len(blocks), 100):
    chunk = blocks[start:start + 100]
    r2 = requests.patch(
        f'https://api.notion.com/v1/blocks/{page_id}/children',
        headers=headers, json={'children': chunk})
    if r2.status_code not in (200, 201):
        print(f"WARN 追加 block @ {start}: {r2.status_code} — {r2.text[:200]}")

print(f"✓ 已推送到 Notion：{ISSUE_TITLE}（{len(blocks)} blocks）")
