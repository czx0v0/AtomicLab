"""
PDF.js Viewer Service
=====================
基于PDF.js的保真PDF渲染器，支持文本选择和高亮交互。

Features:
- 原生PDF保真渲染（公式、表格、图片完整显示）
- 文本层选择（支持高亮）
- 坐标映射（PDF位置 ↔ Chunk ID）
- 高亮数据持久化

Architecture:
    PDF.js Canvas    ←──保真渲染──←  原始PDF文件
         ↓
    Text Layer       ←──文本选择──←  用户交互
         ↓
    Highlight Layer  ←──高亮叠加──←  后端存储的高亮数据
         ↓
    Coordinate Map   ←──位置映射──←  Docling解析的chunks

与Docling的集成：
- Docling负责高级解析和RAG分块
- 解析结果包含每个chunk的页面位置(bounding box)
- 用户选择文本时，通过坐标映射找到对应的chunk
- 高亮数据存储时，记录chunk_id和页面坐标
"""

import os
import json
import base64
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PDFCoordinate:
    """PDF页面坐标"""
    page: int
    x: float
    y: float
    width: float
    height: float
    
    def to_dict(self) -> dict:
        return {
            "page": self.page,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "PDFCoordinate":
        return cls(
            page=data.get("page", 1),
            x=data.get("x", 0),
            y=data.get("y", 0),
            width=data.get("width", 0),
            height=data.get("height", 0),
        )


@dataclass
class HighlightData:
    """高亮数据"""
    highlight_id: str
    doc_id: str
    chunk_id: str
    content: str  # 高亮的文本内容
    color: str = "yellow"  # yellow, green, blue, pink
    annotation: str = ""  # 用户批注
    coordinate: PDFCoordinate = None
    created_at: str = ""
    
    def to_dict(self) -> dict:
        return {
            "id": self.highlight_id,
            "doc_id": self.doc_id,
            "chunk_id": self.chunk_id,
            "content": self.content,
            "color": self.color,
            "annotation": self.annotation,
            "coordinate": self.coordinate.to_dict() if self.coordinate else None,
            "created_at": self.created_at,
        }


@dataclass
class ChunkCoordinateMap:
    """Chunk到PDF坐标的映射"""
    chunk_id: str
    doc_id: str
    page: int
    bbox: Tuple[float, float, float, float]  # (x, y, width, height)
    text_start: int = 0  # 在页面文本中的起始位置
    text_end: int = 0    # 在页面文本中的结束位置
    
    def contains_point(self, x: float, y: float) -> bool:
        """检查点是否在chunk区域内"""
        bx, by, bw, bh = self.bbox
        return bx <= x <= bx + bw and by <= y <= by + bh


class PDFJSViewer:
    """
    PDF.js查看器
    
    生成包含PDF.js的HTML，支持：
    1. 保真渲染PDF
    2. 文本层选择
    3. 高亮叠加
    4. 与后端交互（高亮数据持久化）
    """
    
    # PDF.js CDN版本
    PDFJS_VERSION = "3.11.174"
    
    # 高亮颜色映射
    HIGHLIGHT_COLORS = {
        "yellow": "rgba(255, 235, 59, 0.4)",
        "green": "rgba(76, 175, 80, 0.4)",
        "blue": "rgba(33, 150, 243, 0.4)",
        "pink": "rgba(233, 30, 99, 0.4)",
        "orange": "rgba(255, 152, 0, 0.4)",
    }
    
    def __init__(self):
        self.chunk_maps: Dict[str, List[ChunkCoordinateMap]] = {}
    
    def register_chunk_maps(self, doc_id: str, chunks: List[Any]):
        """
        注册chunk坐标映射
        
        Args:
            doc_id: 文档ID
            chunks: TextChunk列表（来自Docling解析）
        """
        maps = []
        for chunk in chunks:
            if hasattr(chunk, 'page_number') and chunk.page_number:
                # 从chunk的bbox信息创建映射
                bbox = getattr(chunk, 'bbox', (0, 0, 100, 20))
                if hasattr(chunk, 'metadata') and chunk.metadata:
                    bbox = getattr(chunk.metadata, 'bbox', bbox)
                
                maps.append(ChunkCoordinateMap(
                    chunk_id=chunk.chunk_id,
                    doc_id=doc_id,
                    page=chunk.page_number,
                    bbox=bbox if isinstance(bbox, tuple) else (0, 0, 100, 20),
                ))
        
        self.chunk_maps[doc_id] = maps
    
    def find_chunk_by_coordinate(self, doc_id: str, page: int, x: float, y: float) -> Optional[str]:
        """
        根据PDF坐标找到对应的chunk_id
        
        Args:
            doc_id: 文档ID
            page: 页码
            x, y: PDF坐标
            
        Returns:
            chunk_id 或 None
        """
        if doc_id not in self.chunk_maps:
            return None
        
        for cmap in self.chunk_maps[doc_id]:
            if cmap.page == page and cmap.contains_point(x, y):
                return cmap.chunk_id
        
        return None
    
    def render_viewer(
        self,
        pdf_path: str,
        doc_id: str,
        highlights: List[HighlightData] = None,
        doc_name: str = "",
    ) -> str:
        """
        生成PDF.js查看器HTML
        
        Args:
            pdf_path: PDF文件路径
            doc_id: 文档ID
            highlights: 已有高亮数据
            doc_name: 文档名称
            
        Returns:
            HTML字符串
        """
        # 读取PDF为base64
        try:
            with open(pdf_path, "rb") as f:
                pdf_base64 = base64.b64encode(f.read()).decode("ascii")
        except Exception as e:
            return f"<div class='txt-empty'>PDF读取失败: {str(e)[:50]}</div>"
        
        # 检查文件大小
        file_size_mb = len(pdf_base64) * 3 / 4 / (1024 * 1024)
        if file_size_mb > 30:
            return f"<div class='txt-empty'>PDF过大 ({file_size_mb:.1f}MB)，建议使用文本模式</div>"
        
        # 序列化高亮数据
        highlights_json = json.dumps([h.to_dict() for h in (highlights or [])])
        
        return self._generate_html(
            pdf_base64=pdf_base64,
            doc_id=doc_id,
            doc_name=doc_name or os.path.basename(pdf_path),
            file_size_mb=file_size_mb,
            highlights_json=highlights_json,
        )
    
    def _generate_html(
        self,
        pdf_base64: str,
        doc_id: str,
        doc_name: str,
        file_size_mb: float,
        highlights_json: str,
    ) -> str:
        """生成完整的HTML"""
        
        return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{doc_name}</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/{self.PDFJS_VERSION}/pdf.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        .pdf-container {{
            width: 100%;
            background: #525659;
            padding: 20px;
            min-height: 600px;
            max-height: 800px;
            overflow-y: auto;
            border-radius: 8px;
        }}
        
        .pdf-header {{
            background: #f7fafc;
            padding: 12px 16px;
            border-radius: 8px 8px 0 0;
            border-bottom: 1px solid #e2e8f0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .pdf-title {{
            font-size: 14px;
            color: #2d3748;
            font-weight: 500;
        }}
        
        .pdf-info {{
            font-size: 12px;
            color: #718096;
        }}
        
        .toolbar {{
            display: flex;
            gap: 8px;
            align-items: center;
            padding: 8px 12px;
            background: #edf2f7;
            border-bottom: 1px solid #e2e8f0;
        }}
        
        .toolbar-btn {{
            padding: 6px 12px;
            border: 1px solid #cbd5e0;
            border-radius: 4px;
            background: white;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
        }}
        
        .toolbar-btn:hover {{
            background: #e2e8f0;
        }}
        
        .toolbar-btn.active {{
            background: #3182ce;
            color: white;
            border-color: #3182ce;
        }}
        
        .color-picker {{
            display: flex;
            gap: 4px;
            margin-left: 12px;
        }}
        
        .color-btn {{
            width: 24px;
            height: 24px;
            border-radius: 4px;
            border: 2px solid transparent;
            cursor: pointer;
        }}
        
        .color-btn.selected {{
            border-color: #2d3748;
        }}
        
        .page-container {{
            margin: 20px auto;
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            position: relative;
        }}
        
        .text-layer {{
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            overflow: hidden;
            opacity: 0.2;
            line-height: 1.0;
        }}
        
        .text-layer > span {{
            color: transparent;
            position: absolute;
            white-space: pre;
            pointer-events: all;
        }}
        
        .text-layer ::selection {{
            background: rgba(0, 0, 255, 0.3);
        }}
        
        .highlight-layer {{
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            pointer-events: none;
        }}
        
        .highlight {{
            position: absolute;
            pointer-events: auto;
            cursor: pointer;
            transition: opacity 0.2s;
        }}
        
        .highlight:hover {{
            opacity: 0.8;
        }}
        
        .highlight.yellow {{ background: {self.HIGHLIGHT_COLORS['yellow']}; }}
        .highlight.green {{ background: {self.HIGHLIGHT_COLORS['green']}; }}
        .highlight.blue {{ background: {self.HIGHLIGHT_COLORS['blue']}; }}
        .highlight.pink {{ background: {self.HIGHLIGHT_COLORS['pink']}; }}
        .highlight.orange {{ background: {self.HIGHLIGHT_COLORS['orange']}; }}
        
        .loading {{
            text-align: center;
            padding: 40px;
            color: #a0aec0;
        }}
        
        .page-nav {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 12px;
            padding: 12px;
            background: #edf2f7;
            border-top: 1px solid #e2e8f0;
        }}
        
        .page-num {{
            font-size: 13px;
            color: #4a5568;
        }}
    </style>
</head>
<body>
    <div class="pdf-header">
        <div>
            <span class="pdf-title">{doc_name}</span>
            <span class="pdf-info"> ({file_size_mb:.1f} MB)</span>
        </div>
        <span class="pdf-info">💡 选择文本后点击高亮按钮添加笔记</span>
    </div>
    
    <div class="toolbar">
        <button class="toolbar-btn" id="prevPage">◀ 上一页</button>
        <button class="toolbar-btn" id="nextPage">下一页 ▶</button>
        <span class="page-num" id="pageInfo">第 1 / ? 页</span>
        
        <div style="flex: 1;"></div>
        
        <span style="font-size: 12px; color: #4a5568;">高亮颜色:</span>
        <div class="color-picker">
            <div class="color-btn selected" data-color="yellow" style="background: {self.HIGHLIGHT_COLORS['yellow']};"></div>
            <div class="color-btn" data-color="green" style="background: {self.HIGHLIGHT_COLORS['green']};"></div>
            <div class="color-btn" data-color="blue" style="background: {self.HIGHLIGHT_COLORS['blue']};"></div>
            <div class="color-btn" data-color="pink" style="background: {self.HIGHLIGHT_COLORS['pink']};"></div>
        </div>
        
        <button class="toolbar-btn" id="addHighlight">✏️ 添加高亮</button>
        <button class="toolbar-btn" id="addAnnotation">📝 添加批注</button>
    </div>
    
    <div class="pdf-container" id="pdfContainer">
        <div class="loading">正在加载PDF...</div>
    </div>
    
    <script>
        // 配置PDF.js worker
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/{self.PDFJS_VERSION}/pdf.worker.min.js';
        
        // 全局状态
        const state = {{
            docId: '{doc_id}',
            pdfDoc: null,
            currentPage: 1,
            totalPages: 0,
            scale: 1.5,
            currentColor: 'yellow',
            highlights: {highlights_json},
            selectedText: '',
            selectedRects: [],
        }};
        
        // 加载PDF
        async function loadPDF() {{
            const container = document.getElementById('pdfContainer');
            container.innerHTML = '<div class="loading">正在加载PDF...</div>';
            
            try {{
                const pdfData = atob('{pdf_base64}');
                state.pdfDoc = await pdfjsLib.getDocument({{ data: pdfData }}).promise;
                state.totalPages = state.pdfDoc.numPages;
                
                updatePageInfo();
                await renderPage(state.currentPage);
            }} catch (error) {{
                container.innerHTML = '<div class="loading" style="color: #e53e3e;">PDF加载失败: ' + error.message + '</div>';
            }}
        }}
        
        // 渲染单页
        async function renderPage(pageNum) {{
            const container = document.getElementById('pdfContainer');
            container.innerHTML = '';
            
            const page = await state.pdfDoc.getPage(pageNum);
            const viewport = page.getViewport({{ scale: state.scale }});
            
            // 创建页面容器
            const pageContainer = document.createElement('div');
            pageContainer.className = 'page-container';
            pageContainer.style.width = viewport.width + 'px';
            pageContainer.style.height = viewport.height + 'px';
            pageContainer.id = 'page-' + pageNum;
            
            // Canvas层 - 渲染PDF
            const canvas = document.createElement('canvas');
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            const ctx = canvas.getContext('2d');
            
            await page.render({{ canvasContext: ctx, viewport: viewport }}).promise;
            pageContainer.appendChild(canvas);
            
            // 文本层 - 支持选择
            const textLayer = document.createElement('div');
            textLayer.className = 'text-layer';
            pageContainer.appendChild(textLayer);
            
            // 高亮层
            const highlightLayer = document.createElement('div');
            highlightLayer.className = 'highlight-layer';
            highlightLayer.id = 'highlight-layer-' + pageNum;
            pageContainer.appendChild(highlightLayer);
            
            container.appendChild(pageContainer);
            
            // 渲染文本层
            const textContent = await page.getTextContent();
            await renderTextLayer(textLayer, viewport, textContent);
            
            // 渲染已有高亮
            renderHighlights(pageNum, viewport);
            
            // 监听文本选择
            textLayer.addEventListener('mouseup', handleTextSelect);
        }}
        
        // 渲染文本层
        async function renderTextLayer(container, viewport, textContent) {{
            container.innerHTML = '';
            
            textContent.items.forEach(item => {{
                const span = document.createElement('span');
                span.textContent = item.str;
                
                const tx = pdfjsLib.Util.transform(viewport.transform, item.transform);
                const fontSize = Math.sqrt(tx[0] * tx[0] + tx[1] * tx[1]);
                
                span.style.left = tx[4] + 'px';
                span.style.top = (tx[5] - fontSize) + 'px';
                span.style.fontSize = fontSize + 'px';
                span.style.fontFamily = item.fontName || 'sans-serif';
                
                container.appendChild(span);
            }});
        }}
        
        // 渲染高亮
        function renderHighlights(pageNum, viewport) {{
            const layer = document.getElementById('highlight-layer-' + pageNum);
            if (!layer) return;
            
            layer.innerHTML = '';
            
            state.highlights
                .filter(h => !h.coordinate || h.coordinate.page === pageNum)
                .forEach(h => {{
                    if (!h.coordinate) return;
                    
                    const div = document.createElement('div');
                    div.className = 'highlight ' + h.color;
                    div.style.left = h.coordinate.x + 'px';
                    div.style.top = h.coordinate.y + 'px';
                    div.style.width = h.coordinate.width + 'px';
                    div.style.height = h.coordinate.height + 'px';
                    div.dataset.highlightId = h.id;
                    div.title = h.annotation || h.content;
                    
                    div.onclick = () => showHighlightDetail(h);
                    layer.appendChild(div);
                }});
        }}
        
        // 处理文本选择
        function handleTextSelect(e) {{
            const selection = window.getSelection();
            if (!selection || selection.isCollapsed) {{
                state.selectedText = '';
                state.selectedRects = [];
                return;
            }}
            
            state.selectedText = selection.toString();
            
            // 获取选择区域的矩形
            const range = selection.getRangeAt(0);
            const rects = range.getClientRects();
            
            state.selectedRects = [];
            for (let i = 0; i < rects.length; i++) {{
                const rect = rects[i];
                const pageContainer = document.querySelector('.page-container');
                const pageRect = pageContainer.getBoundingClientRect();
                
                state.selectedRects.push({{
                    x: rect.left - pageRect.left,
                    y: rect.top - pageRect.top,
                    width: rect.width,
                    height: rect.height,
                }});
            }}
        }}
        
        // 添加高亮
        function addHighlight() {{
            if (!state.selectedText) {{
                alert('请先选择要高亮的文本');
                return;
            }}
            
            const highlight = {{
                id: 'HL-' + Date.now(),
                doc_id: state.docId,
                chunk_id: '',  // 需要通过坐标映射获取
                content: state.selectedText,
                color: state.currentColor,
                annotation: '',
                coordinate: {{
                    page: state.currentPage,
                    x: state.selectedRects[0]?.x || 0,
                    y: state.selectedRects[0]?.y || 0,
                    width: state.selectedRects[0]?.width || 100,
                    height: state.selectedRects[0]?.height || 20,
                }},
                created_at: new Date().toISOString(),
            }};
            
            state.highlights.push(highlight);
            
            // 通知Gradio后端
            if (window.parent && window.parent.Gradio) {{
                window.parent.Gradio.setHighlight(JSON.stringify(highlight));
            }}
            
            // 通过隐藏input传递数据
            const input = document.createElement('input');
            input.type = 'hidden';
            input.id = 'highlight-data';
            input.value = JSON.stringify(highlight);
            document.body.appendChild(input);
            
            // 触发事件
            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
            
            // 重新渲染高亮
            renderHighlights(state.currentPage);
            
            // 清除选择
            window.getSelection().removeAllRanges();
            state.selectedText = '';
            state.selectedRects = [];
        }}
        
        // 显示高亮详情
        function showHighlightDetail(highlight) {{
            const annotation = prompt('编辑批注:', highlight.annotation || '');
            if (annotation !== null) {{
                highlight.annotation = annotation;
                // 更新后端
                // TODO: 调用Gradio更新接口
            }}
        }}
        
        // 更新页面信息
        function updatePageInfo() {{
            document.getElementById('pageInfo').textContent = 
                `第 ${{state.currentPage}} / ${{state.totalPages}} 页`;
        }}
        
        // 事件绑定
        document.getElementById('prevPage').onclick = () => {{
            if (state.currentPage > 1) {{
                state.currentPage--;
                updatePageInfo();
                renderPage(state.currentPage);
            }}
        }};
        
        document.getElementById('nextPage').onclick = () => {{
            if (state.currentPage < state.totalPages) {{
                state.currentPage++;
                updatePageInfo();
                renderPage(state.currentPage);
            }}
        }};
        
        document.getElementById('addHighlight').onclick = addHighlight;
        
        document.getElementById('addAnnotation').onclick = () => {{
            if (!state.selectedText) {{
                alert('请先选择要批注的文本');
                return;
            }}
            const annotation = prompt('输入批注内容:');
            if (annotation) {{
                state.currentColor = 'blue';  // 批注默认蓝色
                addHighlight();
                // 设置批注
                state.highlights[state.highlights.length - 1].annotation = annotation;
            }}
        }};
        
        // 颜色选择
        document.querySelectorAll('.color-btn').forEach(btn => {{
            btn.onclick = () => {{
                document.querySelectorAll('.color-btn').forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
                state.currentColor = btn.dataset.color;
            }};
        }});
        
        // 启动
        loadPDF();
    </script>
</body>
</html>'''
