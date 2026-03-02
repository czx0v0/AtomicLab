# Atomic Lab 原子科研：基于原子化知识解构的科研协作工作站

## 1 项目简介

Atomic Lab 是一款专注于"读写闭环"的原子化科研工作站。针对科研人员在阅读 PDF 时灵感零散、文献整合困难的痛点，我们构建了一个沉浸式环境。系统通过原子化协议，将用户阅读过程中的零散感悟（碎片）转化为逻辑节点（原子），并以知识图谱的形式可视化呈现，最终在写作阶段提供结构化检索与参考。

**核心理念**：消除"认知内化断层"——在 PDF 存储与碎片化灵感之间建立有效的逻辑衔接。

## 2 业务价值说明

- **沉浸式阅读**：整合 PDF 文本提取与实时笔记，解决应用频繁切换导致的注意力损耗。
- **智能解构**：笔记即素材。通过 Crusher Agent 一键将阅读笔记转化为结构化的原子知识卡片。
- **知识图谱**：基于 ECharts 力导向图可视化知识节点与关联关系，支持搜索高亮。
- **参考写作**：在写作区自由撰写，左侧知识树与搜索栏提供结构化参考，支持 Markdown 导出。

## 3 AI 创新性说明

- **Atomic-RAG 驱动的知识解构**：系统将每一条原子知识拆分为 Axiom（公理）+ Methodology（方法）+ Boundary（边界）三层结构，实现学术语义的精准捕捉。
- **Multi-Agent 架构**：统一 BaseAgent 协议，支持 Crusher（解构）、Annotator（批注）、Synthesizer（合成）等多种 Agent 协同工作。
- **知识图谱可视化**：解构结果自动构建为 Domain → Atom 层级图谱，支持力导向布局和搜索高亮。
- **三段式工作流**：界面通过 Tab 切换引导用户完成 Read → Organize → Write 全过程。

## 4 技术实现说明

- **核心模型**：调用 **ModelScope DeepSeek-V3.2** 支撑高阶逻辑推理。
- **知识树**：`KnowledgeTree` 数据结构，节点类型（domain/atom/note/concept）+ 边关系（derives_from/contradicts/extends/references）。
- **图谱可视化**：ECharts 力导向图，支持节点点击交互和搜索高亮。
- **状态管理**：采用 `gr.State` 维护文献库、笔记列表、知识树和统计数据。
- **模块化架构**：核心逻辑拆分为 `core`、`agents`、`knowledge`、`ui`、`tabs` 五个子模块。

### 4.1 Agent 协议

| Agent       | 代号       | 输入                  | 输出                                          |
| ----------- | ---------- | --------------------- | --------------------------------------------- |
| Crusher     | 解构引擎   | 阅读笔记 + 文献上下文 | 3 atoms: [Axiom] + [Methodology] + [Boundary] |
| Annotator   | 批注引擎   | 目标节点 + 同域节点   | 批注 + 新关联边 (TODO)                        |
| Synthesizer | 树合成引擎 | 所有原子              | 层级父子关系 (TODO)                           |

### 4.2 全局状态

| State          | 内容                                                               |
| -------------- | ------------------------------------------------------------------ |
| `library_store`| `{pid: {name, text, atoms[], filepath}}` — 文献 metadata + 原子   |
| `notes`        | `[{id, type, content, page, ts, source_pid}]` — 阅读笔记          |
| `tree`         | `KnowledgeTree {nodes, edges, metadata}` — 知识图谱               |
| `stats`        | `{docs, atoms, notes, nodes}` — 实时计数                          |

### 4.3 项目结构

```
atomic-lab/
├── app.py                 # 入口：组装 UI + 事件绑定
├── core/
│   ├── config.py          # API、模型、常量配置
│   ├── utils.py           # 工具函数（PDF提取、JSON解析等）
│   └── state.py           # ID生成器、初始状态工厂
├── agents/
│   ├── base.py            # BaseAgent 协议（统一接口）
│   └── crusher.py         # Crusher 解构引擎
├── knowledge/
│   ├── tree_model.py      # KnowledgeTree/Node/Edge 数据模型
│   └── search.py          # 知识搜索（精确匹配 + 标签过滤）
├── ui/
│   ├── styles.py          # CSS 样式
│   ├── renderers.py       # HTML 渲染函数
│   └── echarts_graph.py   # ECharts 图谱生成器
├── tabs/                  # 各 Tab 的 UI 构建（备用模块化方案）
├── docs/                  # 架构文档
└── requirements.txt
```

## 5 交互与设计说明 (UX Design)

- **极简三步走**：**Read**（阅读文献）→ **Organize**（知识图谱）→ **Write**（参考写作）
- **原子卡片**：每张原子卡片含 Domain 标签、Axiom、Methodology、Boundary 四层信息。
- **知识图谱**：力导向布局，Domain 蓝色大节点 → Atom 绿色中节点，支持拖拽和缩放。

### 5.1 Tab 布局

| Tab                   | 左栏                | 右栏              |
| --------------------- | ------------------- | ----------------- |
| **📖 阅读**     | 文献上传+文本阅读   | 笔记输入+列表     |
| **🌳 知识图谱** | 搜索+ECharts图谱    | 节点详情+笔记+解构|
| **✍️ 写作**   | 搜索+知识树+参考卡片| 写作区+下载       |

### 5.2 工作流逻辑

1. **Read（阅读）**：上传 PDF，左侧文本提取阅读 + 右侧笔记输入。
2. **Organize（知识图谱）**：搜索知识节点，通过 Crusher Agent 解构笔记为原子卡片，自动构建知识图谱。
3. **Write（写作）**：搜索知识库，参考原子卡片，自由写作，支持 Markdown 下载。

---

## 快速启动

```bash
pip install -r requirements.txt
python app.py
```

浏览器访问 `http://127.0.0.1:7860`

## 技术栈

- **Runtime**: Python 3.10 + Gradio 4.x
- **LLM**: DeepSeek-V3.2 (ModelScope Inference API)
- **PDF**: PyPDF2 文本提取
- **可视化**: ECharts 5.x 力导向图
