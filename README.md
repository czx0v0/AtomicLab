# Atomic Lab — 原子化科研工作站

> Read · Organize · Write · Chat

## 项目简介

Atomic Lab 是一款面向研究者的 AI 辅助科研工作站。围绕「阅读 → 整理 → 写作 → 对话」四阶段工作流，将文献阅读和笔记管理流程与大语言模型结合，自动完成笔记分类、关键词标注和知识图谱构建。

**核心理念**：每一条笔记都是知识原子，AI 为其赋予分类和标签，最终形成可检索、可视化的知识树。

## 功能亮点

- **沉浸式阅读**：PDF 文本提取 + 原始 PDF 双模式，选中文字自动弹出浮动工具栏（高亮 · 翻译 · 复制 · 问AI）
- **高亮笔记**：点击颜色按钮自动保存为笔记卡片，支持红/黄/绿/紫四色标记
- **一键翻译**：弹出菜单内中英互译，可保存翻译结果为笔记
- **AI 笔记分类**：Crusher Agent 自动分为「方法 / 公式 / 图像 / 定义 / 观点 / 数据 / 其他」七类
- **自动打标签**：每条笔记 1-3 个关键词标签 + 一句话 AI 批注
- **双图谱视图**：
  - 笔记知识图谱：文献 → 笔记 → 标签 树形结构（ECharts 力导向图）
  - 文献关系图：论文级关联（共享标签自动连边）
- **跨文献合成**：Synthesizer Agent 发现跨论文主题关联和宏观洞察
- **写作辅助**：Markdown 格式工具栏 + 侧栏知识树浏览 + AI 建议 + 导出
- **RAG 对话**：AI 助手基于文献和笔记回答问题，支持翻译、知识问答、跨文献分析
- **密码保护**：默认开启，通过环境变量 `ENABLE_AUTH` 和 `AUTH_PASSWORD` 控制

## AI 架构

### Multi-Agent 系统

采用 Router + 专家 Agent 架构，统一 `BaseAgent` 接口：

| Agent | 职责 | 说明 |
|-------|------|------|
| **Router** | 意图识别 + 分发 | 关键词检测 + LLM 分类，路由到对应专家 Agent |
| **Crusher** | 笔记分类引擎 | 七分类 + 标签 + 摘要 + 学科识别 |
| **Synthesizer** | 跨文献合成 | 主题发现 + 关联分析 + 重要性排序 + 洞察 |
| **Translator** | 翻译引擎 | 中英自动检测 + 互译 |
| **Conversation** | RAG 问答 | 检索知识树 → 提取片段 → LLM 生成带引用回答 |

### Atomic-RAG

以单条笔记为检索粒度，AI 在分类阶段介入（而非生成阶段），用户保留写作控制权。对话模式下采用 3 步 RAG 管线：搜索节点 → 提取上下文 → 生成回答。

### 知识树结构

四层层级：`domain → document → note → tag`，支持 `contains`、`tagged_with`、`references` 三种边关系。

## 技术栈

| 层 | 技术 |
|----|------|
| 前端框架 | Gradio 6.5+（Python 原生 Web UI） |
| 主题 | Gradio Soft 浅色主题 + 自定义 CSS |
| 大语言模型 | DeepSeek-V3.2 (ModelScope Inference API) |
| 可视化 | ECharts 5（MutationObserver 自动初始化） |
| PDF 解析 | PyPDF2（逐页文本提取） |
| PDF 渲染 | Base64 嵌入（≤20MB），超大文件提示文本模式 |
| JS 通信 | 隐藏 Textbox + data 属性 + 事件触发 |
| 部署 | ModelScope 创空间 |
| 语言 | Python 3.10+ |

## 项目结构

```
atomic-lab/
├── main.py              # 入口：组装 UI + 事件绑定 + 密码控制
├── core/
│   ├── config.py        # API、模型、节点类型、密码配置
│   ├── utils.py         # PDF 提取、JSON 解析、HTML 转义
│   └── state.py         # ID 生成器、状态工厂
├── agents/
│   ├── base.py          # BaseAgent 协议 + call_llm()
│   ├── crusher.py       # Crusher 笔记分类引擎
│   ├── synthesizer.py   # Synthesizer 跨文献合成引擎
│   ├── router.py        # Router 意图识别 + 分发
│   ├── translator.py    # Translator 中英互译
│   └── conversation.py  # Conversation RAG 问答
├── knowledge/
│   ├── tree_model.py    # KnowledgeTree / Node / Edge + 双图谱
│   └── search.py        # 搜索、过滤、层级路径查询
├── ui/
│   ├── styles.py        # CSS 样式（浅色主题）+ Header HTML
│   ├── global_js.py     # 全局 JS（ECharts 初始化 + 浮动弹出菜单 + 通信）
│   ├── renderers.py     # HTML 渲染（分类卡片、知识树、合成结果）
│   └── echarts_graph.py # ECharts 图谱生成
├── tabs/
│   ├── read/            # 阅读 Tab：上传 + 双模式阅读 + 高亮笔记 + 翻译
│   ├── organize/        # 知识图谱 Tab：Crusher + Synthesizer + 双图谱
│   ├── write/           # 写作 Tab：Markdown 工具栏 + 知识树 + 编辑器
│   └── chat/            # AI 助手 Tab：RAG 对话
└── requirements.txt
```

## Tab 布局

| Tab | 左栏 | 中栏 | 右栏 |
|-----|------|------|------|
| 阅读 | 文献列表 + 查看模式 | 文本/PDF双模式阅读 + 翻页 | 阅读笔记卡片 |
| 知识图谱 | 搜索 + 操作按钮 | 笔记图谱 + 文献关系图 | 节点详情 + 分析结果 |
| 写作 | 搜索 + 知识树浏览 | Markdown 编辑器 + 工具栏 | AI 建议 + 导出 |
| AI 助手 | — | 对话界面（RAG 问答） | — |

## 快速启动

```bash
pip install -r requirements.txt
python main.py
```

浏览器访问 `http://127.0.0.1:7860`

### 密码保护

默认开启密码认证（用户名 `admin`，密码通过环境变量 `AUTH_PASSWORD` 设置）。

```bash
# 自定义密码
export AUTH_PASSWORD=your_password

# 关闭密码保护
export ENABLE_AUTH=false
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MS_KEY` | (无) | ModelScope API Key |
| `ENABLE_AUTH` | `true` | 是否开启密码认证 |
| `AUTH_PASSWORD` | (无) | 登录密码（必须通过环境变量设置） |

## 技术要点

### JS ↔ Python 通信

Gradio 6.5.1 的 `gr.HTML()` 使用 innerHTML 赋值，会自动过滤 `<script>` 标签。解决方案：

1. 全局 JS 通过 `launch(js=...)` 注入，在页面加载时执行一次
2. ECharts 配置通过 `data-option` 属性传递，MutationObserver 监测 DOM 变化自动初始化
3. JS → Python 通过隐藏 Textbox 的 `change` 事件触发 Gradio 回调
4. Python → JS 通过更新 `gr.HTML()` 组件内容实现

### PDF 双模式

- **文本模式**：PyPDF2 逐页提取文本，渲染为可选中的段落（支持高亮弹出菜单）
- **PDF 模式**：Base64 编码嵌入 `<object>` 标签，20MB 以内直接渲染，超大文件提示切换文本模式
