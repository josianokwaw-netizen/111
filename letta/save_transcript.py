#!/usr/bin/env python3
"""
save_transcript.py — Claude Code Stop Hook 调用

只做两件事：
1. 把本次会话摘要写入 letta/pending_transcript.txt
2. git commit + push → 触发 GitHub Actions 完成 Gemini 提取 + Letta 写入

不需要任何 API key，全部由 Actions 用 GitHub Secrets 完成。
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
TRANSCRIPT_FILE = Path(__file__).parent / "pending_transcript.txt"


def main():
    # 读取 transcript（从环境变量或 stdin）
    transcript = os.environ.get("CLAUDE_TRANSCRIPT", "")
    if not transcript and not sys.stdin.isatty():
        transcript = sys.stdin.read().strip()
    if not transcript:
        transcript = f"会话时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    # 写入文件前脱敏：移除常见 secret 模式
    import re
    transcript = re.sub(r'ntn_[A-Za-z0-9]{20,}', 'ntn_REDACTED', transcript)
    transcript = re.sub(r'sk-[A-Za-z0-9\-]{30,}', 'sk-REDACTED', transcript)
    TRANSCRIPT_FILE.write_text(transcript, encoding="utf-8")
    print(f"[sync] transcript 已保存 ({len(transcript)} 字)")

    # git commit + push
    try:
        subprocess.run(["git", "-C", str(ROOT), "add", "letta/pending_transcript.txt"], check=True)
        result = subprocess.run(
            ["git", "-C", str(ROOT), "diff", "--staged", "--quiet"],
            capture_output=True
        )
        if result.returncode == 0:
            print("[sync] 无变化，跳过推送")
            return
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(
            ["git", "-C", str(ROOT), "commit", "-m", f"chore(letta): session transcript {date_str}"],
            check=True
        )
        branch = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "--abbrev-ref", "HEAD"],
            text=True
        ).strip()
        subprocess.run(
            ["git", "-C", str(ROOT), "push", "-u", "origin", branch],
            check=True
        )
        print("[sync] ✅ 已推送，GitHub Actions 将自动提取记忆")
    except subprocess.CalledProcessError as e:
        print(f"[sync] git 失败: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
