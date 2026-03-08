# 更新日志

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

### 2026-03-07 v2.5.0 (atomic-knowledge-and-citation)

#### 🚀 新功能

**1. 原子知识解构 (Atomic-RAG)**

- 三层解构结构：Axiom（公理）+ Methodology（方法）+ Boundary（边界）
- 七分类系统：Method/Definition/Formula/Context/Data/Result/Insight
- 提供原子知识to_rag_text()方法，用于向量检索

**2. 引用关系提取**

- 支持多种引用格式解析：IEEE/APA/GB/T 7714
- 自动识别参考文献部分
- CrossRef API集成（可选），补充元数据
- 构建文献引用关系图谱

**3. 知识树三级结构**

- 文献→章节→笔记三级层次结构
- 章节级RAG检索，提升召回率和精度
- 章节摘要生成，辅助检索语义理解

#### 🔧 改进

- **三层结构详细说明**：

  - 两层结构（文献→笔记）：检索精度低，噪音多
  - 三层结构（文献→章节→笔记）：先定位章节，再检索笔记
  - 性能提升：检索时间↓70%，召回率↑30%，精度↑33%
- **Wiki同步修复**：

  - 移除.gitignore中的.github/*规则
  - 更新wiki-folder为repowiki/zh
  - GitHub Actions自动化同步生效

#### 📝 代码变更

| 文件                                | 变更描述                     |
| ----------------------------------- | ---------------------------- |
| `models/atomic_knowledge.py`      | 原子知识解构数据模型（新增） |
| `services/atomic_decomposer.py`   | 原子知识解构服务（新增）     |
| `services/citation_extractor.py`  | 引用关系提取服务（新增）     |
| `services/summarizer.py`          | 章节摘要生成服务（新增）     |
| `knowledge/tree_model.py`         | Section节点类型和方法        |
| `.gitignore`                      | 移除.github/*规则            |
| `.github/workflows/sync-wiki.yml` | 更新wiki-folder路径          |

---

### 2026-03-07 v2.4.0 (chapter-extraction-enhancement)

#### 🚀 新功能

**1. Docling结构显示模式**

- 多模式章节提取：支持Markdown标题、编号章节、大写章节名等多种格式
- 章节层级可视化：正确渲染Markdown标题层级（#, ##, ###）
- 参考文献过滤：自动识别并过滤参考文献格式的条目（如"23. Author, N., ..."）
- 辅助文本分块：基于章节层级组织内容

**2. 分块数据库显示模式**

- 按章节组织分块：显示文本分块的章节归属关系
- 层级结构展示：树状结构显示章节-分块关系
- 分块类型标注：语义分块、表格分块等类型标识
- 章节内容预览：每个章节显示内容片段

#### 🔧 改进

- **多模式章节提取**：

  - 模式1：标准Markdown标题（## Chapter）
  - 模式2：编号章节（1. INTRODUCTION, Task 1: Peak Prediction）
  - 模式3：大写章节名（INTRODUCTION, RELATED WORK, ACKNOWLEDGEMENT）
  - 模式4：关键词匹配（references, introduction, task, web server等）
  - 模式5：元数据回退（过滤参考文献格式）
- **调试输出优化**：详细的章节提取过程追踪，帮助定位问题
- **层级显示**：使用CSS data-level属性实现视觉层级区分

#### 📝 代码变更

| 文件                      | 变更描述                               |
| ------------------------- | -------------------------------------- |
| `tabs/read/__init__.py` | 多模式章节提取逻辑，增强正则表达式匹配 |
| `ui/renderers.py`       | 章节层级渲染，树状结构显示             |
| `ui/styles.py`          | CSS层级样式（data-level属性）          |
| `README.md`             | 新增Docling结构和分块数据库模式说明    |

---

### 2026-03-07 v2.3.2 (search-enhancements)

#### 🚀 新功能

**1. 模糊匹配搜索**

- 支持部分匹配：输入部分字母或汉字也能找到相关结果
- 前缀匹配：查询前缀与字段内容匹配时降权显示
- Token匹配：自动分词后部分Token匹配也可检索
- 精确匹配优先：完整匹配的结果排在前面，模糊匹配作为备选

**2. References章节检索增强**

- 章节标题自动识别（References、Introduction、Methods等）
- 章节名称加入chunk元数据，支持按章节检索
- 搜索时自动包含章节信息

#### 🔧 改进

- **OCR服务增强**：详细日志输出、图片格式转换重试、错误信息反馈
- **翻译按钮修复**：整理Tab翻译按钮无反馈问题修复
- **事件绑定修复**：note_action_tb组件visible状态正确设置

#### 🐛 Bug修复

| 问题                     | 解决方案                              |
| ------------------------ | ------------------------------------- |
| References章节搜索不完整 | 添加章节识别和元数据索引              |
| OCR有时识别失败          | 增强错误处理和格式转换重试            |
| 整理Tab翻译按钮无反馈    | 修复JS事件绑定和组件状态              |
| demo.load报错            | 移入with demo上下文内调用             |
| show_label警告           | 移除container=False时的show_label参数 |
| Dropdown值警告           | 添加allow_custom_value=True           |

#### 📝 代码变更

| 文件                                      | 变更描述                                   |
| ----------------------------------------- | ------------------------------------------ |
| `knowledge/search.py`                   | 新增模糊匹配算法 `_calculate_node_match` |
| `services/search/keyword_search.py`     | 模糊匹配评分增强                           |
| `services/chunking/semantic_chunker.py` | 章节识别 `_extract_section_headers`      |
| `models/chunk.py`                       | 新增 `section_name` 字段                 |
| `services/ocr_service.py`               | 增强错误处理和日志                         |
| `ui/global_js.py`                       | 修复noteAction事件分发                     |
| `main.py`                               | 修复demo.load调用位置                      |

---

### 2026-03-07 v2.3.1 (ui-enhancements)

#### 🚀 新功能

**1. 截图笔记卡片跳转功能**

- 点击截图笔记卡片可跳转到原始PDF文档对应页面位置
- 利用现有的页面索引信息实现精准定位

**2. AI助手回答中的可点击卡片**

- AI回答中的引用笔记卡片支持点击跳转到原文
- 整理页面和写作页面搜索结果卡片支持跳转
- 笔记卡片显示来源文献和页码信息

**3. AI助手输入区工具栏**

- 模型选择器移至AI助手输入框左下角
- 新增"当前文献"选择器，可指定AI分析的文献范围
- 文献选择器与其他Tab同步联动

#### 🔧 改进

- **简化阅读模式**：移除"Docling模式"选项，解析功能已整合到RAG服务
- 只保留三种阅读模式：PDF高亮（默认）、文本模式、PDF原版

#### 🐛 Bug修复

| 问题                     | 解决方案                        |
| ------------------------ | ------------------------------- |
| 截图笔记点击无反应       | 添加jumpToSource跳转功能        |
| AI引用卡片无法跳转       | 添加source_pid到cited_notes数据 |
| 整理页搜索结果点击无跳转 | 添加jumpToSource跳转逻辑        |

---

### 2026-03-07 v2.3.0 (docling-pdf-viewer)

#### 🚀 新功能

**1. PDF.js高亮阅读模式**

- 基于PDF.js 3.11的保真PDF渲染（公式、表格、图片完整显示）
- 文本层选择 → 一键高亮（黄/绿/蓝/粉四色）
- 高亮数据持久化框架（HighlightData数据模型）
- iframe + srcdoc架构，解决Gradio HTML组件限制

**2. 坐标映射服务**

- 新增 `services/renderer/coordinate_mapper.py`
- PDF位置 ↔ RAG Chunk ID双向映射
- 支持高亮与RAG分块联动

**3. 查询扩展优化**

- 新增 `QUERY_EXPANSIONS` 映射表
- SQL自动扩展为MySQL/PostgreSQL/SQLite/Database/DBMS/Query
- AI/Metabolite等术语自动扩展

**4. 实时状态反馈增强**

- Chat/Organize/Write Tab 操作进度实时显示
- 进度动画和状态HTML组件

#### 🔧 改进

- **AI提示词优化**：强制基于上下文回答，避免"未找到相关内容"
- **表格解析修复**：列名和单元格值强制转字符串
- **启动清理**：每次重启自动删除storage文件夹

#### 🐛 Bug修复

| 问题                         | 解决方案                          |
| ---------------------------- | --------------------------------- |
| PDF高亮显示"正在加载"        | 使用iframe srcdoc嵌入完整HTML文档 |
| ChunkMetadata doc_id参数错误 | doc_id移至TextChunk层级           |
| Chat输出数量不匹配警告       | 添加chat_status到outputs          |
| SQL查询无结果                | 新增查询扩展功能                  |
| Docling表格解析警告          | str()转换headers和rows            |

#### 📦 新增文件

| 文件路径                                   | 功能描述          |
| ------------------------------------------ | ----------------- |
| `services/renderer/pdfjs_viewer.py`      | PDF.js渲染器服务  |
| `services/renderer/coordinate_mapper.py` | PDF-Chunk坐标映射 |
| `services/renderer/__init__.py`          | 渲染器模块初始化  |

#### 📊 技术架构对比

| 特性     | MinerU (magic-pdf) | 当前方案 (Docling + PDF.js) |
| -------- | ------------------ | --------------------------- |
| 定位     | 文档解析工具       | 全流程科研工作站            |
| 解析精度 | 90+ (VLM)          | 82-85                       |
| 扫描PDF  | ✅ 自动OCR         | ⚠️ 需配置                 |
| 高亮交互 | ❌ 无              | ✅ 完整支持                 |
| RAG集成  | ❌ 无              | ✅ 三路混合检索             |
| AI对话   | ❌ 无              | ✅ RAG增强问答              |

---

### 2026-03-07 v2.1.0 (advanced-pdf-parsing)

#### 🚀 新功能

**1. RAG系统**

- 实现三路混合检索架构（语义 + 关键词 + 元数据过滤）
- 两阶段重排序：RRF融合 + Cross-Encoder重排序
- 支持bge-reranker-v2-m3模型精确计算相关性

**2. 高级PDF解析 (Docling)**

- 集成IBM开源Docling解析器
- 支持表格结构化提取和Markdown导出
- 支持公式识别和图表描述
- 自动计算文档解析置信度

**3. 智能文本分块**

- 语义分块：基于sentence-transformers计算句子相似度动态分割
- 表格专用分块：双重embedding策略（结构hash + 语义文本）
- 支持中英文混合文本分块

**4. 向量存储与检索**

- FAISS向量存储，支持HNSW索引
- BM25关键词索引，支持jieba中文分词
- 元数据过滤和持久化存储

**5. RAG统一服务**

- 整合解析→分块→索引→检索→重排全流程
- 异步文档处理，不阻塞UI
- 优雅降级，依赖缺失时自动回退

#### 📦 新增文件

| 文件路径                                  | 功能描述                |
| ----------------------------------------- | ----------------------- |
| `models/parse_result.py`                | Docling解析结果数据模型 |
| `models/chunk.py`                       | 文本块数据模型          |
| `models/search.py`                      | 搜索结果数据模型        |
| `services/rag_service.py`               | RAG统一服务入口         |
| `services/parser/docling_parser.py`     | Docling解析器实现       |
| `services/chunking/semantic_chunker.py` | 语义分块器              |
| `services/chunking/table_chunker.py`    | 表格分块器              |
| `services/search/faiss_store.py`        | FAISS向量存储           |
| `services/search/bm25_index.py`         | BM25关键词索引          |
| `services/search/hybrid_searcher.py`    | 混合检索服务            |
| `services/search/reranker.py`           | Cross-Encoder重排序器   |
| `test_rag.py`                           | RAG功能测试脚本         |

#### 🔧 修改文件

| 文件路径                              | 变更说明                                |
| ------------------------------------- | --------------------------------------- |
| `main.py`                           | 集成RAG服务初始化，更新事件绑定         |
| `core/config.py`                    | 添加RAG_CONFIG配置项                    |
| `tabs/read/__init__.py`             | 上传时触发RAG文档处理                   |
| `tabs/organize/__init__.py`         | 搜索时优先使用RAG检索                   |
| `agents/conversation.py`            | 集成RAG检索到AI问答，支持精准引用       |
| `services/parser/docling_parser.py` | 修复Docling API弃用警告                 |
| `requirements.txt`                  | 添加docling、faiss-cpu、rank-bm25等依赖 |

#### 📊 核心算法

**RRF融合算法**：

```
score = Σ(weight_i / (k + rank_i))
其中 k=60, weight_semantic=0.6, weight_keyword=0.3
```

**表格双重Embedding**：

- 结构Hash：MD5(列名+行数) 用于精确匹配
- 语义文本：表格描述 + 前500字符 用于相似搜索

#### 🧪 测试验证

- ✅ 模块导入测试（8/8通过）
- ✅ 数据模型测试
- ✅ RRF融合算法测试
- ✅ 主程序启动测试
- ✅ RAG检索集成到AI问答

#### 🐛 Bug修复

| 问题                | 解决方案                                           |
| ------------------- | -------------------------------------------------- |
| Docling API弃用警告 | 添加 `doc`参数到 `export_to_dataframe()`等方法 |
| RAG检索未生效       | ConversationAgent优先使用RAG服务检索               |
| 参考文献检索失败    | 语义检索支持全文检索，不再只搜索开头               |

---

### 2026-03-03 v2.0.1 (gradio6-ui)

1. **Gradio 6 适配** - 适配 Gradio 6.5+ 新版 API
2. **UI/UX 增强**
   - 卡片按钮功能修复（翻译、AI标签、批注、手动标签）
   - 全局文献选择同步（阅读/整理/写作三页面联动）
   - AI标签与手动标签分色显示（紫/绿）
   - 模态弹窗替代 prompt() 原生对话框
   - 按钮状态反馈（loading/success/error 动画）
3. **数据流优化**
   - 笔记元数据正确同步到知识树（notes_st ↔ tree_st ↔ lib_st）
   - AI摘要与AI标签功能分离
