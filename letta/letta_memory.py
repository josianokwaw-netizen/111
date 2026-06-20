#!/usr/bin/env python3
"""
letta_memory.py — 将 Letta 云端记忆块注入 Claude Code 会话。

用法：
  python letta/letta_memory.py --read              # 读取所有记忆块并打印
  python letta/letta_memory.py --write LABEL VALUE # 更新指定记忆块
  python letta/letta_memory.py --cache             # 从 Letta 拉取并写入本地缓存文件（本地/CI 运行）
  python letta/letta_memory.py --init              # 首次初始化代理（打印代理 ID）

SessionStart hook 读缓存文件而非直接调 API，避免远程环境网络限制。
同步流程：本地或 GitHub Action 运行 --cache → commit memory_cache.md → hook 读文件。
"""

import argparse
import os
import sys

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
AGENT_NAME  = "claude-codex-memory"                          # Letta 云端代理名称，保持唯一
API_KEY_ENV = "LETTA_API_KEY"                                # 从环境变量读取，避免硬编码敏感信息
CACHE_FILE  = os.path.join(os.path.dirname(__file__), "memory_cache.md")  # 本地缓存文件路径

# 首次创建代理时的默认记忆块（之后可通过 --write 随时更新）
DEFAULT_BLOCKS = [
    {
        "label": "human",            # 描述用户身份与上下文
        "value": (
            "用户：Wiki 知识管理系统维护者，使用 Notion 三库体系（源库 · 维基库 · 日志库）管理知识。\n"
            "偏好中文交流，关注内容质量与自动化流程。"
        ),
    },
    {
        "label": "persona",          # 描述 Claude 在此场景下的角色与行为约束
        "value": (
            "我是 Claude，协助用户维护 Notion Wiki 知识系统。\n"
            "每次操作后必须往日志库写记录，遵循 scheme 约定。\n"
            "支持摄入、查询、复检、合并、删除等标准流程。"
        ),
    },
]


# ---------------------------------------------------------------------------
# 客户端初始化
# ---------------------------------------------------------------------------
def _get_client():
    """从环境变量读取 API Key 并构建 Letta 客户端。"""
    api_key = os.environ.get(API_KEY_ENV, "")
    if not api_key:
        print(f"❌ 环境变量 {API_KEY_ENV} 未设置", file=sys.stderr)
        sys.exit(1)

    from letta_client import Letta          # 延迟导入，避免未安装时报错
    return Letta(api_key=api_key)           # 默认连接 Letta Cloud (https://api.letta.com)


# ---------------------------------------------------------------------------
# 代理查找 / 创建
# ---------------------------------------------------------------------------
def _find_or_create_agent(client) -> str:
    """返回名为 AGENT_NAME 的代理 ID；不存在则自动创建。"""
    # 按名称搜索已有代理（list 返回分页迭代器）
    for agent in client.agents.list(name=AGENT_NAME):
        if agent.name == AGENT_NAME:
            return agent.id

    # 未找到 → 新建，附带默认记忆块
    agent = client.agents.create(
        name=AGENT_NAME,
        model="openai/gpt-4o-mini",         # 低成本模型，仅用作记忆容器
        memory_blocks=DEFAULT_BLOCKS,
        include_base_tools=False,            # 不需要工具，只用记忆功能
    )
    print(f"✅ 已创建 Letta 代理：{AGENT_NAME}  id={agent.id}", file=sys.stderr)
    return agent.id


# ---------------------------------------------------------------------------
# 读取记忆
# ---------------------------------------------------------------------------
def cmd_read(client, agent_id: str) -> None:
    """读取所有记忆块并以 Markdown 格式输出到 stdout（供 hook 注入上下文）。"""
    blocks = list(client.agents.blocks.list(agent_id=agent_id))  # 获取所有块

    if not blocks:
        print("<!-- Letta Memory: 暂无记忆块 -->")
        return

    lines = ["<!-- Letta Memory Start -->", ""]
    for blk in blocks:
        lines.append(f"### [{blk.label}]")    # 块标签作为小标题
        lines.append(blk.value.strip())
        lines.append("")
    lines.append("<!-- Letta Memory End -->")
    print("\n".join(lines))


# ---------------------------------------------------------------------------
# 写入 / 更新记忆块
# ---------------------------------------------------------------------------
def cmd_write(client, agent_id: str, label: str, value: str) -> None:
    """更新指定标签的记忆块内容。"""
    client.agents.blocks.update(
        agent_id=agent_id,
        block_label=label,   # 按 label 定位记忆块
        value=value,
    )
    print(f"✅ 已更新记忆块 [{label}]：{value[:60]}{'…' if len(value) > 60 else ''}")


# ---------------------------------------------------------------------------
# 写入本地缓存文件（供 GitHub Action / 本地同步使用）
# ---------------------------------------------------------------------------
def cmd_cache(client, agent_id: str) -> None:
    """从 Letta 拉取记忆块并写入 memory_cache.md，之后 hook 直接读文件。"""
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):   # 捕获 cmd_read 的输出
        cmd_read(client, agent_id)
    content = buf.getvalue()

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ 记忆缓存已写入：{CACHE_FILE}")


# ---------------------------------------------------------------------------
# 初始化命令（打印代理信息）
# ---------------------------------------------------------------------------
def cmd_init(client, agent_id: str) -> None:
    """打印代理 ID 供确认，可在 app.letta.com 验证。"""
    print(f"✅ Letta 代理就绪")
    print(f"   名称：{AGENT_NAME}")
    print(f"   ID  ：{agent_id}")
    print(f"   管理：https://app.letta.com")


# ---------------------------------------------------------------------------
# 读取本地缓存（SessionStart hook 在远程环境中调用此函数）
# ---------------------------------------------------------------------------
def cmd_read_cache() -> None:
    """读取本地缓存文件并输出；文件不存在时静默退出。"""
    if not os.path.exists(CACHE_FILE):
        print("<!-- Letta Memory: 缓存文件不存在，请先运行 --cache 同步 -->")
        return
    with open(CACHE_FILE, encoding="utf-8") as f:
        print(f.read(), end="")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Letta 记忆块 ↔ Claude Code 集成工具")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--read",       action="store_true", help="从 Letta API 读取记忆块并输出")
    group.add_argument("--read-cache", action="store_true", help="读取本地缓存文件并输出（远程 hook 使用）")
    group.add_argument("--write",      nargs=2, metavar=("LABEL", "VALUE"), help="更新指定记忆块")
    group.add_argument("--cache",      action="store_true", help="从 Letta 拉取并写入本地缓存文件")
    group.add_argument("--init",       action="store_true", help="初始化/确认代理")
    args = parser.parse_args()

    # --read-cache 不需要 API 连接，直接读文件
    if args.read_cache:
        cmd_read_cache()
        return

    client   = _get_client()
    agent_id = _find_or_create_agent(client)

    if args.write:
        cmd_write(client, agent_id, args.write[0], args.write[1])
    elif args.cache:
        cmd_cache(client, agent_id)
    elif args.init:
        cmd_init(client, agent_id)
    else:
        cmd_read(client, agent_id)   # --read 或无参数均执行读取


if __name__ == "__main__":
    main()
