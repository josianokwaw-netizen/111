#!/usr/bin/env python3
"""
post_session_sync.py — Claude Code 会话结束后自动触发

功能：
1. 读取本次会话的 CLAUDE_TRANSCRIPT 摘要（由 hook 传入）
2. 用 Gemini / DeepSeek 提取值得记住的信息
3. 写入 Letta Memory
4. 更新本地缓存文件
5. git commit + push 备份到 GitHub

由 .claude/settings.json Stop hook 自动调用，无需手动运行。
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

# ── 路径 ─────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
CACHE_FILE = Path(__file__).parent / "memory_cache.md"

# ── 环境变量 ──────────────────────────────────────────
LETTA_API_KEY  = os.environ.get("LETTA_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
AGENT_NAME     = "claude-codex-memory"


# ── Letta 工具 ────────────────────────────────────────
def get_letta_client():
    try:
        from letta_client import Letta
        return Letta(api_key=LETTA_API_KEY)
    except ImportError:
        print("[sync] letta-client 未安装，跳过记忆更新", file=sys.stderr)
        return None


def find_agent(client):
    for agent in client.agents.list(name=AGENT_NAME):
        if agent.name == AGENT_NAME:
            return agent.id
    return None


def read_memory(client, agent_id) -> dict:
    blocks = list(client.agents.blocks.list(agent_id=agent_id))
    return {b.label: b.value for b in blocks}


def write_memory(client, agent_id, label: str, value: str):
    client.agents.blocks.update(
        block_label=label,
        agent_id=agent_id,
        value=value
    )


def refresh_cache(client, agent_id):
    memory = read_memory(client, agent_id)
    lines = ["<!-- Letta Memory Start -->", ""]
    for label, value in memory.items():
        lines.append(f"### [{label}]")
        lines.append(value.strip())
        lines.append("")
    lines.append("<!-- Letta Memory End -->")
    CACHE_FILE.write_text("\n".join(lines), encoding="utf-8")
    print("[sync] 缓存已刷新")


# ── LLM 提取记忆 ──────────────────────────────────────
def extract_with_gemini(transcript: str, current_human: str) -> dict | None:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = f"""
分析以下对话摘要，提取值得长期记住的用户信息（偏好、习惯、重要决策、项目进展）。
若本次对话无新信息，返回 {{"should_update": false}}。

当前已知用户信息:
{current_human}

本次对话摘要:
{transcript}

返回 JSON（不要 markdown 代码块）:
{{"should_update": true/false, "new_human_info": "更新后的完整用户信息（中文）"}}
"""
        result = model.generate_content(prompt)
        return json.loads(result.text.strip())
    except Exception as e:
        print(f"[sync] Gemini 提取失败: {e}", file=sys.stderr)
        return None


def extract_with_deepseek(transcript: str, current_human: str) -> dict | None:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

        prompt = f"""
分析以下对话摘要，提取值得长期记住的用户信息（偏好、习惯、重要决策、项目进展）。
若本次对话无新信息，返回 {{"should_update": false}}。

当前已知用户信息:
{current_human}

本次对话摘要:
{transcript}

只返回 JSON，不要其他文字:
{{"should_update": true/false, "new_human_info": "更新后的完整用户信息（中文）"}}
"""
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[sync] DeepSeek 提取失败: {e}", file=sys.stderr)
        return None


def extract_memory_update(transcript: str, current_human: str) -> dict | None:
    if GEMINI_API_KEY:
        result = extract_with_gemini(transcript, current_human)
        if result:
            return result
    if DEEPSEEK_API_KEY:
        return extract_with_deepseek(transcript, current_human)
    print("[sync] 未配置 GEMINI_API_KEY 或 DEEPSEEK_API_KEY，跳过智能提取")
    return None


# ── Git 推送 ──────────────────────────────────────────
def git_push_cache():
    try:
        subprocess.run(["git", "-C", str(ROOT), "add", "letta/memory_cache.md"], check=True)
        result = subprocess.run(
            ["git", "-C", str(ROOT), "diff", "--staged", "--quiet"],
            capture_output=True
        )
        if result.returncode == 0:
            print("[sync] 缓存无变化，跳过 commit")
            return
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(
            ["git", "-C", str(ROOT), "commit", "-m", f"chore: memory sync {date_str}"],
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
        print("[sync] ✅ 已推送到 GitHub")
    except subprocess.CalledProcessError as e:
        print(f"[sync] git 操作失败: {e}", file=sys.stderr)


# ── 主流程 ────────────────────────────────────────────
def main():
    # 从环境变量或 stdin 读取本次会话摘要
    transcript = os.environ.get("CLAUDE_TRANSCRIPT", "")
    if not transcript and not sys.stdin.isatty():
        transcript = sys.stdin.read().strip()

    if not transcript:
        transcript = f"会话时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    print(f"[sync] 会话结束，开始同步记忆...")

    # 连接 Letta
    client = get_letta_client()
    if not client or not LETTA_API_KEY:
        print("[sync] 跳过（无 LETTA_API_KEY）")
        return

    agent_id = find_agent(client)
    if not agent_id:
        print(f"[sync] 未找到 agent '{AGENT_NAME}'，跳过")
        return

    # 读取当前记忆
    memory = read_memory(client, agent_id)
    current_human = memory.get("human", "")

    # 用 LLM 提取新信息
    update = extract_memory_update(transcript, current_human)

    if update and update.get("should_update") and update.get("new_human_info"):
        new_info = update["new_human_info"]
        write_memory(client, agent_id, "human", new_info)
        print(f"[sync] ✅ 记忆已更新: {new_info[:80]}...")
    else:
        print("[sync] 本次无新记忆需要更新")

    # 刷新缓存文件
    refresh_cache(client, agent_id)

    # 推送到 GitHub
    git_push_cache()


if __name__ == "__main__":
    main()
