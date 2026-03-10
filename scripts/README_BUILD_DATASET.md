# SFT 数据集构建脚本使用指南

## 功能概览

`build_sft_dataset.py` 是一个全自动的学术数据集构建工具，支持：

1. **arXiv 自动爬取** - 按关键词搜索并下载最新学术 PDF
2. **Semantic Scholar 引文抓取** - 自动获取 BibTeX 和引用关系（类似 Zotero）
3. **MinerU 高精度解析** - 转换 PDF 为结构化 Markdown
4. **Teacher 模型蒸馏** - 大模型提取 AtomicNote JSON
5. **ShareGPT 格式输出** - 生成 ms-swift 可用的训练数据
6. **测试集自动划分** - 支持按比例划分训练/测试集

## 环境配置

### 1. 安装依赖

```bash
cd ai-hackthon
pip install -r requirements.txt
```

### 2. 配置 API Keys

在 `.env` 文件中配置（二选一）：

**选项 A: 使用 ModelScope API（默认）**
```env
MS_KEY=ms-your-key-here
API_BASE=https://api-inference.modelscope.cn/v1
```

**选项 B: 使用 DeepSeek API（推荐 - 成本更低）**
```env
DEEPSEEK_API_KEY=sk-your-deepseek-key-here
DEEPSEEK_API_BASE=https://api.deepseek.com
```

### 3. 配置 MinerU

确保本地已安装 MinerU 并配置好 `magic-pdf` 命令：

```bash
# 测试 MinerU 是否可用
magic-pdf --version
```

## 基础用法

### 最简单的命令（使用 ModelScope API）

```bash
python scripts/build_sft_dataset.py \
  --keywords "Retrieval Augmented Generation" "Knowledge Graph" \
  --max-papers 50
```

### 使用 DeepSeek API（推荐）

```bash
python scripts/build_sft_dataset.py \
  --keywords "Retrieval Augmented Generation" "Knowledge Graph" \
  --max-papers 50 \
  --use-deepseek \
  --teacher-model deepseek-chat
```

### 启用 Semantic Scholar 引文抓取

```bash
python scripts/build_sft_dataset.py \
  --keywords "RAG" "Question Answering" \
  --max-papers 30 \
  --use-deepseek \
  --enable-semantic-scholar
```

### 启用测试集划分

```bash
python scripts/build_sft_dataset.py \
  --keywords "Machine Learning" \
  --max-papers 100 \
  --use-deepseek \
  --enable-semantic-scholar \
  --test-split-ratio 0.1
```

## 主要参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--keywords` | arXiv 搜索关键词（可多个） | RAG, Knowledge Graph |
| `--max-papers` | 最多下载论文数 | 50 |
| `--use-deepseek` | 使用 DeepSeek API | False |
| `--enable-semantic-scholar` | 启用 Semantic Scholar 引文抓取 | False |
| `--test-split-ratio` | 测试集比例（0.0-0.5） | 0.0 |
| `--download-interval` | arXiv 下载间隔（秒，≥3） | 3.0 |
| `--teacher-model` | Teacher 模型名称 | deepseek-ai/DeepSeek-V3.2 |
| `--output-jsonl` | 输出文件路径 | data/train.jsonl |

## 生成的数据格式

### ShareGPT 格式（用于 ms-swift 训练）

```json
{
  "messages": [
    {
      "role": "user",
      "content": "请将以下学术章节提炼为 AtomicNote JSON 数组..."
    },
    {
      "role": "assistant",
      "content": "[{\"knowledge_type\": \"方法\", \"title\": \"...\", \"content\": \"...\", \"page_num\": 3, \"bbox\": [100, 200, 300, 250], \"bibtex_citation\": \"@article{...}\"}]"
    }
  ],
  "meta": {
    "source": "arxiv+mineru+teacher",
    "arxiv_id": "2301.12345",
    "paper_title": "...",
    "section_title": "Introduction",
    "keywords": ["RAG"]
  }
}
```

### AtomicNote Schema

每个提取的笔记必须包含：

```json
{
  "knowledge_type": "方法|公式|图像|定义|观点|数据|其他",
  "title": "笔记标题",
  "content": "笔记内容",
  "page_num": 3,
  "bbox": [x1, y1, x2, y2],
  "bibtex_citation": "@article{...}"
}
```

## 完整工作流示例

### 1. 构建训练集（100篇论文，90% 训练 / 10% 测试）

```bash
python scripts/build_sft_dataset.py \
  --keywords "Retrieval Augmented Generation" "Semantic Search" "Vector Database" \
  --max-papers 100 \
  --use-deepseek \
  --enable-semantic-scholar \
  --test-split-ratio 0.1 \
  --output-jsonl data/train.jsonl
```

输出文件：
- `data/train.jsonl` - 90 篇论文的训练数据
- `data/test_train.jsonl` - 10 篇论文的测试数据

### 2. 使用 ms-swift 进行微调

```bash
# 训练 Qwen2.5-3B
swift sft \
  --model Qwen/Qwen2.5-3B \
  --dataset data/train.jsonl \
  --output_dir output/qwen2.5-3b-atomic \
  --num_train_epochs 3 \
  --per_device_train_batch_size 2 \
  --gradient_accumulation_steps 8 \
  --learning_rate 5e-5 \
  --save_strategy epoch

# 评估测试集
swift eval \
  --model output/qwen2.5-3b-atomic \
  --dataset data/test_train.jsonl
```

## 最佳实践

### 1. 控制成本

- 使用 `--use-deepseek` + DeepSeek API（比 ModelScope 便宜 10-20 倍）
- 限制 `--max-papers` 到合理数量（50-100 篇足够初步训练）
- 使用 `--max-sections-per-paper 10` 限制每篇论文的章节数

### 2. 提升质量

- 启用 `--enable-semantic-scholar` 获取真实引文信息
- 精选 `--keywords` 确保论文相关性高
- 检查 `data/train.jsonl` 前几条样本，确认质量

### 3. 调试与恢复

脚本支持断点续传：
- 已下载的 PDF 会跳过（检查 `data/raw/arxiv_pdf/`）
- 已解析的 Markdown 会复用（检查 `data/raw/mineru_out/`）
- 输出文件使用追加模式，支持多次运行累积数据

### 4. 异常处理

脚本内置容错机制：
- 单篇论文失败不会中断全流程
- API 调用失败自动重试（最多 3 次）
- 网络超时自动跳过并继续

## 故障排查

### 1. arXiv 下载失败（HTTP 503）

- 确认 `--download-interval` ≥ 3 秒
- 检查本地网络是否正常
- 尝试降低 `--max-papers` 数量

### 2. MinerU 解析失败

```bash
# 测试单个 PDF
magic-pdf -p test.pdf -o output -m auto
```

- 确认 MinerU 已正确安装
- 检查模型文件是否下载完整（见 AtomicLab/MODEL_STORAGE_CONFIG.md）

### 3. Teacher API 调用失败

- 检查 `.env` 中的 API Key 是否有效
- 确认账户有足够余额
- 尝试降低 `--max-section-chars` 减少单次请求 token 数

### 4. Semantic Scholar 限流（429 错误）

- 脚本已内置 3.2 秒间隔（API 限制：100 req / 5 min）
- 如遇限流，脚本会自动等待 10 秒后继续

## 后续工作

### 1. 构建 Golden Dataset（RAG 测试集）

从训练数据中挑选 50 篇高质量论文：

```bash
# 随机采样 50 篇构建沙盒知识库
import json
import random

with open("data/train.jsonl") as f:
    all_records = [json.loads(line) for line in f]

# 按论文去重
papers = {}
for rec in all_records:
    arxiv_id = rec["meta"]["arxiv_id"]
    if arxiv_id not in papers:
        papers[arxiv_id] = []
    papers[arxiv_id].append(rec)

# 随机选 50 篇
golden_papers = random.sample(list(papers.values()), min(50, len(papers)))
```

### 2. 人工问题标注

为 Golden Dataset 设计 20 个复杂问题：

- **单文献精确问答**: "论文 X 在第 5 页提到的 RAG 方法是什么？"
- **多文献对比**: "比较论文 A 和 B 中的 RAG 架构差异"
- **跨文献合成**: "总结这 5 篇论文对检索质量的评估指标"

### 3. 评估指标

- **准确度**: 小模型分类准确率（方法/公式/观点等七分类）
- **完整性**: `page_num` 和 `bbox` 填充率
- **引用质量**: `bibtex_citation` 准确率

## 参考链接

- ms-swift 文档: https://swift.readthedocs.io/zh-cn/latest/
- ModelScope API: https://www.modelscope.cn/docs/models/download
- Semantic Scholar API: https://api.semanticscholar.org/api-docs/
- arXiv API 规范: https://info.arxiv.org/help/api/index.html
