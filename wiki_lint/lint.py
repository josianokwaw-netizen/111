"""
Wiki Lint — 检查 GitHub Wiki Markdown 文件的常见问题。

检查项：
  1. 空文件
  2. 缺少一级标题（H1）
  3. 标题层级跳跃（如 H1 直接到 H3）
  4. 内部链接死链（引用的 .md 文件不存在）
  5. 外部链接可达性（HTTP 状态码非 2xx/3xx）

用法：
  python lint.py <wiki_dir>

退出码：
  0 — 无问题
  1 — 发现至少一个错误
"""

import os
import re
import sys
import time
import requests

TIMEOUT = 10
CHECKED_URLS: dict[str, int] = {}


def check_file(path: str, all_pages: set[str]) -> list[str]:
    errors = []
    with open(path, encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()
    filename = os.path.basename(path)

    # 1. 空文件
    if not content.strip():
        return [f"{filename}: 文件为空"]

    # 2. 缺少 H1
    headings = [(i + 1, line) for i, line in enumerate(lines) if re.match(r"^#{1,6}\s", line)]
    levels = [len(re.match(r"^(#+)", h[1]).group(1)) for h in headings]

    if not any(lv == 1 for lv in levels):
        errors.append(f"{filename}: 缺少一级标题（H1）")

    # 3. 标题层级跳跃
    for i in range(1, len(levels)):
        if levels[i] - levels[i - 1] > 1:
            errors.append(
                f"{filename}:{headings[i][0]}: 标题层级跳跃 H{levels[i-1]} → H{levels[i]}"
            )

    # 4. 内部链接死链
    internal = re.findall(r"\[.*?\]\((?!https?://)([^)#]+?)(?:#[^)]*)?\)", content)
    for link in internal:
        target = link.strip()
        if target.endswith(".md"):
            target_name = os.path.basename(target)
        else:
            target_name = target + ".md"
        if target_name not in all_pages:
            errors.append(f"{filename}: 内部链接失效 → {link}")

    # 5. 外部链接可达性
    external = re.findall(r"\[.*?\]\((https?://[^)]+)\)", content)
    for url in set(external):
        if url in CHECKED_URLS:
            status = CHECKED_URLS[url]
        else:
            try:
                resp = requests.head(url, timeout=TIMEOUT, allow_redirects=True)
                status = resp.status_code
            except Exception:
                status = 0
            CHECKED_URLS[url] = status
            time.sleep(0.1)
        if status == 0:
            errors.append(f"{filename}: 外部链接无法访问 → {url}")
        elif status >= 400:
            errors.append(f"{filename}: 外部链接返回 {status} → {url}")

    return errors


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python lint.py <wiki_dir>")
        sys.exit(1)

    wiki_dir = sys.argv[1]
    if not os.path.isdir(wiki_dir):
        print(f"目录不存在: {wiki_dir}")
        sys.exit(1)

    md_files = [f for f in os.listdir(wiki_dir) if f.endswith(".md")]
    all_pages = set(md_files)

    if not md_files:
        print("Wiki 目录中没有 Markdown 文件。")
        sys.exit(0)

    all_errors: list[str] = []
    for filename in sorted(md_files):
        filepath = os.path.join(wiki_dir, filename)
        errors = check_file(filepath, all_pages)
        all_errors.extend(errors)

    if all_errors:
        print(f"\n发现 {len(all_errors)} 个问题：\n")
        for err in all_errors:
            print(f"  ✗ {err}")
        sys.exit(1)
    else:
        print(f"检查完成，{len(md_files)} 个文件，无问题。")
        sys.exit(0)


if __name__ == "__main__":
    main()
