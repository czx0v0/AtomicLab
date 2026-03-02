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
          if (nodeId) setGradioValue('#selected-node-input', nodeId);
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

  function showToast(msg, dur) {
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(function() { toast.classList.remove('show'); }, dur || 1500);
  }

  function hidePopup() {
    popup.classList.remove('show');
    var tr = document.getElementById('popup-translate-result');
    if (tr) { tr.style.display = 'none'; tr.textContent = ''; }
  }

  // ── Show popup on text selection in .txt-reader ──
  document.addEventListener('mouseup', function(e) {
    if (popup.contains(e.target)) return;

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

      // Visual highlight
      try {
        var sel = window.getSelection();
        if (sel.rangeCount > 0 && sel.toString().trim()) {
          var range = sel.getRangeAt(0);
          var mark = document.createElement('mark');
          mark.className = 'hl-' + color;
          range.surroundContents(mark);
          sel.removeAllRanges();
        }
      } catch(err) { /* cross-element selection */ }

      // Auto-save as note via hidden textbox
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
  // File List: click to select file (sets hidden dropdown value)
  // ═══════════════════════════════════════════════════════════════
  window.setFileSelection = function(pid) {
    // Set the hidden dropdown value to trigger Gradio event
    setGradioValue('#pdf-selector-hidden', pid);
    // Also update visual active state
    document.querySelectorAll('.file-item').forEach(function(el) {
      el.classList.remove('active');
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
