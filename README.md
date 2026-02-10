# Atomic Lab | 科研驾驶舱 v1.0

沉浸式多智能体科研辅助系统，以"星际驾驶舱"为视觉隐喻，将学术文献粉碎为可检索的知识原子。

## 架构

```
+------------------+     +------------------+     +------------------+
|   Navigator      |     |   Engineer       |     |   HUD Designer   |
|   (领航员)       |     |   (首席工程师)    |     |   (界面渲染)      |
|   任务/番茄钟    |     |   语义粉碎/Qwen  |     |   原子卡片/雷达图 |
+------------------+     +------------------+     +------------------+
         |                        |                        |
         +------------------------+------------------------+
                                  |
                          SessionState (全局状态)
```

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量（已有 .env 文件，或手动设置）
#    MODELSCOPE_TOKEN=ms-xxxxx

# 3. 启动应用
python app.py
```

浏览器访问 `http://localhost:7860`

## 功能模块

| 模块 | 说明 |
|------|------|
| Mission Log (左栏) | 待办事项管理、番茄钟计时、航行建议 |
| Main Console (中栏) | 文本/PDF 输入、原子粉碎执行、雷达遥测图 |
| Atomic Storage (右栏) | 知识原子卡片流、航行统计面板 |

## 技术栈

- **前端**: Gradio + 自定义 HUD CSS
- **LLM**: Qwen (ModelScope API)
- **可视化**: Plotly (dark theme)
- **PDF 解析**: PyPDF2
