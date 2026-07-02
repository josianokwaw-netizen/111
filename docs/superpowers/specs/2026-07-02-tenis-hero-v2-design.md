# TENIS 个人网站 · Hero v2 设计规格

> 2026-07-02，经 brainstorming 需求对齐后定稿。产出：`site/index.html`（单文件初稿，可直接静态部署预览）。

## 已拍板的决策（用户确认）

| 决策点 | 结论 |
|--------|------|
| 背景处理 | 图1（十二使徒海岸线航拍）压暗冷调 duotone：`grayscale + brightness(.52) + contrast(1.15)` + 钢青 multiply 叠色 + 浪沫青 radial 提色 + vignette |
| 初稿形态 | 单文件 HTML（GSAP CDN + CSS 3D 工牌）先定视觉；确认后再迁 React+Vite+R3F 真物理工牌 |
| 标题排版 | 收字号排 2 行：「我用 AI 造个人网站，/ 也教你造。」 |
| Figma 稿 | 暂不生成，拿真页面预览迭代 |

## 设计 Token

**色板（石墨黑冷调，accent 取自海岸浪沫）**

| 名称 | 值 | 用途 |
|------|-----|------|
| 石墨黑 ink | `#0E1116` | 页面基底 |
| 钢青黑 steel | `#18202A` | 叠色/面板 |
| 冷白 cold | `#E9EDF1` | 主文字（替代参考站的奶油白） |
| 雾灰蓝 fog | `#8B98A8` | 次级文字 |
| 浪沫青 foam | `#79B8AD` | 唯一 accent：标题重点字、LIVE 点、章节轨点 |

**字体**：Anton（英文 display / ghost 字 / 工牌名）+ Noto Sans SC 700/900（中文标题正文）+ IBM Plex Mono（等宽科技小字：kick、rail、状态行、工牌元数据）。

**Signature 元素**：挂绳工牌（React Bits Lanyard 的静态先行版）——鼬头像 + TENIS + 条码 + DRAG ME，纯 JS 单摆物理（待机轻摆、可拖拽、松手弹簧回正）。这是页面唯一"花哨"的地方，其余克制。

## 布局

- 顶部导航：忒尼斯 / TENIS · STUDIO + 01-04 编号菜单（about/build/write/video）+ CONTACT 实心按钮
- 左侧章节轨（mono 小字，当前章高亮），右侧三行英文定位语（AI builder. / Site maker. / A studio of one.）
- 标题区压底：mono kick 行 → 2 行大标题 → 英文 mono 副标
- 工牌从视口顶垂下（桌面偏右，≤720px 居中）
- 底部：左 SCROLL 状态行 + 右 FRAME 000/240 计数（GSAP scrub 驱动，为后续视频逐帧版本埋点）
- 第二屏：01-04 章节预告卡（scroll 浮现），footer 含 contact 占位

## 动效

- 工牌：rAF 单摆（k=0.012, damp=0.985）+ pointer 拖拽角速度继承
- GSAP ScrollTrigger：FRAME 计数 0→240 随全页滚动 scrub；章节卡浮现
- `prefers-reduced-motion` 全部降级

## 迁移路线（下一步）

1. 视觉定稿后迁 React+Vite：R3F+drei+rapier 真 Lanyard（需 card.glb + lanyard.png 贴图，把鼬头像烘进卡面贴图）
2. GSAP scrub 接真视频逐帧序列；Lenis 平滑滚动
3. about 页补社媒账号清单（待用户提供）

## 待用户提供

- 社媒账号清单（平台 + 链接）→ about 页 / footer contact
- 确认鼬头像是否作为正式头像
