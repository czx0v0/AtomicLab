"""
Global JavaScript
=================
Centralized JS injected via gr.Blocks(head=..., js=...).
Handles: ECharts auto-init via MutationObserver + Floating popup menu.

Replaces all inline <script> that Gradio's gr.HTML() strips via innerHTML.
"""

# ── Preload resources in <head> ──
ECHARTS_HEAD = (
    '<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"'
    " onerror=\"this.onerror=null;this.src='https://unpkg.com/echarts@5/dist/echarts.min.js'\"></script>"
    '<link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap" rel="stylesheet">'
)

# ── Global JS (runs once on page load via gr.Blocks(js=...)) ──
GLOBAL_JS = r"""
(function() {
  // ═══════════════════════════════════════════════════════════════
  // Utilities
  // ═══════════════════════════════════════════════════════════════
  function setGradioValue(selector, value) {
    var el = document.querySelector(selector + ' textarea');
    if (!el) el = document.querySelector(selector + ' input');
    if (!el) { console.warn('[Atomic] setGradioValue: no element for', selector); return; }
    var proto = el.tagName === 'TEXTAREA'
      ? window.HTMLTextAreaElement.prototype
      : window.HTMLInputElement.prototype;
    var setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
    setter.call(el, value);
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
  }

  function getGradioValue(selector) {
    var el = document.querySelector(selector + ' textarea');
    if (!el) el = document.querySelector(selector + ' input');
    return el ? el.value : '';
  }

  // ═══════════════════════════════════════════════════════════════
  // Note Card Expand/Collapse
  // ═══════════════════════════════════════════════════════════════
  window.toggleNoteExpand = function(btn) {
    var card = btn.closest('.nt');
    if (!card) return;
    
    var isCollapsed = card.classList.contains('nt-collapsed');
    if (isCollapsed) {
      card.classList.remove('nt-collapsed');
      card.classList.add('nt-expanded');
      btn.textContent = '收起 ▲';
    } else {
      card.classList.remove('nt-expanded');
      card.classList.add('nt-collapsed');
      btn.textContent = '展开 ▼';
    }
  };

  // ═══════════════════════════════════════════════════════════════
  // Scroll to Highlight in Reader
  // ═══════════════════════════════════════════════════════════════
  window.scrollToHighlight = function(noteId) {
    // Find the mark element with this note ID
    var mark = document.querySelector('mark[data-note-id="' + noteId + '"]');
    if (mark) {
      // Scroll the reader container to show the mark
      var reader = mark.closest('.txt-reader');
      if (reader) {
        mark.scrollIntoView({ behavior: 'smooth', block: 'center' });
        // Add pulse animation
        mark.classList.add('highlight-focus');
        setTimeout(function() {
          mark.classList.remove('highlight-focus');
        }, 2500);
      }
    } else {
      // Mark not on current page - show toast
      showToast('该高亮在其他页面，请翻页查看');
    }
  };

  // ═══════════════════════════════════════════════════════════════
  // Click highlight mark to show note card
  // ═══════════════════════════════════════════════════════════════
  document.addEventListener('click', function(e) {
    var mark = e.target.closest('mark[data-note-id]');
    if (mark) {
      var noteId = mark.getAttribute('data-note-id');
      if (noteId) {
        // Find and highlight the corresponding note card
        var noteCard = document.querySelector('.nt[data-note-id="' + noteId + '"]');
        if (noteCard) {
          noteCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
          noteCard.style.boxShadow = '0 0 0 3px var(--accent-blue)';
          setTimeout(function() {
            noteCard.style.boxShadow = '';
          }, 2000);
          
          // Expand if collapsed
          if (noteCard.classList.contains('nt-collapsed')) {
            var btn = noteCard.querySelector('.nt-expand-btn');
            if (btn) toggleNoteExpand(btn);
          }
        }
      }
    }
  });

  // ═══════════════════════════════════════════════════════════════
  // Organize Tab: Tree Expand/Collapse
  // ═══════════════════════════════════════════════════════════════
  window.toggleOrgTree = function(rowEl, targetId) {
    var content = document.getElementById(targetId);
    if (!content) return;
    
    var toggle = rowEl.querySelector('.org-toggle');
    var isCollapsed = content.style.display === 'none';
    
    if (isCollapsed) {
      content.style.display = 'block';
      if (toggle) toggle.textContent = '▼';
    } else {
      content.style.display = 'none';
      if (toggle) toggle.textContent = '▶';
    }
  };

  // ═══════════════════════════════════════════════════════════════
  // Organize Tab: Note Card Action Buttons
  // ═══════════════════════════════════════════════════════════════
  window.noteAction = function(action, nodeId) {
    console.log('[Atomic] noteAction:', action, nodeId);
    
    // Find and add loading state to clicked button
    var clickedBtn = event && event.target;
    if (clickedBtn && clickedBtn.classList.contains('nt-action-btn')) {
      clickedBtn.classList.add('loading');
      // Remove loading state after timeout (fallback)
      setTimeout(function() { clickedBtn.classList.remove('loading'); }, 8000);
    }
    
    // Special handling for "ask" - switch to AI tab and send question
    if (action === 'ask') {
      // Get the note content
      var noteCard = document.querySelector('.nt[data-note-id="' + nodeId + '"]');
      var content = '';
      if (noteCard) {
        var body = noteCard.querySelector('.nt-body');
        if (body) content = body.textContent.trim();
      }
      // Also try getting from detail card
      if (!content) {
        var detailCard = document.querySelector('.node-detail-card .nt-body');
        if (detailCard) content = detailCard.textContent.trim();
      }
      
      // Switch to AI assistant tab
      var tabs = document.querySelectorAll('button[role="tab"]');
      for (var i = 0; i < tabs.length; i++) {
        if (tabs[i].textContent.trim().indexOf('AI') >= 0) {
          tabs[i].click();
          break;
        }
      }
      
      // Send to AI after tab switch
      setTimeout(function() {
        var askText = content ? '请解释这段内容：' + content.substring(0, 200) : '请解释这条笔记';
        setGradioValue('#ai-ask-input', Date.now() + '|' + askText);
        if (clickedBtn) clickedBtn.classList.remove('loading');
      }, 400);
      
      showToast('正在发送到AI助手...');
      return;
    }
    
    // For other actions, send to Python handler via hidden textbox
    var payload = action + ':' + nodeId;
    setGradioValue('#note-action-input', payload);
    
    // Show immediate feedback
    var messages = {
      'translate': '正在翻译...',
      'tag': '正在生成标签...',
      'search': '正在搜索相似笔记...',
      'annotate': '请在阅读页面添加标注',
      'manual_tag': '正在添加标签...'
    };
    showToast(messages[action] || '处理中...');
  };

  // ═══════════════════════════════════════════════════════════════
  // Manual Tag Input Handler (supports passing input element directly)
  // ═══════════════════════════════════════════════════════════════
  window.manualTag = function(nodeId, inputEl) {
    var input = inputEl || document.getElementById('manual-tag-input');
    if (!input) return;
    
    var tagText = input.value.trim();
    if (!tagText) {
      showToast('请输入标签文本');
      return;
    }
    
    // Send manual_tag:node_id:tag_text
    var payload = 'manual_tag:' + nodeId + ':' + tagText;
    setGradioValue('#note-action-input', payload);
    input.value = '';
    showToast('正在添加标签: ' + tagText);
  };

  // ═══════════════════════════════════════════════════════════════
  // Show Annotate Popup for adding annotation to a note
  // ═══════════════════════════════════════════════════════════════
  
  // Create annotate modal (once)
  var annotateModal = document.createElement('div');
  annotateModal.className = 'annotate-modal';
  annotateModal.id = 'annotate-modal';
  annotateModal.innerHTML = [
    '<div class="annotate-modal-content">',
    '  <div class="annotate-modal-title">添加批注</div>',
    '  <textarea class="annotate-modal-input" id="annotate-input" placeholder="请输入批注内容..."></textarea>',
    '  <div class="annotate-modal-btns">',
    '    <button class="annotate-modal-btn" onclick="closeAnnotateModal()">取消</button>',
    '    <button class="annotate-modal-btn primary" onclick="submitAnnotate()">确定</button>',
    '  </div>',
    '</div>',
  ].join('');
  document.body.appendChild(annotateModal);
  
  var currentAnnotateNodeId = '';
  
  window.showAnnotatePopup = function(nodeId) {
    currentAnnotateNodeId = nodeId;
    var modal = document.getElementById('annotate-modal');
    var input = document.getElementById('annotate-input');
    if (modal && input) {
      input.value = '';
      modal.classList.add('show');
      setTimeout(function() { input.focus(); }, 100);
    }
  };
  
  window.closeAnnotateModal = function() {
    var modal = document.getElementById('annotate-modal');
    if (modal) modal.classList.remove('show');
    currentAnnotateNodeId = '';
  };
  
  window.submitAnnotate = function() {
    var input = document.getElementById('annotate-input');
    var annotation = input ? input.value.trim() : '';
    if (!annotation) {
      showToast('请输入批注内容', 1500);
      return;
    }
    if (!currentAnnotateNodeId) {
      showToast('批注目标丢失', 1500);
      return;
    }
    var payload = 'annotate:' + currentAnnotateNodeId + ':' + annotation;
    setGradioValue('#note-action-input', payload);
    closeAnnotateModal();
    showToast('正在添加批注...', 2000);
  };
  
  // Close modal on backdrop click
  annotateModal.addEventListener('click', function(e) {
    if (e.target === annotateModal) closeAnnotateModal();
  });
  
  // Close modal on Escape key
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && annotateModal.classList.contains('show')) {
      closeAnnotateModal();
    }
  });

  // ═══════════════════════════════════════════════════════════════
  // Jump to Source Document (from similar search results)
  // ═══════════════════════════════════════════════════════════════
  window.jumpToSource = function(sourcePid, page) {
    if (!sourcePid) {
      showToast('无法定位：缺少文档信息');
      return;
    }
    
    // Switch to 阅读 tab
    var tabs = document.querySelectorAll('button[role="tab"]');
    for (var i = 0; i < tabs.length; i++) {
      if (tabs[i].textContent.trim() === '阅读') {
        tabs[i].click();
        break;
      }
    }
    
    // Set the document selector to switch to the document
    setTimeout(function() {
      setGradioValue('#pdf-selector-hidden', sourcePid);
      showToast('正在跳转到文档 (第' + page + '页)');
      
      // TODO: After document loads, navigate to specific page
      // This would require storing page number and triggering page navigation
    }, 300);
  };

  // ═══════════════════════════════════════════════════════════════
  // ECharts Auto-Initialization (MutationObserver pattern)
  // ═══════════════════════════════════════════════════════════════
  function initEChartsContainer(el) {
    if (!el || el.classList.contains('echarts-done')) return;
    if (!el.clientHeight || el.clientHeight < 10) return;

    var optionStr = el.getAttribute('data-option');
    if (!optionStr) return;

    try {
      var option = JSON.parse(optionStr);
      var existing = echarts.getInstanceByDom(el);
      if (existing) existing.dispose();

      var chart = echarts.init(el);
      chart.setOption(option);
      el.classList.remove('echarts-auto');
      el.classList.add('echarts-done');

      // Click handler (by type)
      var clickType = el.getAttribute('data-click') || '';
      if (clickType === 'node-select') {
        chart.on('click', function(params) {
          var nodeId = (params.data && params.data.id) ? params.data.id : '';
          if (nodeId) {
            // Check which graph this is by container ID
            var containerId = el.id || '';
            if (containerId.indexOf('write-graph') >= 0) {
              // Write tab graph - use write-specific input
              setGradioValue('#write-graph-node-input', nodeId);
            } else {
              // Organize tab graph - use default input
              setGradioValue('#selected-node-input', nodeId);
            }
          }
        });
      }

      // Responsive resize
      try {
        new ResizeObserver(function() { chart.resize(); }).observe(el);
      } catch(e) {
        window.addEventListener('resize', function() { chart.resize(); });
      }
    } catch(e) {
      console.error('[Atomic] ECharts init error:', e);
    }
  }

  function scanAndInitECharts() {
    if (typeof echarts === 'undefined') return;
    document.querySelectorAll('.echarts-auto').forEach(function(el) {
      initEChartsContainer(el);
    });
  }

  // Watch DOM for new .echarts-auto elements
  var echartsObserver = new MutationObserver(function(mutations) {
    var hasNew = false;
    for (var i = 0; i < mutations.length; i++) {
      if (mutations[i].addedNodes.length > 0) { hasNew = true; break; }
    }
    if (hasNew) {
      requestAnimationFrame(function() { setTimeout(scanAndInitECharts, 120); });
    }
  });
  echartsObserver.observe(document.body, { childList: true, subtree: true });

  // Initial scan with retry (wait for echarts CDN)
  var initRetries = 0;
  function tryInitECharts() {
    scanAndInitECharts();
    if (document.querySelectorAll('.echarts-auto').length > 0 && initRetries++ < 40) {
      setTimeout(tryInitECharts, 250);
    }
  }
  setTimeout(tryInitECharts, 300);

  // ═══════════════════════════════════════════════════════════════
  // Floating Popup Menu (dynamically created, not in gr.HTML)
  // ═══════════════════════════════════════════════════════════════
  var popup = document.createElement('div');
  popup.id = 'txt-popup';
  popup.innerHTML = [
    '<div class="popup-color-btn" style="background:#fc8181" data-color="red" title="红色高亮"></div>',
    '<div class="popup-color-btn" style="background:#fbd38d" data-color="yellow" title="黄色高亮"></div>',
    '<div class="popup-color-btn" style="background:#9ae6b4" data-color="green" title="绿色高亮"></div>',
    '<div class="popup-color-btn" style="background:#d6bcfa" data-color="purple" title="紫色高亮"></div>',
    '<input class="popup-annotation" id="popup-annotation" type="text" placeholder="批注(可选)..." />',
    '<div class="popup-divider"></div>',
    '<div class="popup-action-btn" data-action="translate">翻译</div>',
    '<div class="popup-action-btn" data-action="copy">复制</div>',
    '<div class="popup-action-btn" data-action="ask-ai">问AI</div>',
    '<div class="popup-translate-result" id="popup-translate-result" style="display:none"></div>',
  ].join('');
  document.body.appendChild(popup);

  var toast = document.createElement('div');
  toast.className = 'popup-toast';
  toast.id = 'popup-toast';
  document.body.appendChild(toast);

  var selectedText = '';
  var selectedPage = '1';

  function showToast(msg, dur, type) {
    toast.textContent = msg;
    toast.className = 'popup-toast';  // Reset classes
    if (type) toast.classList.add(type);  // 'success' or 'error'
    toast.classList.add('show');
    setTimeout(function() { 
      toast.classList.remove('show'); 
      toast.className = 'popup-toast';
    }, dur || 1500);
  }
  // Export showToast globally for other functions
  window.showToast = showToast;
  
  // Track last clicked action button for feedback
  var lastActionBtn = null;
  var lastActionType = '';
  
  // Override noteAction to track button
  var originalNoteAction = window.noteAction;
  window.noteAction = function(action, nodeId) {
    var clickedBtn = event && event.target;
    if (clickedBtn && clickedBtn.classList.contains('nt-action-btn')) {
      lastActionBtn = clickedBtn;
      lastActionType = action;
    }
    originalNoteAction(action, nodeId);
  };
  
  // Listen for agent status changes to provide feedback
  var agentStatusObserver = new MutationObserver(function(mutations) {
    mutations.forEach(function(m) {
      if (m.type === 'childList' || m.type === 'characterData') {
        var target = m.target.closest ? m.target.closest('.agent-st') : null;
        if (!target) target = document.querySelector('.agent-st');
        if (target) {
          var text = target.textContent || '';
          if (lastActionBtn) {
            lastActionBtn.classList.remove('loading');
            if (text.indexOf('完成') >= 0 || text.indexOf('已添加') >= 0) {
              lastActionBtn.classList.add('success');
              showToast(text, 2000, 'success');
              setTimeout(function() { 
                if (lastActionBtn) lastActionBtn.classList.remove('success'); 
              }, 2000);
            } else if (text.indexOf('失败') >= 0 || text.indexOf('错误') >= 0) {
              lastActionBtn.classList.add('error');
              showToast(text, 2500, 'error');
              setTimeout(function() { 
                if (lastActionBtn) lastActionBtn.classList.remove('error'); 
              }, 2500);
            }
            lastActionBtn = null;
          }
        }
      }
    });
  });
  // Start observing agent status element when available
  setTimeout(function() {
    var agentSt = document.querySelector('.agent-st');
    if (agentSt) {
      agentStatusObserver.observe(agentSt.parentElement || agentSt, { 
        childList: true, subtree: true, characterData: true 
      });
    }
  }, 1000);

  function hidePopup() {
    popup.classList.remove('show');
    var tr = document.getElementById('popup-translate-result');
    if (tr) { tr.style.display = 'none'; tr.textContent = ''; }
  }

  // ── Show popup on text selection in .txt-reader ──
  document.addEventListener('mouseup', function(e) {
    if (popup.contains(e.target)) return;
    // Don't show popup when clicking on existing marks
    if (e.target.closest('mark[data-note-id]')) return;

    var reader = e.target.closest('.txt-reader');
    if (!reader) { hidePopup(); return; }

    var sel = window.getSelection();
    var text = sel.toString().trim();
    if (!text) { hidePopup(); return; }

    selectedText = text;
    var para = e.target.closest('.txt-para');
    selectedPage = para ? (para.dataset.page || '1') : '1';

    // Position near selection
    var range = sel.getRangeAt(0);
    var rect = range.getBoundingClientRect();
    var px = rect.left + rect.width / 2 - 150;
    var py = rect.top - 52;
    if (py < 10) py = rect.bottom + 10;
    px = Math.max(10, Math.min(px, window.innerWidth - 400));

    popup.style.left = px + 'px';
    popup.style.top = py + 'px';
    var tr = document.getElementById('popup-translate-result');
    if (tr) { tr.style.display = 'none'; tr.textContent = ''; }
    var ann = document.getElementById('popup-annotation');
    if (ann) ann.value = '';
    popup.classList.add('show');
  });

  // Hide on outside click
  document.addEventListener('mousedown', function(e) {
    if (!popup.contains(e.target) && !e.target.closest('.txt-reader')) {
      hidePopup();
    }
  });

  // ── Color highlight buttons ──
  popup.querySelectorAll('.popup-color-btn').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      var color = this.dataset.color;

      // Visual highlight (temporary, will be replaced by server-rendered persistent highlight)
      try {
        var sel = window.getSelection();
        if (sel.rangeCount > 0 && sel.toString().trim()) {
          var range = sel.getRangeAt(0);
          // Check if selection spans multiple elements
          if (range.startContainer === range.endContainer || 
              range.startContainer.parentNode === range.endContainer.parentNode) {
            // Simple case: single element selection
            var mark = document.createElement('mark');
            mark.className = 'hl-' + color;
            range.surroundContents(mark);
          } else {
            // Multi-element selection: highlight using CSS class on common ancestor
            var ancestor = range.commonAncestorContainer;
            if (ancestor.nodeType === 3) ancestor = ancestor.parentNode;
            ancestor.classList.add('hl-temp-' + color);
            // Remove temp class after page refresh will render persistent highlight
            setTimeout(function() { ancestor.classList.remove('hl-temp-' + color); }, 3000);
          }
          sel.removeAllRanges();
        }
      } catch(err) { 
        // Cross-element selection failed, but data will still be saved
        console.log('[Atomic] Temp highlight skipped (cross-element)');
      }

      // Auto-save as note via hidden textbox (this always works regardless of visual highlight)
      var annotation = document.getElementById('popup-annotation') ? document.getElementById('popup-annotation').value.trim() : '';
      var payload = JSON.stringify({
        action: 'highlight', text: selectedText,
        page: selectedPage, color: color, annotation: annotation, _t: Date.now()
      });
      setGradioValue('#highlight-action-input', payload);
      hidePopup();
      showToast('已添加高亮笔记');
    });
  });

  // ── Action buttons: translate, copy, ask-ai ──
  popup.querySelectorAll('.popup-action-btn').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      var action = this.dataset.action;

      if (action === 'copy') {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(selectedText).then(function() {
            showToast('已复制');
          }).catch(function() { fallbackCopy(); });
        } else { fallbackCopy(); }
        hidePopup();

      } else if (action === 'translate') {
        var tr = document.getElementById('popup-translate-result');
        tr.style.display = 'block';
        tr.textContent = '翻译中...';

        setGradioValue('#translate-result-input', '');
        setTimeout(function() {
          setGradioValue('#translate-action-input', Date.now() + '|' + selectedText);
        }, 60);

        // Poll for result
        var pollCount = 0;
        var pollTimer = setInterval(function() {
          var result = getGradioValue('#translate-result-input');
          if (result && result.trim()) {
            tr.innerHTML = result
              + '<br><span class="popup-action-btn" style="margin-top:4px;display:inline-block;cursor:pointer"'
              + ' data-save-translate="true">保存笔记</span>';
            var saveBtn = tr.querySelector('[data-save-translate]');
            if (saveBtn) {
              saveBtn.addEventListener('click', function() {
                var p = JSON.stringify({
                  action: 'translate_note',
                  text: encodeURIComponent(selectedText),
                  translation: encodeURIComponent(result),
                  page: selectedPage, _t: Date.now()
                });
                setGradioValue('#highlight-action-input', p);
                this.textContent = '已保存';
                showToast('已保存翻译笔记');
              });
            }
            clearInterval(pollTimer);
          }
          if (++pollCount > 60) {
            tr.textContent = '翻译超时，请重试';
            clearInterval(pollTimer);
          }
        }, 300);

      } else if (action === 'ask-ai') {
        // 1. Switch to AI assistant tab
        var tabs = document.querySelectorAll('button[role="tab"]');
        for (var ti = 0; ti < tabs.length; ti++) {
          if (tabs[ti].textContent.trim().indexOf('AI') >= 0) {
            tabs[ti].click();
            break;
          }
        }
        // 2. Fill chat input and auto-submit
        var askText = selectedText;
        setTimeout(function() {
          setGradioValue('#chat-input', askText);
          // Also trigger hidden bridge for auto-send
          setGradioValue('#ai-ask-input', Date.now() + '|' + askText);
        }, 400);
        hidePopup();
        showToast('正在发送到AI助手...');
      }
    });
  });

  function fallbackCopy() {
    var ta = document.createElement('textarea');
    ta.value = selectedText;
    ta.style.cssText = 'position:fixed;opacity:0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); showToast('已复制'); }
    catch(e) { showToast('复制失败'); }
    document.body.removeChild(ta);
  }

  // ═══════════════════════════════════════════════════════════════
  // PDF.js iframe highlight message handler
  // ═══════════════════════════════════════════════════════════════
  var pendingTranslateCallback = null;
  
  window.addEventListener('message', function(e) {
    // 接收来自PDF.js iframe的高亮消息
    if (e.data && e.data.type === 'highlight') {
      var hl = e.data.data;
      if (!hl || !hl.content) return;
      
      console.log('[Atomic] PDF.js高亮消息:', hl);
      
      // 构建与文本模式相同格式的payload
      var payload = JSON.stringify({
        action: 'highlight',
        text: hl.content,
        page: String(hl.coordinate ? hl.coordinate.page : 1),
        color: hl.color || 'yellow',
        annotation: hl.annotation || '',
        // PDF.js特有字段
        pdfjs: true,
        coordinate: hl.coordinate,
        rects: hl.rects,
        highlight_id: hl.id,
        _t: Date.now()
      });
      
      // 触发保存笔记
      setGradioValue('#highlight-action-input', payload);
      showToast('已保存高亮笔记到知识图谱');
    }
    
    // 接收截图消息
    if (e.data && e.data.type === 'screenshot') {
      var data = e.data.data;
      if (!data || !data.image) return;
      
      console.log('[Atomic] PDF.js截图消息:', data);
      
      // 构建截图笔记payload
      var payload = JSON.stringify({
        action: 'screenshot',
        image: data.image,  // base64图片
        page: String(data.page || 1),
        annotation: data.annotation || '',
        doc_id: data.doc_id,
        rects: data.rects,
        _t: Date.now()
      });
      
      // 触发保存截图笔记
      setGradioValue('#highlight-action-input', payload);
      showToast('已保存截图笔记');
    }
    
    // 接收翻译请求
    if (e.data && e.data.type === 'translate') {
      var text = e.data.data ? e.data.data.text : '';
      if (!text) return;
      
      console.log('[Atomic] PDF.js翻译请求:', text);
      
      // 发送翻译请求到Python
      setGradioValue('#translate-action-input', Date.now() + '|' + text);
      
      // 设置回调，等待翻译结果
      pendingTranslateCallback = function(result) {
        // 发送翻译结果回iframe
        var iframes = document.querySelectorAll('iframe');
        iframes.forEach(function(iframe) {
          try {
            iframe.contentWindow.postMessage({
              type: 'translate_result',
              data: { translation: result }
            }, '*');
          } catch(err) {}
        });
      };
      
      // 轮询等待翻译结果
      var pollCount = 0;
      var pollTimer = setInterval(function() {
        var result = getGradioValue('#translate-result-input');
        if (result && result.trim()) {
          if (pendingTranslateCallback) {
            pendingTranslateCallback(result);
            pendingTranslateCallback = null;
          }
          clearInterval(pollTimer);
        }
        if (++pollCount > 40) {
          clearInterval(pollTimer);
          pendingTranslateCallback = null;
        }
      }, 200);
    }
    
    // 接收翻译结果（从iframe内部）
    if (e.data && e.data.type === 'translate_result') {
      // 转发给当前激活的iframe
      // 这个分支在父页面不处理，由iframe内部处理
    }
  });

  // ═══════════════════════════════════════════════════════════════
  // File List: click to select file (sets hidden textbox value)
  // ═══════════════════════════════════════════════════════════════
  window.setFileSelection = function(pid) {
    console.log('[Atomic] setFileSelection called with pid:', pid);
    
    // Find the hidden selector element
    // With container=False, the elem_id may be directly on the input/textarea
    var el = document.querySelector('#pdf-selector-hidden');
    if (!el) {
      console.warn('[Atomic] #pdf-selector-hidden not found');
      return;
    }
    
    // Check if el is already an input/textarea or a container
    var input;
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
      input = el;
    } else {
      // It's a container, find the input inside
      input = el.querySelector('textarea') || el.querySelector('input');
    }
    
    if (!input) {
      console.warn('[Atomic] No input element found in #pdf-selector-hidden');
      return;
    }
    
    console.log('[Atomic] Found input element:', input.tagName, 'current value:', input.value);
    
    // Set value using native setter to trigger Gradio's event system
    var proto = input.tagName === 'TEXTAREA'
      ? window.HTMLTextAreaElement.prototype
      : window.HTMLInputElement.prototype;
    var setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
    setter.call(input, pid);
    
    // Dispatch events to trigger Gradio change handler
    input.dispatchEvent(new Event('input', {bubbles: true}));
    input.dispatchEvent(new Event('change', {bubbles: true}));
    
    console.log('[Atomic] Value set to:', input.value);
    
    // Update visual active state
    document.querySelectorAll('.file-item').forEach(function(item) {
      item.classList.remove('active');
    });
    var clicked = event && event.currentTarget;
    if (clicked) clicked.classList.add('active');
  };

  // ═══════════════════════════════════════════════════════════════
  // Writing Toolbar: insert markdown formatting
  // ═══════════════════════════════════════════════════════════════
  window.writeToolbarAction = function(action) {
    // Find the draft textarea
    var ta = document.querySelector('#write-draft textarea');
    if (!ta) return;
    ta.focus();
    var start = ta.selectionStart;
    var end = ta.selectionEnd;
    var selected = ta.value.substring(start, end);
    var before = ta.value.substring(0, start);
    var after = ta.value.substring(end);
    var insert = '';
    var cursorOffset = 0;

    switch(action) {
      case 'bold': insert = '**' + (selected || '粗体') + '**'; cursorOffset = 2; break;
      case 'italic': insert = '*' + (selected || '斜体') + '*'; cursorOffset = 1; break;
      case 'h1': insert = '# ' + (selected || '标题'); cursorOffset = 2; break;
      case 'h2': insert = '## ' + (selected || '标题'); cursorOffset = 3; break;
      case 'h3': insert = '### ' + (selected || '标题'); cursorOffset = 4; break;
      case 'quote': insert = '> ' + (selected || '引用'); cursorOffset = 2; break;
      case 'code': insert = '`' + (selected || '代码') + '`'; cursorOffset = 1; break;
      case 'codeblock': insert = '```\n' + (selected || '') + '\n```'; cursorOffset = 4; break;
      case 'ul': insert = '- ' + (selected || '列表项'); cursorOffset = 2; break;
      case 'ol': insert = '1. ' + (selected || '列表项'); cursorOffset = 3; break;
      case 'link': insert = '[' + (selected || '链接文字') + '](url)'; cursorOffset = 1; break;
      case 'table':
        insert = '| 列1 | 列2 | 列3 |\n| --- | --- | --- |\n| | | |';
        cursorOffset = 0; break;
      case 'hr': insert = '\n---\n'; cursorOffset = 0; break;
      default: return;
    }

    var newValue = before + insert + after;
    // Use native setter to trigger Gradio
    var setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
    setter.call(ta, newValue);
    ta.dispatchEvent(new Event('input', {bubbles: true}));

    // Set cursor position
    var newPos = start + insert.length;
    ta.setSelectionRange(newPos, newPos);
  };
})();
"""
