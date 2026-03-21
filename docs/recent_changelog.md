### 2026-03-21 (atomiclab2-link-demo-organize-sync)

#### 🚀 新功能

**主界面跳转魔搭「原子科研2」**

- **ui/styles.py**：页头增加「打开原子科研2（AtomicLab2）」按钮式链接，新开标签页打开 [AtomicLab2 创空间](https://modelscope.cn/studios/czx0v0/AtomicLab2)；样式与现有蓝色主题一致（`.lab-hdr-actions` / `.lab-atomiclab-btn`）。

#### 🔧 修复 / 体验

**Demo 加载后整理页文档树与章节去重**

- **main.py**：`read["demo_btn"].click` 在刷新全局图谱的 `.then` 之后，再链式调用 `render_doc_note_tree` + 更新 `org_doc_selector`，使加载 Demo 后整理页左侧文档树立即选中对应文献、章节摘要可见；补充 `render_doc_note_tree` 导入。
- **tabs/read/__init__.py**：`_sync_tree_from_demo_sections` 中章节标题 `strip` 后空串归为「未命名章节」；若文档下已存在同名 section 则跳过重复创建，仅补写缺失的 `summary` / `key_points`。

#### 📝 代码变更

| 文件 | 变更描述 |
|------|----------|
| `ui/styles.py` | 页头 AtomicLab2 外链按钮与样式 |
| `main.py` | demo_btn 链式刷新 `doc_tree_html`、`org_doc_selector` |
| `tabs/read/__init__.py` | Demo 章节去重与元数据补全 |

---

### 2026-03-14 (page-number-conflict-and-demo-graph)

#### 🔧 修复

**ChunkMetadata page_number 参数冲突**

- **paragraph_chunker**：实例化 `ChunkMetadata` 时从 `kwargs` 展开字段排除 `page_number`（`k != "page_number"`），避免与显式传入的 `page_number=page_num` 重复，消除 `got multiple values for keyword argument 'page_number'`。
- **rag_service._recover_chunk_store_from_vector_store**：用变量 `page_num` 统一取用并传入，避免后续若改 `**metadata` 时再次冲突。

**Demo 加载后图谱即时刷新**

- **main.py**：`read["demo_btn"].click` 在更新 `agent_status` 的 `.then` 之后增加一层 `.then`，以 `tree_st` 为输入刷新 `org["global_graph_html"]` 与 `wrt["write_graph_html"]`，确保加载 Demo 后整理页 / 写作页 ECharts 图谱立即与五级层级一致。

#### 📝 文档

- **knowledge/tree_model.py**：模块注释明确五级层级（Domain → Document → Section → Note/Summary → Atomic）及 ECharts 节点含 source_pid/page、点击跳转 PDF。

#### 📝 代码变更

| 文件 | 变更描述 |
|------|----------|
| `services/chunking/paragraph_chunker.py` | ChunkMetadata 展开 kwargs 时排除 page_number |
| `services/rag_service.py` | _recover_chunk_store 用 page_num 变量构造 ChunkMetadata/TextChunk |
| `main.py` | demo_btn.click 链式 .then 刷新 global_graph_html、write_graph_html |
| `knowledge/tree_model.py` | 五级层级与 ECharts 跳转说明 |

---

### 2026-03-14 (seeker-ui-bridge-dataframe-page)

#### 🚀 新功能

**引用列表表格与点击跳转**

- **reference_list 正式推送**：Seeker 召回后构建 `reference_list`（格式：`[[引用, 来源, 页码, 摘要], ...]`，[1]/Vector 与 [G1]/Graph 区分），与 `citation_items` 一并随每帧 yield 推送到 UI。
- **ref_dataframe**：Chat 页新增「引用列表（点击行跳转 PDF）」`gr.Dataframe`，展示引用 / 来源 / 页码 / 摘要；`ref_dataframe.select` 绑定 `handle_ref_click`，从 `chat_citation_state` 取 pid、page，写入 `read["jump_request_tb"]`，实现点表格行即跳转阅读 Tab 并翻到对应页。
- **多路输出**：流式输出扩展为 7 元组（chatbot、msg_input、chat_status、citation_bar、current_references_ui、ref_dataframe、chat_citation_state），每帧均带 reference_list 与 citation_items。

#### 🔧 修复

**Chunk 页码入库（解决「全是 p.1」）**

- **rag_service._chunk_document**：当解析结果存在「有实质内容」(content 长度 > 50) 且含 `page_start`/`page_end` 的 sections 时，按节分块并为每节 chunk 写入 `page_number=section.page_start`；否则全文分块并显式传入 `page_number=1`。
- **semantic_chunker / paragraph_chunker**：`_create_chunk` / `_make_chunk` 支持 `kwargs["page_number"]`，写入 `ChunkMetadata.page_number` 与 `TextChunk.page_number`，确保 MinerU/Docling 的章节页码正确进入向量库与引用展示。

#### 📝 代码变更

| 文件 | 变更描述 |
|------|----------|
| `tabs/chat/__init__.py` | reference_list + citation_items 每帧 yield；ref_dataframe、chat_citation_state；handle_ref_click；_yield 返回 7 元组；handle_chat_clear 清空 7 项 |
| `main.py` | send/submit 输出增加 ref_dataframe、chat_citation_state；clear 输出同步；ref_dataframe.select → handle_ref_click → jump_request_tb |
| `services/rag_service.py` | _chunk_document 按节分块并传 page_number，全文分块传 page_number=1 |
| `services/chunking/semantic_chunker.py` | _create_chunk 写入 page_number（metadata + TextChunk） |
| `services/chunking/paragraph_chunker.py` | _make_chunk 写入 page_number（metadata + TextChunk） |

---

### 2026-03-14 (ref-context-bridge-and-refresh)

#### 🔧 修复

**引用来源面板与点击跳转**

- **上下文同步**：在 Synthesizer 开始生成前（多路召回完成后）即从 `retrieval.chunks` 构建 `citation_items`（pid、page、label）并渲染 `refs_ui`，保证 [1] 与列表第 1 项一致；Phase 3「评估完成，准备合成答案...」的 yield 即传入 `refs_ui`，避免中间步骤用空字符串覆盖。
- **强制刷新**：流式结束后对同一 5 元组（history、status、citation_bar、current_references_ui）再 yield 一次，解决 Gradio 6.2 异步下「当前回答引用来源」仍显示「暂无引用来源」的问题。
- **点击跳转**：引用卡片已带 `onclick="jumpToSource(pid, page)"`，与全局 `jumpToSource` 一致，点击后切到阅读 Tab 并定位 PDF 页码，无需额外 Python 绑定。

#### 📝 代码变更

| 文件 | 变更描述 |
|------|----------|
| `tabs/chat/__init__.py` | 检索后即构建 citation_items/refs_ui；Phase 3 yield 传入 refs_ui；RAG 上下文循环不再重复 append citation_items；结束双 yield 强制刷新引用面板 |

---

### 2026-03-14 (ultimate-sprint-graph-rag)

#### 🚀 新功能

**1. 轻量级 Graph RAG**

- **数据**：`ParsedDocument` 增加 `edges`（主-谓-宾三元组）与 `edge_chunk_ids`；解析后对前 30 个 chunk 做 LLM 关系抽取并写入文档图。
- **检索**：第一路向量 Top5，第二路基于 edges 一度关联扩展，合并上下文；引用区分 **[1]-[5]**（向量直接匹配）与 **[G1]-[Gk]**（知识图谱扩展），回答末尾与引用栏同步标注。
- **标题降级**：若全文仅一个一级标题，则二级标题（##）视作独立 Section 参与摘要生成。

**2. 意图识别与上下文锁定**

- **阅读 Tab 当前文档**：Chat 发送时传入 `read["pdf_selector"]`，将「当前打开的文档」摘要或前 500 字注入 system 上下文，强制优先参考。
- **翻译摘要**：用户说「翻译摘要」时识别为 TASK_TRANSLATE，直接提取当前文档 Summary/前 500 字调用 Translator 翻译并标注 `[参考本地文献]`。
- **概念解释 (CONCEPT_EXPLAIN)**：问题含 RAG、知识图谱等学术名词时，要求「本地检索 + 常识」路线，严禁仅回复「未在本地找到」。
- **引用透明化**：Synthesizer 要求明确标注 `[参考本地文献: 第X页]` 或 `[扩展知识]`。

**3. 写作 Tab 错别字/病句检查**

- 新增「检查」按钮与 `handle_check_typos(draft_text)`，本地正则检测常见错别字与学术病句（的得地、在再、做作、进行了等），结果输出到 AI 建议框。

**4. 图片 Base64 全量**

- `inline_images_in_markdown` 增加相对路径 fallback（`images/`、`figures/`、`fig/`、`assets/`）；`_get_mineru_raw_markdown` 在无 RAG 缓存时从 `lib` 的 `parsed_document.content` / `text` 取内容并做内联，Demo 与展示侧图片统一 Base64，避免云端 404。

#### 🔧 改进

- **Demo 加载**：改为追加策略，不清空当前文献列表，白皮书作为虚拟文档追加并自动选中；移动端「体验 Demo」置于上传组件上方，加载后收起上传并跳转阅读视图。
- **PDF 高亮**：`ChunkPosition` 支持 `char_offset_start`/`char_offset_end`，bbox 不可用时前端可做 character offset fallback 精准定位。
- **Zen 模式**：写作区右侧列增加磨砂玻璃（`backdrop-filter: blur(12px)`）与半透明背景。

#### 📝 代码变更

| 文件 | 变更描述 |
|------|----------|
| `models/parse_result.py` | ParsedDocument 增加 edges、edge_chunk_ids 及 to_dict |
| `services/rag_service.py` | 标题降级；_extract_relation_edges；retrieve 向量 Top5 + _graph_expand_chunks；_build_context_with_refs |
| `tabs/chat/__init__.py` | _get_current_doc_content；handle_chat_stream_legacy 增加 active_read_pid、翻译摘要短路、当前文档注入、CONCEPT_EXPLAIN、引用 [1]/[G1] |
| `tabs/read/__init__.py` | _get_mineru_raw_markdown 从 lib 取内容 + 多 base_dir 内联；Path 导入 |
| `tabs/write/__init__.py` | handle_check_typos、check_btn |
| `main.py` | chat 输入增加 read["pdf_selector"]；check_btn 绑定 handle_check_typos |
| `core/utils.py` | inline_images_in_markdown 相对路径多子目录 fallback |
| `ui/styles.py` | Zen 模式 #write-right-col 磨砂玻璃样式 |

---

### 2026-03-14 (readme-structure-env)

#### 📝 文档

- **README**：核心功能按四 Tab（阅读 / 整理 / 写作 / AI 助手）重写；阅读模式表更新为五种（文档结构、去掉分块数据库）；密码保护相关描述与环境变量已去除；环境变量表增加 MinerU 相关（`MINERU_API_KEY`、`MINERU_API_BASE`、`MINERU_API_ENDPOINT`、`MINERU_PARSE_METHOD`）；项目结构更新（core/utils 内联、parser/mineru_cloud_parser、tabs 与 scripts 描述）；Multi-Agent 架构改为「整理/写作侧」与「AI 助手 RAG 流水线」四阶段分块表述。

---

### 2026-03-14 (zen-color-mineru-inline)

#### 🔧 改进

- **Zen 模式**：改为仅颜色区分，不再改变布局尺寸。开启后外圈（`.gradio-container`）变灰（`#e2e8f0`），写作区保持白底卡片并带圆角/阴影，便于专注写作。
- **新上传文档图片**：MinerU Markdown 视图在展示时对 `](/file=...)` 做 Base64 内联（与 Demo 策略一致），新上传文档的图片在任意环境均可正常显示。内联逻辑抽到 `core.utils.inline_images_in_markdown`，供 Demo 脚本与阅读区共用；`_get_mineru_raw_markdown` 在存在 `cache_dir` 时自动内联。

#### 📝 代码变更

| 文件 | 变更描述 |
|------|----------|
| `ui/styles.py` | Zen 模式仅设外圈灰底与写作区卡片样式，移除全屏 min-height |
| `core/utils.py` | 新增 `inline_images_in_markdown`、`image_path_to_base64_data_url` |
| `tabs/read/__init__.py` | `_get_mineru_raw_markdown` 展示时调用内联，新上传文档图片可加载 |
| `scripts/generate_demo_mock.py` | 改为从 `core.utils` 引入 `inline_images_in_markdown` |

---

### 2026-03-14 (read-simplify-rag-refs-write-zen)

#### 🔧 改进

**1. 阅读模式精简**

- 「Docling结构」改名为「**文档结构**」；「**分块数据库**」选项已从查看模式中移除（兼容旧状态时自动回退为文档结构）。
- 「RAG分块粒度」「分块模式」控件改为隐藏（`visible=False`），仍可通过环境变量/配置生效。

**2. RAG 引用来源与一键跳转**

- 修复「📑 当前回答引用来源」在流式输出期间被清空的问题：在合成阶段开始前预渲染 `citation_bar` 与 `refs_ui`，流式 yield 时持续传入，保证有引用时始终展示卡片并可点击跳转 PDF。
- `_yield()` 支持传入 `citation_html` / `refs_ui` 以在打字机输出过程中保持引用区显示。

**3. 写作 Tab**

- **Zen 模式**：开启后隐藏左侧栏，外圈变灰、写作区保持卡片样式（后改为仅颜色区分，见 `zen-color-mineru-inline`）。
- **一键语病/润色**：新增「语病/润色」按钮与 `handle_polish(draft_text)`，对写作区全文做语病检查与润色后写回草稿框。

#### 📝 代码变更

| 文件 | 变更描述 |
|------|----------|
| `tabs/read/__init__.py` | view_mode 改为文档结构、移除分块数据库；chunk_granularity/chunk_mode 隐藏；handle_mode_switch 兼容旧选项 |
| `tabs/chat/__init__.py` | 合成前预渲染 refs_ui/citation_html，流式循环中传入 _yield，避免引用区被清空 |
| `tabs/write/__init__.py` | 新增 handle_polish、polish_btn；写作区列 elem_id=write-right-col |
| `ui/global_js.py` | Zen 勾选时 body 增加 write-zen-mode class |
| `ui/styles.py` | body.write-zen-mode 下 #write-right-col 样式（后改为仅颜色） |
| `main.py` | polish_btn.click → handle_polish，更新 draft_text |

---

### 2026-03-14 (demo-base64-citation-hierarchy)

#### 🚀 新功能

**1. Demo 图片 Base64 内联（跨平台加载）**

- `scripts/generate_demo_mock.py` 生成 Mock 数据时，将解析结果中的图片由路径引用改为 Base64 内联；
- 支持 `](/file=path)`（MinerU 产出）与 `](path.png)` 相对路径，统一替换为 `](data:image/xxx;base64,...)`；
- 生成的 `mock_library.json` 在 ModelScope / 本地均可 100% 加载图片，无跨平台路径失效问题。

**2. 全局引用跳转（PDF 锚点联动）**

- 新增全局 `window.jumpToPdf(pageNumOrIndex, textSnippet)`，供 RAG 回答内 [1][2] 等引用点击跳转；
- 对话内引用由 `makeCitationsClickable` 包装为 `<a class="citation-link" onclick="jumpToPdf(...)">[1]</a>`；
- 继续使用隐藏 `gr.Textbox(elem_id="jump-request-input")` 与 `handle_jump_request` 实现跨 Tab 跳转阅读页并定位页码。

**3. 五级层级与 Demo 全量输出**

- 知识树层级确认为：**Domain → Document → Section → Note/Summary → Atomic Knowledge**（Atomic 为 Note 子节点）；
- `handle_load_demo` 全量更新：`markdown_view`（mineru_markdown）、`tree_view`（tree_st）、`pdf_viewer`（pdf_selector + pdf_embed_html）、分块数据库等，加载 Demo 后前端三块视图与状态同步刷新。

#### 🔧 改进

- 阅读区 `_get_mineru_raw_markdown` 明确支持 Base64 内联图，无需 `/file=` 协议即可在 `gr.Markdown` 中显示；
- `handle_load_demo` 增加 `view_mode` 入参，按当前阅读模式刷新 pdf_text / pdf_embed / mineru_markdown，避免「后端有数据、前端不刷新」。

#### 📝 代码变更

| 文件 | 变更描述 |
|------|----------|
| `scripts/generate_demo_mock.py` | 新增 `inline_images_in_markdown()`，生成时图片 Base64 内联 |
| `tabs/read/__init__.py` | `_get_mineru_raw_markdown` 文档说明 Base64；`handle_load_demo` 文档补充全量 outputs |
| `ui/global_js.py` | 新增 `jumpToPdf()`；`makeCitationsClickable` 引用改为 `<a onclick="jumpToPdf(...)">` |

---

### 2026-03-14 (agentic-rag-and-citation-ui)

#### 🚀 新功能

**1. Agentic RAG 对话流水线（Phase 3）**

- **Reviewer 规划阶段**：先分析意图并规划检索路线；调用 `optimize_search_query()` 做意图识别与中英学术关键词提取；气泡展示「意图: 学术问答 | 提取实体: [关键词] | 规划路线: 多路召回 (Vector, Graph, ArXiv)」或「意图: 闲聊/任务 | 跳过检索」。
- **Seeker 多路执行阶段**：FAISS 本地向量检索（保留原始 question 做多语言匹配）、知识图谱检索（Mock 占位）、ArXiv 兜底（仅当本地结果少于 2 条时触发）；气泡展示「召回完毕：本地原子卡片 (n条) | 知识图谱 (0条) | ArXiv (m条)」。
- **Reviewer 评估阶段**：对召回上下文做质量评估（0–100 分），气泡展示「质量评估: xx/100，上下文充足，已过滤低质片段，交由合成器。」。
- **Synthesizer 生成阶段**：流式打字机输出，系统提示要求回答中标注引用格式如 `[Doc_1_Page_5]`、`[ArXiv_1908.123]`。

**2. 查询重写与意图过滤**

- `services/rag_service.py` 新增 `optimize_search_query(user_query)`：调用现有 LLM，先做意图识别（闲聊/打招呼/纯指令 → 返回 `NONE`），再做中英学术关键词提取；返回 `NONE` 时对话流跳过检索直接进入合成器。
- ArXiv 检索统一使用英文学术关键词，解决中文提问导致 ArXiv API 返回 0 条的问题。

**3. 引用来源独立 UI（Phase 4）**

- Chat 页新增 **当前回答引用来源** 区域（`current_references_ui`），位于引用按钮栏下方。
- Synthesizer 完成后将本次使用的本地原子卡片与 ArXiv 卡片元数据推送到该区域，以卡片列表展示。
- **点击交互**：本地 PDF 卡片点击触发 `jumpToSource(pid, page)` 跳转阅读页并定位页码；ArXiv 卡片点击在新窗口打开 `https://arxiv.org/abs/ID`。

#### 🔧 改进

- ArXiv API 请求改为 **HTTPS**（`https://export.arxiv.org`），连接超时由 10s 调整为 20s，减少超时与网络拦截。
- 对话流 yield 统一为 5 个输出：`chatbot`、`msg_input`、`chat_status`、`citation_bar`、`current_references_ui`；清空对话时一并清空引用来源区域。

#### 📝 代码变更

| 文件 | 变更描述 |
|------|----------|
| `services/rag_service.py` | 新增 `_QUERY_REWRITE_SYSTEM`、`optimize_search_query()` |
| `tabs/chat/__init__.py` | 重写 `handle_chat_stream_legacy` 为四阶段 Agentic 流水线；新增 `_render_references_ui()`；`build_chat_tab` 增加 `current_references_ui`；`handle_chat_clear` 增加对引用 UI 的清空 |
| `main.py` | Chat 发送/提交/清空事件增加 `current_references_ui` 输出绑定 |

---

### 2026-03-14 (mineru-cloud-and-demo-static)

#### 🚀 新功能

**1. MinerU Cloud 解析后端**

- 新增 `MinerUCloudParser`，基于 MinerU Cloud API v4 实现高精度 PDF 解析；
- 通过 `PARSER_BACKEND=mineru` 与 `MINERU_API_KEY` 环境变量启用云端解析；
- 统一路由到云端解析器，不再调用本地 `mineru.EXE` CLI，云端不可用时自动回退至 Docling。

**2. Demo 静态数据秒开体验**

- `tabs/read` 中新增「🎁 体验: 加载官方架构白皮书」按钮；
- 新增 `demo_data/` 目录约定：`demo_paper.pdf`、`mock_library.json`、`mock_notes.json`、`faiss_index/`；
- Demo 加载逻辑改为优先读取静态 JSON 和预构建向量索引，绝不触发实时解析与 embedding；
- 当静态文件缺失时，自动注入最小化内存 Mock 数据，保证 UI 不崩溃。

**3. Demo 数据离线生成脚本**

- 新增 `scripts/generate_demo_mock.py` 脚本；
- 支持从 `demo_data/demo_paper.pdf` 出发，调用真实 `RAGService` 生成向量索引与状态快照；
- 自动将向量索引保存到 `demo_data/faiss_index/`，并输出 `mock_library.json` / `mock_notes.json`；
- 可作为端到端回归测试的辅助工具，方便在算法更新后一键刷新 Demo 数据。

#### 📝 代码变更

| 文件                                      | 变更描述                                         |
| ----------------------------------------- | ------------------------------------------------ |
| `core/config.py`                          | 新增 MinerU Cloud 相关配置项                     |
| `services/parser/mineru_cloud_parser.py`  | MinerU Cloud v4 解析实现与 ZIP 结果解析          |
| `services/rag_service.py`                 | 解析器路由切换为 MinerU Cloud，新增 Demo 索引加载 |
| `tabs/read/__init__.py`                  | Demo 按钮与静态 Demo 加载逻辑                     |
| `scripts/generate_demo_mock.py`           | Demo 静态数据与向量索引离线生成脚本               |
| `README.md`                               | 新增 Demo 体验与 MinerU Cloud 集成说明           |

---

### 2026-03-10 (mineru-deepseek-chunk)

#### 🚀 新功能

**1. MinerU 解析优化**

- 结构视图直接读取 `parsed_docs` 缓存中的原始章节，彻底去除模糊关键词匹配
- 新增 **MinerU Markdown** 查看模式：直接展示 MinerU 解析生成的原始 Markdown，含标题层级、置信度评分
- MinerU 多版本兼容：自动检测 UNIPipe Python API 或 `magic-pdf` CLI 并择优使用

**2. DeepSeek 官方 API 直连降级**

- ModelScope 所有模型全部触发限额（HTTP 429）后，自动切换至 DeepSeek 官方 API（`deepseek-chat`）
- 通过 `.env` 中的 `DEEPSEEK_API_KEY` / `DEEPSEEK_API_BASE` 配置，无需改代码
- 三级容错链：ModelScope 主模型 → ModelScope 备用模型池 → DeepSeek 官方 API

**3. 段落分块模式**

- 新增 `ParagraphChunker`：按 `\n\n` 空行直接切割，无需加载 embedding 模型，启动快
- 自动合并过短段落（< 80 token），拆分超长段落（> max_chunk_size）
- 适合 MinerU / Docling 等已保留段落结构的解析结果

**4. 分块 UI 控件**

- 阅读页左栏新增「**分块模式**」Radio（语义 / 段落），切换后热替换 chunker，对后续上传立即生效
- 新增「**RAG 分块粒度**」Radio（细 / 中 / 粗），对应三组参数预设

#### 🔧 改进

- 分块默认参数调优：`chunk_size` 512→900，`overlap` 50→120，`similarity_threshold` 0.7→0.58
- `SemanticChunker` 最小句子数 2→4，新增最小 token 阈值门槛，减少碎片分块
- 所有分块参数支持环境变量覆盖：`CHUNK_MODE` / `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` / `RAG_SIMILARITY_THRESHOLD`

#### 📝 代码变更

| 文件                                          | 变更描述                                           |
| --------------------------------------------- | -------------------------------------------------- |
| `agents/base.py`                            | `call_llm()` 新增 DeepSeek 直连降级逻辑            |
| `core/config.py`                            | 新增 `DEEPSEEK_API_KEY/BASE`，`chunk_mode` 配置    |
| `services/chunking/paragraph_chunker.py`    | 新增段落分块器（新文件）                           |
| `services/chunking/__init__.py`             | 导出 `ParagraphChunker`                            |
| `services/rag_service.py`                   | 新增 `parsed_docs` 缓存、`update_chunk_mode()`、`update_chunking_profile()` |
| `tabs/read/__init__.py`                     | 新增 MinerU Markdown 视图、重写结构视图、分块 UI 控件 |

---

### 2026-03-08 v2.6.0 (knowledge-tree-sections)

#### 🚀 新功能

**1. 知识树章节节点自动创建**

- RAG处理完成后自动创建section节点
- 章节摘要同步到知识树metadata
- 知识树展示三级结构：domain → document → section → note

**2. AI助手反馈增强**

- 添加点赞/点踩按钮
- 添加一键复制回答按钮
- 反馈状态显示

#### 🐛 修复

- **问AI功能修复**：handle_ai_ask使用yield from正确传递生成器
- **引用提取修复**：ChunkMetadata.doc_id属性访问错误
- **知识树ID前缀**：global_js.py中KN-改为NK-

#### 📝 代码变更

| 文件                          | 变更描述                         |
| ----------------------------- | -------------------------------- |
| `models/search.py`          | ProcessingResult添加sections字段 |
| `services/rag_service.py`   | 返回章节信息用于知识树构建       |
| `tabs/read/__init__.py`     | RAG处理后创建section节点         |
| `tabs/chat/__init__.py`     | AI反馈功能、生成器修复           |
| `ui/renderers.py`           | 章节摘要显示                     |
| `ui/global_js.py`           | 知识树ID前缀修复                 |
| `tabs/organize/__init__.py` | 引用提取ChunkMetadata修复        |
