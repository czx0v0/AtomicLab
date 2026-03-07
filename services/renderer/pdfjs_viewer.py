"""
PDF.js Viewer Service
=====================
基于PDF.js的保真PDF渲染器，支持文本选择和高亮交互。

Features:
- 原生PDF保真渲染（公式、表格、图片完整显示）
- 文本层选择（支持高亮）
- 坐标映射（PDF位置 ↔ Chunk ID）
- 高亮数据持久化
"""

import os
import json
import base64
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import html


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


@dataclass
class HighlightData:
    """高亮数据"""

    highlight_id: str
    doc_id: str
    chunk_id: str
    content: str
    color: str = "yellow"
    annotation: str = ""
    coordinate: PDFCoordinate = None
    created_at: str = ""
    rects: list = None  # 支持多个rect（跨行选择）

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
            "rects": self.rects,  # 多rect支持
        }


class PDFJSViewer:
    """PDF.js查看器 - 使用iframe嵌入完整HTML"""

    PDFJS_VERSION = "3.11.174"

    HIGHLIGHT_COLORS = {
        "yellow": "rgba(255, 235, 59, 0.4)",
        "green": "rgba(76, 175, 80, 0.4)",
        "blue": "rgba(33, 150, 243, 0.4)",
        "pink": "rgba(233, 30, 99, 0.4)",
        "orange": "rgba(255, 152, 0, 0.4)",
    }

    def render_viewer(
        self,
        pdf_path: str,
        doc_id: str,
        highlights: List[HighlightData] = None,
        doc_name: str = "",
    ) -> str:
        """生成PDF.js查看器HTML"""
        # 读取PDF为base64
        try:
            with open(pdf_path, "rb") as f:
                pdf_base64 = base64.b64encode(f.read()).decode("ascii")
        except Exception as e:
            return f"<div class='txt-empty'>PDF读取失败: {str(e)[:50]}</div>"

        file_size_mb = len(pdf_base64) * 3 / 4 / (1024 * 1024)
        if file_size_mb > 30:
            return f"<div class='txt-empty'>PDF过大 ({file_size_mb:.1f}MB)，建议使用文本模式</div>"

        highlights_json = json.dumps([h.to_dict() for h in (highlights or [])])

        return self._generate_iframe_html(
            pdf_base64, doc_id, doc_name, file_size_mb, highlights_json
        )

    def _generate_iframe_html(
        self,
        pdf_base64: str,
        doc_id: str,
        doc_name: str,
        file_size_mb: float,
        highlights_json: str,
    ) -> str:
        """生成包含iframe的HTML，iframe内嵌完整PDF.js viewer"""

        # 生成内部HTML文档
        inner_html = self._generate_inner_html(
            pdf_base64, doc_id, doc_name, file_size_mb, highlights_json
        )

        # 转义HTML用于srcdoc属性
        escaped_html = html.escape(inner_html, quote=True)

        return f"""<div style="border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">
    <div style="background: #f7fafc; padding: 8px 12px; border-bottom: 1px solid #e2e8f0;">
        <span style="font-weight: 500; color: #2d3748;">{html.escape(doc_name)}</span>
        <span style="color: #718096; font-size: 12px;"> ({file_size_mb:.1f} MB)</span>
    </div>
    <iframe 
        srcdoc="{escaped_html}"
        style="width: 100%; height: 750px; border: none;"
        allow="fullscreen"
    ></iframe>
</div>"""

    def _generate_inner_html(
        self,
        pdf_base64: str,
        doc_id: str,
        doc_name: str,
        file_size_mb: float,
        highlights_json: str,
    ) -> str:
        """生成PDF.js viewer的完整HTML文档"""

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/{self.PDFJS_VERSION}/pdf.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ background: #525659; font-family: system-ui, sans-serif; }}
        
        .toolbar {{
            background: #edf2f7;
            padding: 8px 12px;
            border-bottom: 1px solid #e2e8f0;
            display: flex;
            gap: 8px;
            align-items: center;
            flex-wrap: wrap;
        }}
        
        .btn {{
            padding: 6px 12px;
            border: 1px solid #cbd5e0;
            border-radius: 4px;
            background: white;
            cursor: pointer;
            font-size: 12px;
        }}
        .btn:hover {{ background: #e2e8f0; }}
        .btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
        
        .page-info {{ font-size: 13px; color: #4a5568; min-width: 80px; text-align: center; }}
        
        .color-picker {{ display: flex; gap: 4px; margin-left: 8px; }}
        .color-btn {{
            width: 20px; height: 20px;
            border-radius: 4px;
            border: 2px solid transparent;
            cursor: pointer;
        }}
        .color-btn.selected {{ border-color: #2d3748; }}
        
        .container {{
            display: flex;
            justify-content: center;
            padding: 20px;
            min-height: calc(100vh - 50px);
        }}
        
        .page-wrapper {{
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            position: relative;
        }}
        
        .text-layer {{
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            overflow: hidden;
            opacity: 0.2;
            line-height: 1.0;
        }}
        .text-layer span {{
            color: transparent;
            position: absolute;
            white-space: pre;
            pointer-events: all;
        }}
        .text-layer ::selection {{ background: rgba(0, 0, 255, 0.3); }}
        
        .highlight-layer {{
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            pointer-events: none;
        }}
        .highlight {{
            position: absolute;
            pointer-events: auto;
            cursor: pointer;
        }}
        .highlight.yellow {{ background: {self.HIGHLIGHT_COLORS['yellow']}; }}
        .highlight.green {{ background: {self.HIGHLIGHT_COLORS['green']}; }}
        .highlight.blue {{ background: {self.HIGHLIGHT_COLORS['blue']}; }}
        .highlight.pink {{ background: {self.HIGHLIGHT_COLORS['pink']}; }}
        
        .loading {{ text-align: center; padding: 40px; color: #a0aec0; }}
        .error {{ color: #e53e3e; }}
        
        .screenshot-overlay {{
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.3);
            cursor: crosshair;
            z-index: 9999;
        }}
        .screenshot-hint {{
            position: fixed;
            top: 20px; left: 50%;
            transform: translateX(-50%);
            background: #2d3748;
            color: white;
            padding: 10px 20px;
            border-radius: 6px;
            font-size: 14px;
            z-index: 10000;
        }}
    </style>
</head>
<body>
    <div class="toolbar">
        <button class="btn" id="prevBtn" disabled>◀ 上一页</button>
        <span class="page-info" id="pageInfo">1 / ?</span>
        <button class="btn" id="nextBtn" disabled>下一页 ▶</button>
        
        <div style="flex: 1;"></div>
        
        <span style="font-size: 12px; color: #4a5568;">颜色:</span>
        <div class="color-picker">
            <div class="color-btn selected" data-color="yellow" style="background:{self.HIGHLIGHT_COLORS['yellow']}"></div>
            <div class="color-btn" data-color="green" style="background:{self.HIGHLIGHT_COLORS['green']}"></div>
            <div class="color-btn" data-color="blue" style="background:{self.HIGHLIGHT_COLORS['blue']}"></div>
            <div class="color-btn" data-color="pink" style="background:{self.HIGHLIGHT_COLORS['pink']}"></div>
        </div>
        
        <button class="btn" id="highlightBtn">✏️ 添加高亮</button>
        <button class="btn" id="screenshotBtn">📷 截图笔记</button>
    </div>
    
    <div class="container" id="container">
        <div class="loading">正在加载PDF...</div>
    </div>

    <script>
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/{self.PDFJS_VERSION}/pdf.worker.min.js';
        
        const state = {{
            docId: '{doc_id}',
            pdf: null,
            page: 1,
            total: 0,
            scale: 1.5,
            color: 'yellow',
            highlights: {highlights_json},
            selectedText: '',
            selectedRects: []
        }};
        
        const container = document.getElementById('container');
        const prevBtn = document.getElementById('prevBtn');
        const nextBtn = document.getElementById('nextBtn');
        const pageInfo = document.getElementById('pageInfo');
        
        async function init() {{
            try {{
                const pdfData = atob('{pdf_base64}');
                state.pdf = await pdfjsLib.getDocument({{ data: pdfData }}).promise;
                state.total = state.pdf.numPages;
                updateUI();
                await renderPage(state.page);
            }} catch (e) {{
                container.innerHTML = '<div class="loading error">加载失败: ' + e.message + '</div>';
            }}
        }}
        
        async function renderPage(num) {{
            container.innerHTML = '<div class="loading">正在渲染...</div>';
            
            const page = await state.pdf.getPage(num);
            const viewport = page.getViewport({{ scale: state.scale }});
            
            // Canvas
            const canvas = document.createElement('canvas');
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            const ctx = canvas.getContext('2d');
            await page.render({{ canvasContext: ctx, viewport: viewport }}).promise;
            
            // Wrapper
            const wrapper = document.createElement('div');
            wrapper.className = 'page-wrapper';
            wrapper.style.width = viewport.width + 'px';
            wrapper.style.height = viewport.height + 'px';
            wrapper.appendChild(canvas);
            
            // Text layer
            const textLayer = document.createElement('div');
            textLayer.className = 'text-layer';
            wrapper.appendChild(textLayer);
            
            // Highlight layer
            const hlLayer = document.createElement('div');
            hlLayer.className = 'highlight-layer';
            hlLayer.id = 'hl-' + num;
            wrapper.appendChild(hlLayer);
            
            container.innerHTML = '';
            container.appendChild(wrapper);
            
            // Render text
            const textContent = await page.getTextContent();
            textContent.items.forEach(item => {{
                const span = document.createElement('span');
                span.textContent = item.str;
                const tx = pdfjsLib.Util.transform(viewport.transform, item.transform);
                const fs = Math.sqrt(tx[0]*tx[0] + tx[1]*tx[1]);
                span.style.cssText = `left:${{tx[4]}}px;top:${{tx[5]-fs}}px;font-size:${{fs}}px;font-family:${{item.fontName||'sans-serif'}}`;
                textLayer.appendChild(span);
            }});
            
            // Render highlights
            renderHighlights(num, viewport);
            
            // Text selection
            textLayer.addEventListener('mouseup', () => {{
                const sel = window.getSelection();
                if (sel && !sel.isCollapsed) {{
                    state.selectedText = sel.toString();
                    const range = sel.getRangeAt(0);
                    const rects = range.getClientRects();
                    const wrapperRect = wrapper.getBoundingClientRect();
                    state.selectedRects = [];
                    for (let i = 0; i < rects.length; i++) {{
                        state.selectedRects.push({{
                            x: rects[i].left - wrapperRect.left,
                            y: rects[i].top - wrapperRect.top,
                            w: rects[i].width,
                            h: rects[i].height
                        }});
                    }}
                }}
            }});
        }}
        
        function renderHighlights(pageNum, viewport) {{
            const layer = document.getElementById('hl-' + pageNum);
            if (!layer) return;
            layer.innerHTML = '';
            
            state.highlights.filter(h => !h.coordinate || h.coordinate.page === pageNum).forEach(h => {{
                if (!h.coordinate) return;
                
                // 支持多个rect（跨行选择）
                if (h.rects && h.rects.length > 0) {{
                    h.rects.forEach(r => {{
                        const div = document.createElement('div');
                        div.className = 'highlight ' + h.color;
                        div.style.cssText = `left:${{r.x}}px;top:${{r.y}}px;width:${{r.w || r.width}}px;height:${{r.h || r.height}}px`;
                        div.title = h.annotation || h.content;
                        layer.appendChild(div);
                    }});
                }} else {{
                    // 单rect兼容
                    const div = document.createElement('div');
                    div.className = 'highlight ' + h.color;
                    div.style.cssText = `left:${{h.coordinate.x}}px;top:${{h.coordinate.y}}px;width:${{h.coordinate.width}}px;height:${{h.coordinate.height}}px`;
                    div.title = h.annotation || h.content;
                    layer.appendChild(div);
                }}
            }});
        }}
        
        function addHighlight() {{
            if (!state.selectedText) {{
                alert('请先选择要高亮的文本');
                return;
            }}
            
            // 支持跨行选择：保存所有rect
            const hl = {{
                id: 'HL-' + Date.now(),
                doc_id: state.docId,
                chunk_id: '',
                content: state.selectedText,
                color: state.color,
                annotation: '',
                coordinate: {{
                    page: state.page,
                    x: state.selectedRects[0]?.x || 0,
                    y: state.selectedRects[0]?.y || 0,
                    width: state.selectedRects[0]?.w || 100,
                    height: state.selectedRects[0]?.h || 20
                }},
                rects: state.selectedRects,  // 保存所有rect支持跨行
                created_at: new Date().toISOString()
            }};
            
            state.highlights.push(hl);
            renderHighlights(state.page);
            
            // 通知父页面保存到知识图谱
            if (window.parent) {{
                window.parent.postMessage({{ type: 'highlight', data: hl }}, '*');
            }}
            
            window.getSelection().removeAllRanges();
            state.selectedText = '';
            state.selectedRects = [];
        }}
        
        // ═══════════════════════════════════════════════════════════════
        // 截图笔记功能
        // ═══════════════════════════════════════════════════════════════
        let screenshotMode = false;
        let screenshotStart = null;
        let screenshotOverlay = null;
        
        function startScreenshot() {{
            screenshotMode = true;
            screenshotStart = null;
            
            // 创建遮罩层
            screenshotOverlay = document.createElement('div');
            screenshotOverlay.className = 'screenshot-overlay';
            screenshotOverlay.innerHTML = '<div class="screenshot-hint">拖动鼠标选择截图区域，按ESC取消</div>';
            document.body.appendChild(screenshotOverlay);
            
            screenshotOverlay.addEventListener('mousedown', onScreenshotMouseDown);
            screenshotOverlay.addEventListener('mousemove', onScreenshotMouseMove);
            screenshotOverlay.addEventListener('mouseup', onScreenshotMouseUp);
            
            // ESC取消
            document.addEventListener('keydown', cancelScreenshot);
        }}
        
        function cancelScreenshot(e) {{
            if (e && e.key !== 'Escape') return;
            screenshotMode = false;
            if (screenshotOverlay) {{
                screenshotOverlay.remove();
                screenshotOverlay = null;
            }}
            document.removeEventListener('keydown', cancelScreenshot);
        }}
        
        function onScreenshotMouseDown(e) {{
            screenshotStart = {{ x: e.clientX, y: e.clientY }};
        }}
        
        function onScreenshotMouseMove(e) {{
            if (!screenshotStart) return;
            // 可以添加选区预览
        }}
        
        function onScreenshotMouseUp(e) {{
            if (!screenshotStart) return;
            
            const end = {{ x: e.clientX, y: e.clientY }};
            const rect = {{
                x: Math.min(screenshotStart.x, end.x),
                y: Math.min(screenshotStart.y, end.y),
                w: Math.abs(end.x - screenshotStart.x),
                h: Math.abs(end.y - screenshotStart.y)
            }};
            
            // 最小尺寸检查
            if (rect.w < 20 || rect.h < 20) {{
                cancelScreenshot();
                return;
            }}
            
            // 获取当前页面的canvas
            const canvas = container.querySelector('canvas');
            if (!canvas) {{
                cancelScreenshot();
                return;
            }}
            
            // 计算相对于canvas的坐标
            const canvasRect = canvas.getBoundingClientRect();
            const cropX = rect.x - canvasRect.left;
            const cropY = rect.y - canvasRect.top;
            
            // 创建裁剪canvas
            const cropCanvas = document.createElement('canvas');
            cropCanvas.width = rect.w;
            cropCanvas.height = rect.h;
            const ctx = cropCanvas.getContext('2d');
            
            // 从原canvas裁剪
            ctx.drawImage(canvas, cropX, cropY, rect.w, rect.h, 0, 0, rect.w, rect.h);
            
            // 转为base64
            const imageData = cropCanvas.toDataURL('image/png');
            
            // 通知父页面保存截图笔记
            if (window.parent) {{
                window.parent.postMessage({{ 
                    type: 'screenshot', 
                    data: {{
                        image: imageData,
                        page: state.page,
                        doc_id: state.docId,
                        annotation: '',
                        rect: rect
                    }}
                }}, '*');
            }}
            
            cancelScreenshot();
        }}
        
        function updateUI() {{
            pageInfo.textContent = state.page + ' / ' + state.total;
            prevBtn.disabled = state.page <= 1;
            nextBtn.disabled = state.page >= state.total;
        }}
        
        prevBtn.onclick = () => {{ if (state.page > 1) {{ state.page--; updateUI(); renderPage(state.page); }} }};
        nextBtn.onclick = () => {{ if (state.page < state.total) {{ state.page++; updateUI(); renderPage(state.page); }} }};
        document.getElementById('highlightBtn').onclick = addHighlight;
        document.getElementById('screenshotBtn').onclick = startScreenshot;
        
        document.querySelectorAll('.color-btn').forEach(btn => {{
            btn.onclick = () => {{
                document.querySelectorAll('.color-btn').forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
                state.color = btn.dataset.color;
            }};
        }});
        
        init();
    </script>
</body>
</html>"""
