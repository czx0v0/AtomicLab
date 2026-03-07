"""
Docling Viewer Interactions
===========================
Docling PDF渲染器的JavaScript交互代码

支持：
- 文本选中高亮
- 浮动工具栏（翻译/复制/笔记）
- 高亮点击显示笔记
- 页码导航
"""

DOCLING_INTERACTIONS_JS = """
// Docling Viewer 交互脚本
(function() {
    'use strict';
    
    // 配置
    const CONFIG = {
        popupDelay: 200,
        highlightColors: ['yellow', 'red', 'green', 'blue', 'purple'],
        maxSelectionLength: 500
    };
    
    // 状态
    let currentSelection = null;
    let popupTimeout = null;
    let activePopup = null;
    
    // 初始化
    function init() {
        const viewer = document.querySelector('.docling-viewer');
        if (!viewer) return;
        
        // 绑定选择事件
        viewer.addEventListener('mouseup', handleSelection);
        viewer.addEventListener('touchend', handleSelection);
        
        // 点击其他地方关闭弹窗
        document.addEventListener('click', handleDocumentClick);
        
        // 绑定高亮点击事件
        viewer.addEventListener('click', handleHighlightClick);
        
        console.log('[DoclingViewer] 初始化完成');
    }
    
    // 处理文本选择
    function handleSelection(e) {
        const selection = window.getSelection();
        const text = selection.toString().trim();
        
        if (!text || text.length < 2) {
            hidePopup();
            return;
        }
        
        if (text.length > CONFIG.maxSelectionLength) {
            console.log('[DoclingViewer] 选择文本过长');
            return;
        }
        
        currentSelection = {
            text: text,
            range: selection.getRangeAt(0)
        };
        
        // 延迟显示弹窗（避免误触）
        clearTimeout(popupTimeout);
        popupTimeout = setTimeout(() => {
            showPopup(e.clientX, e.clientY, text);
        }, CONFIG.popupDelay);
    }
    
    // 显示浮动工具栏
    function showPopup(x, y, text) {
        hidePopup();
        
        const popup = document.createElement('div');
        popup.className = 'docling-popup';
        popup.innerHTML = `
            <div class="popup-content">
                <span class="popup-text" title="${escapeHtml(text)}">${escapeHtml(text.substring(0, 30))}${text.length > 30 ? '...' : ''}</span>
                <div class="popup-actions">
                    <button class="popup-btn highlight-btn" data-color="yellow" title="高亮">
                        <span class="color-dot yellow"></span>
                    </button>
                    <button class="popup-btn highlight-btn" data-color="red" title="重要">
                        <span class="color-dot red"></span>
                    </button>
                    <button class="popup-btn highlight-btn" data-color="green" title="参考">
                        <span class="color-dot green"></span>
                    </button>
                    <button class="popup-btn" id="btn-translate" title="翻译">🌐</button>
                    <button class="popup-btn" id="btn-copy" title="复制">📋</button>
                    <button class="popup-btn" id="btn-note" title="笔记">📝</button>
                </div>
            </div>
        `;
        
        // 定位弹窗
        const rect = document.documentElement.getBoundingClientRect();
        const popupWidth = 280;
        const popupHeight = 60;
        
        let left = x - popupWidth / 2;
        let top = y - popupHeight - 10;
        
        // 边界检查
        if (left < 10) left = 10;
        if (left + popupWidth > rect.width - 10) left = rect.width - popupWidth - 10;
        if (top < 10) top = y + 20;
        
        popup.style.cssText = `
            position: fixed;
            left: ${left}px;
            top: ${top}px;
            z-index: 10000;
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            padding: 10px 14px;
            min-width: 260px;
            font-family: system-ui, -apple-system, sans-serif;
            font-size: 13px;
        `;
        
        document.body.appendChild(popup);
        activePopup = popup;
        
        // 绑定按钮事件
        bindPopupEvents(popup, text);
    }
    
    // 绑定弹窗事件
    function bindPopupEvents(popup, text) {
        // 高亮按钮
        popup.querySelectorAll('.highlight-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const color = btn.dataset.color;
                createHighlight(color);
                hidePopup();
            });
        });
        
        // 翻译按钮
        popup.querySelector('#btn-translate').addEventListener('click', (e) => {
            e.stopPropagation();
            translateText(text);
            hidePopup();
        });
        
        // 复制按钮
        popup.querySelector('#btn-copy').addEventListener('click', (e) => {
            e.stopPropagation();
            copyText(text);
            hidePopup();
        });
        
        // 笔记按钮
        popup.querySelector('#btn-note').addEventListener('click', (e) => {
            e.stopPropagation();
            addNote(text);
            hidePopup();
        });
    }
    
    // 创建高亮
    function createHighlight(color) {
        if (!currentSelection || !currentSelection.range) return;
        
        const mark = document.createElement('mark');
        mark.className = `hl-${color}`;
        mark.dataset.noteId = 'new_' + Date.now();
        
        try {
            currentSelection.range.surroundContents(mark);
            
            // 触发事件通知Gradio
            notifyGradio('highlight', {
                text: currentSelection.text,
                color: color,
                page: getCurrentPage()
            });
        } catch (e) {
            console.error('[DoclingViewer] 高亮创建失败:', e);
        }
        
        // 清除选择
        window.getSelection().removeAllRanges();
    }
    
    // 翻译文本
    function translateText(text) {
        notifyGradio('translate', { text: text });
    }
    
    // 复制文本
    function copyText(text) {
        navigator.clipboard.writeText(text).then(() => {
            showToast('已复制到剪贴板');
        }).catch(() => {
            showToast('复制失败');
        });
    }
    
    // 添加笔记
    function addNote(text) {
        notifyGradio('note', {
            text: text,
            page: getCurrentPage()
        });
    }
    
    // 处理高亮点击
    function handleHighlightClick(e) {
        const mark = e.target.closest('mark');
        if (!mark) return;
        
        e.stopPropagation();
        
        const noteId = mark.dataset.noteId;
        const noteText = mark.textContent;
        
        // 显示笔记详情弹窗
        showNoteDetail(e.clientX, e.clientY, noteId, noteText);
    }
    
    // 显示笔记详情
    function showNoteDetail(x, y, noteId, text) {
        hidePopup();
        
        const popup = document.createElement('div');
        popup.className = 'docling-popup note-detail';
        popup.innerHTML = `
            <div class="note-detail-content">
                <p class="note-text">${escapeHtml(text)}</p>
                <div class="note-actions">
                    <button class="note-btn" id="btn-view-note">查看笔记</button>
                    <button class="note-btn" id="btn-delete-highlight">删除高亮</button>
                </div>
            </div>
        `;
        
        popup.style.cssText = `
            position: fixed;
            left: ${x}px;
            top: ${y}px;
            z-index: 10000;
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            padding: 14px;
            min-width: 200px;
            max-width: 300px;
        `;
        
        document.body.appendChild(popup);
        activePopup = popup;
        
        // 绑定事件
        popup.querySelector('#btn-view-note').addEventListener('click', () => {
            notifyGradio('view_note', { noteId: noteId });
            hidePopup();
        });
        
        popup.querySelector('#btn-delete-highlight').addEventListener('click', () => {
            removeHighlight(noteId);
            hidePopup();
        });
    }
    
    // 移除高亮
    function removeHighlight(noteId) {
        const mark = document.querySelector(`mark[data-note-id="${noteId}"]`);
        if (mark) {
            const parent = mark.parentNode;
            parent.replaceChild(document.createTextNode(mark.textContent), mark);
            parent.normalize();
            
            notifyGradio('delete_highlight', { noteId: noteId });
        }
    }
    
    // 获取当前页码
    function getCurrentPage() {
        const section = document.querySelector('.doc-section[data-page]');
        return section ? section.dataset.page : '1';
    }
    
    // 隐藏弹窗
    function hidePopup() {
        if (activePopup) {
            activePopup.remove();
            activePopup = null;
        }
        clearTimeout(popupTimeout);
    }
    
    // 处理文档点击
    function handleDocumentClick(e) {
        if (!e.target.closest('.docling-popup')) {
            hidePopup();
        }
    }
    
    // 通知Gradio
    function notifyGradio(action, data) {
        // 通过自定义事件通知Gradio
        const event = new CustomEvent('doclingAction', {
            detail: { action, data, timestamp: Date.now() }
        });
        document.dispatchEvent(event);
        
        console.log('[DoclingViewer] 动作:', action, data);
    }
    
    // 显示提示
    function showToast(message) {
        const toast = document.createElement('div');
        toast.className = 'docling-toast';
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: #333;
            color: white;
            padding: 10px 20px;
            border-radius: 20px;
            font-size: 13px;
            z-index: 10001;
            animation: fadeInOut 2s ease;
        `;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 2000);
    }
    
    // HTML转义
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // 添加CSS动画
    function addStyles() {
        if (document.getElementById('docling-animations')) return;
        
        const style = document.createElement('style');
        style.id = 'docling-animations';
        style.textContent = `
            @keyframes fadeInOut {
                0% { opacity: 0; transform: translateX(-50%) translateY(10px); }
                20% { opacity: 1; transform: translateX(-50%) translateY(0); }
                80% { opacity: 1; transform: translateX(-50%) translateY(0); }
                100% { opacity: 0; transform: translateX(-50%) translateY(-10px); }
            }
            
            .docling-popup .popup-content {
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .docling-popup .popup-text {
                flex: 1;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                color: #4a5568;
            }
            
            .docling-popup .popup-actions {
                display: flex;
                gap: 6px;
            }
            
            .docling-popup .popup-btn {
                width: 28px;
                height: 28px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 14px;
                background: #f7fafc;
                transition: all 0.2s;
            }
            
            .docling-popup .popup-btn:hover {
                background: #e2e8f0;
            }
            
            .docling-popup .color-dot {
                width: 14px;
                height: 14px;
                border-radius: 50%;
                display: block;
            }
            
            .color-dot.yellow { background: #fbbf24; }
            .color-dot.red { background: #f87171; }
            .color-dot.green { background: #34d399; }
            
            .note-detail-content .note-text {
                margin: 0 0 10px 0;
                font-size: 13px;
                line-height: 1.5;
                color: #2d3748;
            }
            
            .note-detail-content .note-actions {
                display: flex;
                gap: 8px;
            }
            
            .note-detail-content .note-btn {
                flex: 1;
                padding: 6px 12px;
                border: 1px solid #e2e8f0;
                border-radius: 4px;
                background: white;
                cursor: pointer;
                font-size: 12px;
                color: #4a5568;
            }
            
            .note-detail-content .note-btn:hover {
                background: #f7fafc;
            }
        `;
        document.head.appendChild(style);
    }
    
    // 启动
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            init();
            addStyles();
        });
    } else {
        init();
        addStyles();
    }
})();
"""


def get_interaction_js() -> str:
    """获取交互JavaScript代码"""
    return f"<script>{DOCLING_INTERACTIONS_JS}</script>"


def wrap_with_interactions(html_content: str) -> str:
    """将HTML内容包装为可交互的Docling视图"""
    from .docling_styles import get_docling_styles
    
    return f"""
    {get_docling_styles()}
    {get_interaction_js()}
    <div class="docling-viewer-wrapper">
        {html_content}
    </div>
    """
