# Wiki 知识管理系统 · Claude 行为规范

配套 Notion 三库知识系统（源库 · 维基库 · 日志库）。
Scheme 约定（小咪约定层）：https://app.notion.com/p/3808335c510181ab91bce0d212f58457

---

## 强制：每次操作后写日志

完成以下任意操作后，**必须立即**往 Notion 日志库写一条记录，不得省略：

| 操作 | --op 值 |
|------|----------|
| 摄入新源，生成摘要/更新维基页 | `摄入` |
| 用户提问，回答并考虑回填问答页 | `查询` |
| 运行 Lint 复检 | `复检` |
| Scheme 本页有改动 | `Schema更新` |
| 合并维基页 | `合并` |
| 删除维基页 | `删除` |

### 写日志：优先用 Notion MCP

```
工具：notion-create-pages
parent database_id：36a8335c5101826296aa816dd77513f6

属性：
  条目  (title)  : "[操作类型] 操作摘要"   示例："[摄入] Reddit方法论帖子"
  操作  (select) : 摄入 / 查询 / 复检 / 维护 / Schema更新 / 合并 / 删除
  日期  (date)   : 今天  YYYY-MM-DD
  详情  (text)   : 一句话：做了什么，结果是什么
  关联维基页 (relation) : 新建或更新的维基页 URL（可为空）
  相关源     (relation) : 触发本次操作的源页 URL（可为空）
```

### 写日志：备选 CLI（本地 / GitHub Actions）

```bash
cd wiki_lint
python write_log.py \
  --op  摄入 \
  --title "Reddit方法论帖子" \
  --detail "摄入 Reddit 方法论，新建摘要页，更新内容营销总览" \
  [--wiki  "notion-page-url,..."] \
  [--source "notion-source-url,..."]
```

---

## 数据库 ID（常用）

| 库 | database_id |
|----|-------------|
| 源库 | `d748335c510182ea885201b572eddef4` |
| 维基库 | `3cb8335c510183e5839681992705faaa` |
| 日志库 | `36a8335c5101826296aa816dd77513f6` |
| Skill 目录库 | `c27f84a719c847b4a99900127e11dcf1`（data_source `8f80fe9c-a613-4c48-b3f2-6281a3dfe85a`） |

---

## Skill 登记与路由（Skill Catalog）

我帮你「记忆」skill：每上传一个 skill 就分类、安装、登记到 Notion「🧩 Skill 目录」库，
并按 README/SKILL.md 把它路由到对应角色/任务。

### 上传一个 skill 时，自动执行：

1. **取内容** — 优先 codeload 整包下载（`https://codeload.github.com/<owner>/<repo>/tar.gz/refs/heads/<branch>`），
   raw 单文件读取也可用；`github.com` git clone 受出口策略限制会 403，别走那条路。
2. **判定是否真 skill** — 看是否有带 `name`/`description` frontmatter 的 `SKILL.md`：
   - 有 → 真 skill，整包复制进 `.claude/commands/<repo-name>/`，状态 `已安装`。
   - 仅运行时工具（如需 pip 安装 CLI、SKILL.md 藏在子目录）→ 状态 `仅登记`，不拖入 commands。
   - 无 SKILL.md 的独立应用（如 Horizon）→ 状态 `应用·非Skill`，只登记不安装。
3. **分类 + 角色路由** — 按 README 归入分类（内容转换 / 设计·视觉 / Agent能力·工具 / 研究·分析 /
   写作·编辑 / 工程·开发 / 元技能·SkillOps / 应用·非Skill）并填「适配角色」。
4. **登记 Notion** — 往 Skill 目录库新增一行（名称 / 分类 / 状态 / 来源仓库 / 触发场景 /
   适配角色 / 安装路径 / README摘要 / 登记日期），用 `notion-create-pages`，
   parent `data_source_id: 8f80fe9c-a613-4c48-b3f2-6281a3dfe85a`。
5. **写日志** — 往日志库写一条 `--op 摄入`（详情写明登记/安装了哪个 skill）。

### 收到「全局 prompt / 我要做某事」时：

读 Skill 目录库的「触发场景」与「适配角色」，把匹配的 skill 主动挑出来用或建议给你，
而不是等你手动 `/skill-name`。

### 快捷指令

- `登记这个 skill <repo-url>` → 执行上面 5 步。
- `Skill 目录` / `我有哪些 skill` → 拉取 Skill 目录库列出来。

---

## Lint 自动运行

GitHub Actions 每周一 09:00 北京时间自动执行 `wiki_lint/lint.py`，
完成后自动写日志，有问题时发 GitHub Issue 通知。
无需手动触发，但可在 Actions 页面点 Run workflow 立即跑一次。

### Lint 检查项（完全按 scheme 约定）

**维基层（wiki_lint/lint.py）：**
1. 孤儿页 — 无「依据源」且无「相关页」→ **自动标记 `待复检`**
2. 过时页 — 信号分<2，或非「过时」状态但3个月未更新 → **自动标记 `过时`**
3. 缺一句话摘要 — scheme 必填字段为空
4. 未解决矛盾 — 页面标记含「⚠️有矛盾」
5. 待合并页 — 页面标记含「📥待合并」
6. 内容相似页 — 页面标记含「🔁内容相似」
7. 存疑页 — 页面标记含「❓存疑」
8. 高频缺页 — Gemini 分析，≥3次出现但无独立实体/概念页的术语

**源库层（wiki_lint/lint.py）：**
9. 长期待摄入 — 状态=待摄入 且 加入超过7天
10. 孤儿源 — 状态=已摄入 但无「相关维基页」关联

---

## 快捷指令（对话中直接说）

- `摄入这个` → Ingest 流程 → 操作完写日志
- `关于 X，Wiki 里怎么说？` → Query 流程 → 好答案考虑回填 → 写日志
- `给 Wiki 做次体检` → Lint 流程 → 写日志
- `这个 Scheme 要改一下` → Schema 更新 → 写日志

---

## Letta Memory（长期记忆层）

每次 Claude Code 会话启动时，自动从 Letta 云端读取记忆块，注入到当前上下文。

### 记忆块标签

| 标签 | 说明 |
|------|------|
| `human` | 用户画像与偏好（姓名、习惯、工作方式） |
| `persona` | Claude 在本系统中的角色与行为约束 |
| 自定义 | 可添加任意标签（如 `wiki_tips`、`project`） |

### 快捷指令

- `更新记忆 LABEL 新内容` → 执行 `python letta/letta_memory.py --write LABEL "新内容"`
- `查看记忆` → 执行 `python letta/letta_memory.py --read`
- `初始化 Letta` → 执行 `python letta/letta_memory.py --init`

### CLI 用法

```bash
# 读取所有记忆块
python letta/letta_memory.py --read

# 更新某个记忆块
python letta/letta_memory.py --write human "Name: 小咪，偏好中文，Wiki 维护者"

# 首次初始化（查看代理 ID）
python letta/letta_memory.py --init
```

> 代理名称：`claude-codex-memory`，可在 https://app.letta.com 查看与管理。

---

## 编码行为规范（Karpathy Guidelines）

> 来源：[multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills)  
> 基于 Andrej Karpathy 对 LLM 编码陷阱的观察整理，偏向谨慎而非速度，琐碎任务可酌情判断。

### 1. 先思考再编码

**不假设，不隐藏困惑，显式呈现权衡。**

实现前：
- 明确陈述你的假设；若不确定，先提问。
- 若存在多种解读，列出来，不要默默选一个。
- 若有更简单的方案，说出来，必要时推回需求。
- 若有不明确之处，停下来，说清楚哪里困惑，然后提问。

### 2. 简单优先

**最少代码解决问题，不做任何推测性扩展。**

- 不添加未被要求的功能。
- 单次使用的代码不做抽象。
- 不添加未被要求的「灵活性」或「可配置性」。
- 不处理不可能发生的场景的错误。
- 若写了 200 行但 50 行够用，重写它。

自问："资深工程师会觉得这过度复杂吗？" 若是，简化。

### 3. 外科手术式修改

**只改必须改的，只清理自己造的乱。**

修改已有代码时：
- 不「顺手优化」无关代码、注释或格式。
- 不重构未损坏的东西。
- 匹配已有风格，即使你会做得不同。
- 若发现无关死代码，提及它，不要删除它。

你的改动造成孤儿时：
- 删除**你的改动**导致未使用的 import / 变量 / 函数。
- 不要删除原本就存在的死代码，除非被要求。

检验标准：每一行改动都应能直接追溯到用户的请求。

### 4. 目标驱动执行

**定义成功标准，循环直到验证通过。**

将任务转化为可验证的目标：
- "加校验" → "为非法输入写测试，然后让测试通过"
- "修 bug" → "写能复现 bug 的测试，然后让它通过"
- "重构 X" → "确保重构前后测试均通过"

多步骤任务，先陈述简要计划：

```
1. [步骤] → 验证：[检查项]
2. [步骤] → 验证：[检查项]
3. [步骤] → 验证：[检查项]
```

强成功标准让你能独立循环推进；弱标准（"让它能跑"）需要持续追问。
