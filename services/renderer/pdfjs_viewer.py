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
        "yellow": "rgba(255, 235, 59, 0.25)",
        "green": "rgba(76, 175, 80, 0.25)",
        "blue": "rgba(33, 150, 243, 0.25)",
        "pink": "rgba(233, 30, 99, 0.25)",
        "orange": "rgba(255, 152, 0, 0.25)",
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
        """生成PDF.js viewer的完整HTML文档 - v2.4版：缩放控制+工具栏固定+视觉反馈"""

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/{self.PDFJS_VERSION}/pdf.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ background: #525659; font-family: system-ui, sans-serif; }}
        
        /* 顶部工具栏 - 固定定位 */
        .toolbar {{
            position: sticky;
            top: 0;
            z-index: 100;
            background: #edf2f7;
            padding: 8px 12px;
            border-bottom: 1px solid #e2e8f0;
            display: flex;
            gap: 8px;
            align-items: center;
            flex-wrap: wrap;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .btn {{
            padding: 6px 12px;
            border: 1px solid #cbd5e0;
            border-radius: 4px;
            background: white;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
        }}
        .btn:hover {{ background: #e2e8f0; }}
        .btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
        .btn.active {{ background: #3182ce; color: white; border-color: #3182ce; }}
        
        .page-info {{ font-size: 13px; color: #4a5568; min-width: 80px; text-align: center; }}
        
        /* 缩放控制 */
        .zoom-control {{
            display: flex;
            align-items: center;
            gap: 4px;
            background: white;
            border: 1px solid #cbd5e0;
            border-radius: 4px;
            padding: 2px;
        }}
        .zoom-btn {{
            width: 28px;
            height: 24px;
            border: none;
            background: transparent;
            cursor: pointer;
            font-size: 14px;
            color: #4a5568;
            border-radius: 2px;
        }}
        .zoom-btn:hover {{ background: #e2e8f0; }}
        .zoom-value {{
            min-width: 50px;
            text-align: center;
            font-size: 12px;
            color: #2d3748;
            font-weight: 500;
        }}
        
        /* 模式切换按钮 */
        .mode-toggle {{
            display: flex;
            gap: 2px;
            background: #e2e8f0;
            padding: 2px;
            border-radius: 6px;
        }}
        .mode-btn {{
            padding: 6px 14px;
            border: none;
            border-radius: 4px;
            background: transparent;
            cursor: pointer;
            font-size: 12px;
            color: #4a5568;
            transition: all 0.2s;
        }}
        .mode-btn:hover {{ background: rgba(255,255,255,0.5); }}
        .mode-btn.active {{ background: white; color: #2d3748; font-weight: 500; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        
        /* PDF容器 */
        .container {{
            display: flex;
            justify-content: center;
            padding: 20px;
            padding-top: 10px;
            min-height: calc(100vh - 60px);
        }}
        .page-wrapper {{
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            position: relative;
        }}
        
        /* 文本层 */
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
        .text-layer ::selection {{ background: rgba(66, 153, 225, 0.5); }}
        
        /* 选中状态视觉反馈 - 保持到用户操作 */
        .text-layer .keep-selection {{
            background: rgba(66, 153, 225, 0.3);
        }}
        
        /* 高亮层 */
        .highlight-layer {{
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            pointer-events: none;
        }}
        .highlight {{
            position: absolute;
            pointer-events: auto;
            cursor: pointer;
            transition: opacity 0.2s;
        }}
        .highlight:hover {{ opacity: 0.7; }}
        .highlight.yellow {{ background: {self.HIGHLIGHT_COLORS['yellow']}; }}
        .highlight.green {{ background: {self.HIGHLIGHT_COLORS['green']}; }}
        .highlight.blue {{ background: {self.HIGHLIGHT_COLORS['blue']}; }}
        .highlight.pink {{ background: {self.HIGHLIGHT_COLORS['pink']}; }}
        
        /* 浮动工具框 */
        .popup-toolbar {{
            position: fixed;
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.25);
            padding: 10px;
            z-index: 1000;
            display: none;
            min-width: 200px;
        }}
        .popup-toolbar.show {{ display: block; animation: popIn 0.15s ease-out; }}
        @keyframes popIn {{
            from {{ opacity: 0; transform: translateY(5px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .popup-colors {{
            display: flex;
            gap: 6px;
            margin-bottom: 8px;
        }}
        .popup-color-btn {{
            width: 24px; height: 24px;
            border-radius: 50%;
            border: 2px solid transparent;
            cursor: pointer;
            transition: transform 0.15s, border-color 0.15s;
        }}
        .popup-color-btn:hover {{ transform: scale(1.15); }}
        .popup-color-btn.selected {{ border-color: #2d3748; transform: scale(1.1); }}
        
        .popup-annotation {{
            width: 100%;
            padding: 6px 10px;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            font-size: 12px;
            margin-bottom: 8px;
        }}
        .popup-annotation:focus {{ outline: none; border-color: #3182ce; }}
        
        .popup-actions {{
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
        }}
        .popup-action-btn {{
            padding: 5px 10px;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            background: #f7fafc;
            cursor: pointer;
            font-size: 11px;
            color: #4a5568;
        }}
        .popup-action-btn:hover {{ background: #edf2f7; }}
        .popup-action-btn.primary {{ background: #3182ce; color: white; border-color: #3182ce; }}
        .popup-action-btn.primary:hover {{ background: #2c5282; }}
        
        /* 截图遮罩 */
        .screenshot-overlay {{
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.2);
            cursor: crosshair;
            z-index: 999;
        }}
        .screenshot-selection {{
            position: absolute;
            border: 2px dashed #3182ce;
            background: rgba(66, 153, 225, 0.1);
            pointer-events: none;
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
            z-index: 1001;
        }}
        
        .loading {{ text-align: center; padding: 40px; color: #a0aec0; }}
        .error {{ color: #e53e3e; }}
        
        /* 翻译结果 */
        .translate-result {{
            margin-top: 8px;
            padding: 8px;
            background: #f0f9ff;
            border-radius: 4px;
            font-size: 12px;
            color: #2c5282;
            display: none;
        }}
        .translate-result.show {{ display: block; }}
        
        /* OCR按钮 */
        .ocr-section {{
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid #e2e8f0;
            display: none;
        }}
        .ocr-section.show {{ display: block; }}
        .ocr-result {{
            font-size: 12px;
            color: #2d3748;
            background: #f7fafc;
            padding: 6px;
            border-radius: 4px;
            margin-top: 6px;
            max-height: 80px;
            overflow-y: auto;
        }}
    </style>
</head>
<body>
    <div class="toolbar">
        <button class="btn" id="prevBtn" disabled>◀ 上一页</button>
        <span class="page-info" id="pageInfo">1 / ?</span>
        <button class="btn" id="nextBtn" disabled>下一页 ▶</button>
        
        <!-- 缩放控制 -->
        <div class="zoom-control">
            <button class="zoom-btn" id="zoomOut" title="缩小">−</button>
            <span class="zoom-value" id="zoomValue">100%</span>
            <button class="zoom-btn" id="zoomIn" title="放大">+</button>
            <button class="zoom-btn" id="zoomReset" title="重置">⟲</button>
        </div>
        
        <div style="flex: 1;"></div>
        
        <!-- 双模式切换 -->
        <div class="mode-toggle">
            <button class="mode-btn active" id="highlightMode" title="选择文字高亮">✏️ 高亮</button>
            <button class="mode-btn" id="screenshotMode" title="框选截图">📷 截图</button>
        </div>
    </div>
    
    <div class="container" id="container">
        <div class="loading">正在加载PDF...</div>
    </div>
    
    <!-- 浮动工具框 -->
    <div class="popup-toolbar" id="popupToolbar">
        <div class="popup-colors">
            <div class="popup-color-btn selected" data-color="yellow" style="background:#fbd38d" title="黄色"></div>
            <div class="popup-color-btn" data-color="green" style="background:#9ae6b4" title="绿色"></div>
            <div class="popup-color-btn" data-color="blue" style="background:#90cdf4" title="蓝色"></div>
            <div class="popup-color-btn" data-color="pink" style="background:#fbb6ce" title="粉色"></div>
        </div>
        <input type="text" class="popup-annotation" id="popupAnnotation" placeholder="添加批注（可选）..." />
        <div class="translate-result" id="translateResult"></div>
        <div class="ocr-section" id="ocrSection">
            <button class="popup-action-btn" id="ocrBtn">🔍 OCR识别文字</button>
            <div class="ocr-result" id="ocrResult" style="display:none"></div>
        </div>
        <div class="popup-actions">
            <button class="popup-action-btn" id="popupTranslate">翻译</button>
            <button class="popup-action-btn primary" id="popupSave">保存笔记</button>
        </div>
    </div>

    <script>
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/{self.PDFJS_VERSION}/pdf.worker.min.js';
        
        // 全局状态
        const state = {{
            docId: '{doc_id}',
            pdf: null,
            page: 1,
            total: 0,
            scale: 1.0,  // 默认100%缩放
            baseScale: 1.0,  // PDF基础缩放
            color: 'yellow',
            highlights: {highlights_json},
            // 高亮模式状态
            selectedText: '',
            selectedRects: [],
            selectedRange: null,  // 保存选区用于视觉反馈
            // 截图模式状态
            isScreenshotMode: false,
            screenshotStart: null,
            screenshotImageData: null,
        }};
        
        const container = document.getElementById('container');
        const prevBtn = document.getElementById('prevBtn');
        const nextBtn = document.getElementById('nextBtn');
        const pageInfo = document.getElementById('pageInfo');
        const popupToolbar = document.getElementById('popupToolbar');
        const highlightModeBtn = document.getElementById('highlightMode');
        const screenshotModeBtn = document.getElementById('screenshotMode');
        const zoomIn = document.getElementById('zoomIn');
        const zoomOut = document.getElementById('zoomOut');
        const zoomReset = document.getElementById('zoomReset');
        const zoomValue = document.getElementById('zoomValue');
        
        // ═══════════════════════════════════════════════════════════════
        // PDF初始化和渲染
        // ═══════════════════════════════════════════════════════════════
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
            hidePopup();
            
            const page = await state.pdf.getPage(num);
            const viewport = page.getViewport({{ scale: state.scale * state.baseScale }});
            
            // Canvas渲染
            const canvas = document.createElement('canvas');
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            const ctx = canvas.getContext('2d');
            await page.render({{ canvasContext: ctx, viewport: viewport }}).promise;
            
            // 页面包装器
            const wrapper = document.createElement('div');
            wrapper.className = 'page-wrapper';
            wrapper.style.width = viewport.width + 'px';
            wrapper.style.height = viewport.height + 'px';
            wrapper.appendChild(canvas);
            
            // 文本层
            const textLayer = document.createElement('div');
            textLayer.className = 'text-layer';
            wrapper.appendChild(textLayer);
            
            // 高亮层
            const hlLayer = document.createElement('div');
            hlLayer.className = 'highlight-layer';
            hlLayer.id = 'hl-' + num;
            wrapper.appendChild(hlLayer);
            
            container.innerHTML = '';
            container.appendChild(wrapper);
            
            // 渲染文本
            const textContent = await page.getTextContent();
            textContent.items.forEach(item => {{
                const span = document.createElement('span');
                span.textContent = item.str;
                const tx = pdfjsLib.Util.transform(viewport.transform, item.transform);
                const fs = Math.sqrt(tx[0]*tx[0] + tx[1]*tx[1]);
                span.style.cssText = `left:${{tx[4]}}px;top:${{tx[5]-fs}}px;font-size:${{fs}}px;font-family:${{item.fontName||'sans-serif'}}`;
                textLayer.appendChild(span);
            }});
            
            // 渲染已有高亮
            renderHighlights(num);
            
            // 绑定选择事件（高亮模式）
            textLayer.addEventListener('mouseup', onTextSelection);
        }}
        
        // ═══════════════════════════════════════════════════════════════
        // 缩放控制
        // ═══════════════════════════════════════════════════════════════
        function updateZoomDisplay() {{
            zoomValue.textContent = Math.round(state.scale * 100) + '%';
        }}
        
        zoomIn.onclick = () => {{
            if (state.scale < 3) {{
                state.scale = Math.min(3, state.scale + 0.25);
                updateZoomDisplay();
                renderPage(state.page);
            }}
        }};
        
        zoomOut.onclick = () => {{
            if (state.scale > 0.5) {{
                state.scale = Math.max(0.5, state.scale - 0.25);
                updateZoomDisplay();
                renderPage(state.page);
            }}
        }};
        
        zoomReset.onclick = () => {{
            state.scale = 1.0;
            updateZoomDisplay();
            renderPage(state.page);
        }};
        
        updateZoomDisplay();
        
        function renderHighlights(pageNum) {{
            const layer = document.getElementById('hl-' + pageNum);
            if (!layer) return;
            layer.innerHTML = '';
            
            state.highlights.filter(h => !h.coordinate || h.coordinate.page === pageNum).forEach(h => {{
                if (!h.coordinate) return;
                
                const rects = h.rects && h.rects.length > 0 ? h.rects : [h.coordinate];
                const scale = state.scale * state.baseScale;
                rects.forEach(r => {{
                    const div = document.createElement('div');
                    div.className = 'highlight ' + h.color;
                    div.style.cssText = `left:${{r.x * scale}}px;top:${{r.y * scale}}px;width:${{(r.w || r.width) * scale}}px;height:${{(r.h || r.height) * scale}}px`;
                    div.title = h.annotation || h.content;
                    layer.appendChild(div);
                }});
            }});
        }}
        
        function updateUI() {{
            pageInfo.textContent = state.page + ' / ' + state.total;
            prevBtn.disabled = state.page <= 1;
            nextBtn.disabled = state.page >= state.total;
        }}
        
        // ═══════════════════════════════════════════════════════════════
        // 模式切换
        // ═══════════════════════════════════════════════════════════════
        function setMode(mode) {{
            state.isScreenshotMode = (mode === 'screenshot');
            highlightModeBtn.classList.toggle('active', !state.isScreenshotMode);
            screenshotModeBtn.classList.toggle('active', state.isScreenshotMode);
            
            if (state.isScreenshotMode) {{
                container.style.cursor = 'crosshair';
                startScreenshotOverlay();
            }} else {{
                container.style.cursor = 'default';
                removeScreenshotOverlay();
            }}
            hidePopup();
        }}
        
        highlightModeBtn.onclick = () => setMode('highlight');
        screenshotModeBtn.onclick = () => setMode('screenshot');
        
        // ═══════════════════════════════════════════════════════════════
        // 高亮模式：文本选择
        // ═══════════════════════════════════════════════════════════════
        function onTextSelection(e) {{
            if (state.isScreenshotMode) return;
            
            const sel = window.getSelection();
            if (!sel || sel.isCollapsed) return;
            
            state.selectedText = sel.toString().trim();
            if (!state.selectedText) return;
            
            const range = sel.getRangeAt(0);
            state.selectedRange = range;  // 保存选区
            
            const rects = range.getClientRects();
            const wrapperRect = container.querySelector('.page-wrapper').getBoundingClientRect();
            const scale = state.scale * state.baseScale;
            
            state.selectedRects = [];
            for (let i = 0; i < rects.length; i++) {{
                state.selectedRects.push({{
                    x: (rects[i].left - wrapperRect.left) / scale,
                    y: (rects[i].top - wrapperRect.top) / scale,
                    w: rects[i].width / scale,
                    h: rects[i].height / scale
                }});
            }}
            
            // 显示浮动工具框
            const lastRect = rects[rects.length - 1];
            showPopup(lastRect.left + lastRect.width / 2, lastRect.top - 10);
            
            // 不清除选区，保持视觉反馈
            e.preventDefault();
        }}
        
        // ═══════════════════════════════════════════════════════════════
        // 截图模式：框选区域
        // ═══════════════════════════════════════════════════════════════
        let screenshotOverlay = null;
        let screenshotSelection = null;
        
        function startScreenshotOverlay() {{
            if (screenshotOverlay) return;
            
            screenshotOverlay = document.createElement('div');
            screenshotOverlay.className = 'screenshot-overlay';
            screenshotOverlay.innerHTML = '<div class="screenshot-hint">拖动鼠标框选截图区域，ESC取消</div>';
            document.body.appendChild(screenshotOverlay);
            
            screenshotSelection = document.createElement('div');
            screenshotSelection.className = 'screenshot-selection';
            screenshotOverlay.appendChild(screenshotSelection);
            
            screenshotOverlay.addEventListener('mousedown', onScreenshotStart);
            screenshotOverlay.addEventListener('mousemove', onScreenshotMove);
            screenshotOverlay.addEventListener('mouseup', onScreenshotEnd);
            document.addEventListener('keydown', cancelScreenshot);
        }}
        
        function removeScreenshotOverlay() {{
            if (screenshotOverlay) {{
                screenshotOverlay.remove();
                screenshotOverlay = null;
                screenshotSelection = null;
            }}
            document.removeEventListener('keydown', cancelScreenshot);
        }}
        
        function cancelScreenshot(e) {{
            if (e && e.key !== 'Escape') return;
            removeScreenshotOverlay();
            state.screenshotStart = null;
            state.screenshotImageData = null;
            if (state.isScreenshotMode) {{
                setMode('highlight');
            }}
        }}
        
        function onScreenshotStart(e) {{
            state.screenshotStart = {{ x: e.clientX, y: e.clientY }};
            screenshotSelection.style.left = e.clientX + 'px';
            screenshotSelection.style.top = e.clientY + 'px';
            screenshotSelection.style.width = '0';
            screenshotSelection.style.height = '0';
        }}
        
        function onScreenshotMove(e) {{
            if (!state.screenshotStart) return;
            
            const x = Math.min(state.screenshotStart.x, e.clientX);
            const y = Math.min(state.screenshotStart.y, e.clientY);
            const w = Math.abs(e.clientX - state.screenshotStart.x);
            const h = Math.abs(e.clientY - state.screenshotStart.y);
            
            screenshotSelection.style.left = x + 'px';
            screenshotSelection.style.top = y + 'px';
            screenshotSelection.style.width = w + 'px';
            screenshotSelection.style.height = h + 'px';
        }}
        
        function onScreenshotEnd(e) {{
            if (!state.screenshotStart) return;
            
            const rect = {{
                x: Math.min(state.screenshotStart.x, e.clientX),
                y: Math.min(state.screenshotStart.y, e.clientY),
                w: Math.abs(e.clientX - state.screenshotStart.x),
                h: Math.abs(e.clientY - state.screenshotStart.y)
            }};
            
            if (rect.w < 20 || rect.h < 20) {{
                state.screenshotStart = null;
                return;
            }}
            
            // 裁剪截图
            const canvas = container.querySelector('canvas');
            if (!canvas) return;
            
            const canvasRect = canvas.getBoundingClientRect();
            const cropCanvas = document.createElement('canvas');
            cropCanvas.width = rect.w;
            cropCanvas.height = rect.h;
            const ctx = cropCanvas.getContext('2d');
            ctx.drawImage(canvas, rect.x - canvasRect.left, rect.y - canvasRect.top, rect.w, rect.h, 0, 0, rect.w, rect.h);
            
            state.screenshotImageData = cropCanvas.toDataURL('image/png');
            const scale = state.scale * state.baseScale;
            state.selectedRects = [{{ 
                x: (rect.x - canvasRect.left) / scale, 
                y: (rect.y - canvasRect.top) / scale, 
                w: rect.w / scale, 
                h: rect.h / scale 
            }}];
            
            // 显示工具框和OCR区域
            showPopup(rect.x + rect.w / 2, rect.y - 10);
            document.getElementById('ocrSection').classList.add('show');
            
            state.screenshotStart = null;
        }}
        
        // ═══════════════════════════════════════════════════════════════
        // 浮动工具框
        // ═══════════════════════════════════════════════════════════════
        function showPopup(x, y) {{
            // 重置状态
            document.getElementById('popupAnnotation').value = '';
            document.getElementById('translateResult').classList.remove('show');
            document.getElementById('translateResult').textContent = '';
            document.getElementById('ocrSection').classList.remove('show');
            document.getElementById('ocrResult').style.display = 'none';
            
            // 定位
            popupToolbar.style.left = Math.max(10, x - 100) + 'px';
            popupToolbar.style.top = Math.max(10, y - 150) + 'px';
            popupToolbar.classList.add('show');
        }}
        
        function hidePopup() {{
            popupToolbar.classList.remove('show');
            state.selectedText = '';
            state.selectedRects = [];
            state.selectedRange = null;
            state.screenshotImageData = null;
            document.getElementById('ocrSection').classList.remove('show');
            // 清除选区
            window.getSelection()?.removeAllRanges();
        }}
        
        // 颜色选择 - 保持选区视觉反馈
        popupToolbar.querySelectorAll('.popup-color-btn').forEach(btn => {{
            btn.onclick = (e) => {{
                e.stopPropagation();
                popupToolbar.querySelectorAll('.popup-color-btn').forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
                state.color = btn.dataset.color;
                // 不清除选区，保持视觉反馈
            }};
        }})
        
        // OCR按钮
        document.getElementById('ocrBtn').onclick = async () => {{
            if (!state.screenshotImageData) return;
            
            const ocrResult = document.getElementById('ocrResult');
            ocrResult.style.display = 'block';
            ocrResult.textContent = 'OCR识别中...';
            
            // 通知父页面进行OCR
            if (window.parent) {{
                window.parent.postMessage({{ 
                    type: 'ocr', 
                    data: {{ 
                        image: state.screenshotImageData,
                        page: state.page,
                        doc_id: state.docId
                    }}
                }}, '*');
            }}
        }};
        
        // 监听OCR结果
        window.addEventListener('message', function(e) {{
            if (e.data && e.data.type === 'ocr_result') {{
                const ocrText = e.data.data ? e.data.data.text : '';
                const ocrResult = document.getElementById('ocrResult');
                if (ocrText) {{
                    ocrResult.textContent = ocrText;
                    state.selectedText = ocrText;  // 更新为OCR识别的文字
                }} else {{
                    ocrResult.textContent = 'OCR识别失败';
                }}
            }}
        }});;
        
        // 翻译按钮
        document.getElementById('popupTranslate').onclick = async () => {{
            const text = state.selectedText;
            if (!text) return;
            
            const resultDiv = document.getElementById('translateResult');
            resultDiv.textContent = '翻译中...';
            resultDiv.classList.add('show');
            
            // 通知父页面翻译
            if (window.parent) {{
                window.parent.postMessage({{ 
                    type: 'translate', 
                    data: {{ text: text }}
                }}, '*');
            }}
        }};
        
        // 监听翻译结果
        window.addEventListener('message', function(e) {{
            if (e.data && e.data.type === 'translate_result') {{
                const translation = e.data.data ? e.data.data.translation : '';
                const resultDiv = document.getElementById('translateResult');
                if (translation) {{
                    resultDiv.textContent = translation;
                    resultDiv.classList.add('show');
                }} else {{
                    resultDiv.textContent = '翻译失败';
                }}
            }}
        }});
        
        // 保存按钮
        document.getElementById('popupSave').onclick = () => {{
            const annotation = document.getElementById('popupAnnotation').value.trim();
            const ocrText = document.getElementById('ocrResult').textContent;
            const isOCRText = ocrText && ocrText !== 'OCR识别中...' && ocrText !== 'OCR识别失败';
            
            if (state.screenshotImageData) {{
                // 截图笔记
                const data = {{
                    id: 'SS-' + Date.now(),
                    image: state.screenshotImageData,
                    page: state.page,
                    doc_id: state.docId,
                    annotation: annotation,
                    rects: state.selectedRects,
                    ocr_text: isOCRText ? ocrText : ''  // OCR识别的文字
                }};
                if (window.parent) {{
                    window.parent.postMessage({{ type: 'screenshot', data: data }}, '*');
                }}
            }} else if (state.selectedText) {{
                // 高亮笔记
                const hl = {{
                    id: 'HL-' + Date.now(),
                    doc_id: state.docId,
                    chunk_id: '',
                    content: state.selectedText,
                    color: state.color,
                    annotation: annotation,
                    coordinate: {{
                        page: state.page,
                        x: state.selectedRects[0]?.x || 0,
                        y: state.selectedRects[0]?.y || 0,
                        width: state.selectedRects[0]?.w || 100,
                        height: state.selectedRects[0]?.h || 20
                    }},
                    rects: state.selectedRects,
                    created_at: new Date().toISOString()
                }};
                state.highlights.push(hl);
                renderHighlights(state.page);
                if (window.parent) {{
                    window.parent.postMessage({{ type: 'highlight', data: hl }}, '*');
                }}
            }}
            
            hidePopup();
            if (state.isScreenshotMode) setMode('highlight');
        }};
        
        // 点击空白处关闭
        document.addEventListener('mousedown', (e) => {{
            if (!popupToolbar.contains(e.target) && !container.contains(e.target)) {{
                hidePopup();
            }}
        }});
        
        // 翻页
        prevBtn.onclick = () => {{ if (state.page > 1) {{ state.page--; updateUI(); renderPage(state.page); }} }};
        nextBtn.onclick = () => {{ if (state.page < state.total) {{ state.page++; updateUI(); renderPage(state.page); }} }};
        
        init();
    </script>
</body>
</html>"""
