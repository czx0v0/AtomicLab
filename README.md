# Atomic Lab v2.0：基于原子化知识解构的科研协作工作站

## 1. 项目简介 (Introduction & Problem Statement)

Atomic Lab v2.0 是一款专注于**"读写闭环"**的原子化科研工作站。针对科研人员在阅读 PDF 时灵感零散、文献整合困难的痛点，我们构建了一个沉浸式环境。系统通过原子化协议，将用户阅读过程中的零散感悟（碎片）转化为逻辑节点（原子），并在写作阶段提供结构化参考。

**核心理念**：消除"认知内化断层"——在 PDF 存储与碎片化灵感之间建立有效的逻辑衔接。

## 2. 业务价值说明 (Business & Research Value)

- **沉浸式阅读**：整合 PDF 阅读、文本提取与实时笔记，解决应用频繁切换导致的注意力损耗。
- **智能解构**：笔记即素材。通过 Crusher Agent 一键将阅读笔记转化为结构化的原子知识卡片。
- **参考写作**：在写作区自由撰写，左侧原子卡片作为结构化参考，支持 Markdown 导出。

## 3. AI 创新性说明 (AI Core Innovation)

- **Atomic-RAG 驱动的知识解构**：系统将每一条原子知识拆分为 Axiom（公理）+ Methodology（方法）+ Boundary（边界）三层结构，实现学术语义的精准捕捉。
- **Crusher Agent**：负责语义解构与学术公理化提取，基于 Qwen2.5-72B-Instruct 大模型进行高阶逻辑推理。
- **三段式工作流**：界面通过 Tab 切换引导用户完成 Read → Organize → Write 全过程。

## 4. 技术实现说明 (Methodology & Implementation)

- **核心模型**：调用 **ModelScope Qwen2.5-72B-Instruct** 支撑高阶逻辑推理。
- **状态管理**：采用 `gr.State` 维护文献库、笔记列表、原子卡片和统计数据。
- **PDF 阅读**：使用 `gradio_pdf` 组件渲染 PDF，配合 PyPDF2 逐页提取文本显示。

### 工作流逻辑

1. **Read（阅读）**：上传 PDF，左侧 PDF 阅读器 + 中间文本提取 + 右侧笔记输入。
2. **Organize（整理）**：汇总阅读笔记，通过 Crusher Agent 解构为原子知识卡片。
3. **Write（写作）**：左侧参考原子卡片，右侧自由写作区，支持 Markdown 下载。

## 5. 交互与设计说明 (UX Design)

- **极简三步走**：**Read**（阅读文献）→ **Organize**（解构笔记）→ **Write**（参考写作）
- **Scrivener 风格卡片**：每张原子卡片含 Domain 标签、Axiom、Methodology、Boundary 四层信息。
- **学术工具风格**：暖白配色 + 系统字体 + Georgia 衬线阅读字体，贴近 Zotero/Overleaf 的专业感。

---

## 技术架构

```
 ┌──────────┐
 │ Crusher  │
 │ Agent    │
 │ 语义解构  │
 └────┬─────┘
      │
      v
 ┌─────────────────────────────────────────┐
 │         Global State (gr.State)         │
 │ library_store | notes | atoms | stats   │
 └─────────────────────────────────────────┘
      │               │               │
 ┌─────────────────────────────────────────┐
 │          Tab-based Interface            │
 │  📖 阅读    │  🧬 整理    │  ✍️ 写作    │
 │ (PDF+Text) │ (Atom Cards)│ (Editor)    │
 └─────────────────────────────────────────┘
```

## Agent 协议

| Agent      | 代号     | 输入            | 输出                                          |
| ---------- | -------- | --------------- | --------------------------------------------- |
| Crusher    | 解构引擎 | 阅读笔记 + 文献上下文 | 3 atoms: [Axiom] + [Methodology] + [Boundary] |

## Tab 布局

| Tab              | 左栏             | 中栏           | 右栏           |
| ---------------- | ---------------- | -------------- | -------------- |
| **📖 阅读**      | PDF 阅读器       | 文献文本提取    | 笔记输入+列表  |
| **🧬 整理**      | 笔记概览+解构    | 原子卡片+统计   |                |
| **✍️ 写作**      | 参考原子卡片      | 写作区+下载     |                |

## 全局状态

| State           | 内容                                                              |
| --------------- | ----------------------------------------------------------------- |
| `library_store` | `{pid: {name, text, atoms[], filepath}}` — 文献 metadata + 原子  |
| `notes`         | `[{id, type, content, page, ts, source_pid}]` — 阅读笔记        |
| `stats`         | `{docs, atoms, notes}` — 实时计数                                |

## 快速启动

```bash
pip install -r requirements.txt
python app.py
```

浏览器访问 `http://127.0.0.1:7860`

## 技术栈

- **Runtime**: Python 3.10 + Gradio 6.x
- **LLM**: Qwen2.5-72B-Instruct (ModelScope Inference API)
- **PDF**: gradio_pdf 组件 + PyPDF2 文本提取
- **CSS**: 暖白主题 (#fafaf8)，系统字体 + Georgia 衬线
