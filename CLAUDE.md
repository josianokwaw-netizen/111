# Wiki 知识管理系统 · Claude 行为规范

配套 Notion 三库知识系统（源库 · 维基库 · 日志库）。
Scheme 约定：https://app.notion.com/p/9db8335c510182f0bb2d01918f8b6f13

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

---

## Lint 自动运行

GitHub Actions 每周一 09:00 北京时间自动执行 `wiki_lint/lint.py`，
完成后自动写日志，有问题时发 GitHub Issue 通知。
无需手动触发，但可在 Actions 页面点 Run workflow 立即跑一次。

---

## 快捷指令（对话中直接说）

- `摄入这个` → Ingest 流程 → 操作完写日志
- `关于 X，Wiki 里怎么说？` → Query 流程 → 好答案考虑回填 → 写日志
- `给 Wiki 做次体检` → Lint 流程 → 写日志
- `这个 Scheme 要改一下` → Schema 更新 → 写日志
