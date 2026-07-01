# 会话交接摘要 (Handoff)

> 给新会话快速接手用。最后更新：2026-06-30

## 环境 / 仓库
- 仓库：`josianokwaw-netizen/111`，工作分支：**`claude/wiki-lm-xiaohongshu-guide-jmhv5s`**（所有改动提交推送到此分支，勿动 main）
- 项目本体是一个 **Notion Wiki 知识管理系统**（源库/维基库/日志库 + CLAUDE.md 约定）。规则：每次操作后必须往 Notion 日志库(`36a8335c5101826296aa816dd77513f6`)写一条记录。
- 用户：小红书/抖音内容创作者，用 Claude + Notion，账号定位 AI 工具/知识管理，社媒 id **tenis**。

## 已装好的工具 / 脚手架
- **cheat-on-content** skill（内容打分+盲预测+复盘校准系统）已 `/cheat-init` 初始化：
  - `.cheat-state.json`（content_form=`tutorial-builder`, rubric v0, calibration_samples=0, baseline_plays=1022）
  - `rubric_notes.md`(tutorial-builder-zero 7维等权), `predictions/`, `scripts/`, `videos/`, `samples/`
  - 预测锁 hook（`.cheat-hooks/prediction-immutability.sh`）+ SessionStart 报告 hook 已装进 `.claude/settings.json`，已验证生效
- 渲染截图能力：无文生图工具；用 **headless Chromium**(`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`)对 HTML 截 PNG。Playwright node 模块没装。
- MCP：Notion / GitHub / Figma / Vercel 可用（偶发闪断重连）。Codex 的 taste/guizang/Frontend-App-Builder skill **未安装、不可调**。

---

## 任务 A：Wiki LM 小红书图文（已完成并发布）
- 主题：Karpathy 的 LLM Wiki 模式 + 用 Claude+Notion 落地。基于用户上传的 `llm-wiki.md` + Notion 摘录页。
- 成品稿：**`scripts/2026-06-30_wikilm01_wikilm.md`**（标题4备选 / 正文 / 三层结构 / 3个操作 / **3段可复用 prompt** / 标签）。已过 humanizer-zh 去 AI 味，语气中性、工具通用化。
- 封面：**`assets/cover.html`** → **`assets/cover.png`**（小红书 3:4，1080×1440，暗橘"别再让收藏吃灰"）。
- 预测：**`predictions/2026-06-30_eb64df6c0def_养知识库.md`**，7维 composite≈8.57，cold-start 无 bucket。
  - ⚠️ 诚实性：预测在看数据前已拟好，但落盘前用户出示了真实数据 → header 标注"不计入纯盲样本"。
- **已发布**实绩(T+0)：**1022 浏览 / 51 赞 / 12 收藏 / +2 粉**。判断：互动率健康(赞5%)，瓶颈是新号触达低不是内容；可疑点=赞>藏，"附prompt"收藏诱因没在首屏强化够。
- 待办：**正式复盘定在 2026-07-03(T+3d)**，需用户补 **top 20 评论(带赞数)**。state 里已挂 pending_retro。

---

## 任务 B：TENIS 个人网站（进行中 — 当前焦点）
用户下一篇选题=「用 AI 造个人网站」，要先真做出自己的站。

### 已确定的设计决策
- **IP 定位**：**个人网站**（"我用 AI 造个人网站，也教你造"）。
- **参考基调**：王十三/Ethan Wang Studio 那种——暗色电影感 + 奶油白粗体大字 + 等宽科技小字 + 中英双语 + 章节编号 + 挂绳工牌。**"参考但不做成一样"**：我们改用石墨黑冷调。
- **核心交互原理**（用户确认）：参考站的"人物"其实是 **视频逐帧 + GSAP ScrollTrigger scrub**；开场工牌是 **Three.js**（用户提供了 React Bits 的 **Lanyard** 组件源码：@react-three/fiber + drei + rapier + meshline，需 card.glb + lanyard.png）。
- **素材**：先纯代码出，图片槽位留好，用户之后供 AI 图(midjourney/nano banana)再替换。
- **导航/页面**：about（社媒号列表）/ build（个人网站&应用）/ write（日常分享，如小红书）/ video（暂无→coming soon）/ **contact me**。用户设想：相机绕工牌/人物转，点一页转到一个朝向，点完出现 contact。
- **头像**：暂用用户发的 Itachi 动漫图(`assets/site/avatar.png`)，待确认是否正式。
- **动效技术栈**：React+Vite / R3F+drei+rapier / GSAP+ScrollTrigger / Lenis 平滑滚动。

### 已产出
- **`assets/site/hero.html`** → **`assets/site/hero.png`**：Hero v1.1 静态渲染稿。含暗色网格背景、挂绳工牌(头像+条码+DRAG ME)、顶部导航、左侧章节轨、大字标题「我用 AI 造个人网站，也教你造」、右下 `FRAME 000/240 · GSAP SCRUB` 提示。
- 交付形态：用户在手机端，要"能跑的真页面预览截图(不用太细) + 一版 Figma 稿"，v1 范围=**先打样 Hero+工牌**。

### 待用户拍板（卡在这里）
1. **Figma 稿**：A=现在生成到用户 Figma / B=先不进 Figma、拿截图迭代。（创建 Figma 文件是写入用户账号的动作，需确认）
2. **下一步**：①磨 Hero 视觉 / ②上真 R3F 工牌物理效果 / ③铺 about 页。
3. 小问题：中文标题现断成3行("站，"孤行)，是否收字号排成2行。
4. 需用户提供：**社媒账号清单(平台+链接)** 给 about 页；确认头像是否正式。

---

## 关键约定提醒
- 提交信息结尾加 Co-Authored-By 与 Claude-Session 尾注；只推到指定分支。
- 每次实质操作后写 Notion 日志（op: 摄入/查询/复检/维护/合并/删除）。
- 不创建 PR 除非用户明确要求。
