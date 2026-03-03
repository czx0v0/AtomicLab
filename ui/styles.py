"""
UI Styles
=========
Clean white theme with pixel font accents for Atomic Lab.
Design: Press Start 2P pixel font headers + subtle glassmorphism +
        blue/orange accent palette on white background.
"""

CSS = """
/* ══════════════════════════════════════════════════════════════
   CSS Custom Properties — Light Theme
   ══════════════════════════════════════════════════════════════ */
:root{
  --bg-primary:#fafaf8;
  --bg-secondary:#fff;
  --bg-card:#fff;
  --bg-glass:rgba(255,255,255,.85);
  --border:#e2e8f0;
  --border-hover:rgba(91,141,239,.4);
  --text-primary:#2d3748;
  --text-secondary:#4a5568;
  --text-muted:#a0aec0;
  --accent-blue:#5b8def;
  --accent-blue-dim:rgba(91,141,239,.1);
  --accent-orange:#f0883e;
  --accent-orange-dim:rgba(240,136,62,.1);
  --accent-green:#48bb78;
  --accent-red:#e53e3e;
  --accent-purple:#9f7aea;
  --glass-blur:blur(12px);
  --radius:10px;
  --radius-sm:6px;
  --shadow-sm:0 1px 3px rgba(0,0,0,.06);
  --shadow-md:0 4px 12px rgba(0,0,0,.08);
  --shadow-glow:0 0 16px rgba(91,141,239,.1);
  --font-body:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans SC',sans-serif;
  --font-pixel:'Press Start 2P',monospace;
  --font-mono:'SF Mono','Cascadia Code','Fira Code',Menlo,monospace;
}

/* ══════════════════════════════════════════════════════════════
   Global
   ══════════════════════════════════════════════════════════════ */
.gradio-container{
  background:var(--bg-primary)!important;color:var(--text-primary)!important;
  font-family:var(--font-body)!important;max-width:100%!important;
}
.dark .gradio-container{background:var(--bg-primary)!important;color:var(--text-primary)!important;}
/* Force light mode: override Gradio dark mode variables */
.dark{
  --body-background-fill:var(--bg-primary)!important;
  --background-fill-primary:#fff!important;
  --background-fill-secondary:#f7fafc!important;
  --block-background-fill:#fff!important;
  --block-border-color:var(--border)!important;
  --body-text-color:var(--text-primary)!important;
  --body-text-color-subdued:var(--text-secondary)!important;
  --input-background-fill:#fff!important;
  --button-secondary-background-fill:#fff!important;
  --color-accent-soft:var(--accent-blue-dim)!important;
  --panel-background-fill:#fff!important;
  --table-odd-background-fill:#f7fafc!important;
  --neutral-50:#fafaf8!important;
  --neutral-100:#f7fafc!important;
  --neutral-200:#edf2f7!important;
  --neutral-800:#2d3748!important;
  --neutral-900:#1a202c!important;
}

/* ══════════════════════════════════════════════════════════════
   Header — Pixel Title
   ══════════════════════════════════════════════════════════════ */
.lab-hdr{
  text-align:center;padding:16px 0 10px;
  background:linear-gradient(180deg,rgba(91,141,239,.04) 0%,transparent 100%);
  border-bottom:1px solid var(--border);
}
.lab-title{
  font-family:var(--font-pixel)!important;font-size:1.1em;
  color:var(--text-primary);letter-spacing:3px;
}
.lab-title span{color:var(--accent-blue);}
.lab-sub{
  font-family:var(--font-mono)!important;font-size:.65em;
  color:var(--text-muted);letter-spacing:4px;margin-top:4px;text-transform:uppercase;
}
.lab-version{
  font-family:var(--font-pixel)!important;font-size:.45em;
  color:var(--accent-orange);margin-top:2px;letter-spacing:1px;
}

/* ══════════════════════════════════════════════════════════════
   Pixel scan line (decorative)
   ══════════════════════════════════════════════════════════════ */
@keyframes pixel-scan{
  0%{background-position:0 0;}
  100%{background-position:200px 0;}
}
.pixel-scan-line{
  height:2px;
  background:repeating-linear-gradient(90deg,var(--accent-blue) 0,var(--accent-blue) 4px,transparent 4px,transparent 8px);
  background-size:200px 2px;animation:pixel-scan 3s linear infinite;opacity:.3;
}

/* ══════════════════════════════════════════════════════════════
   Tip Bar
   ══════════════════════════════════════════════════════════════ */
.tip{
  font-size:.82em;color:#718096;padding:8px 14px;background:#f7fafc;
  border-radius:var(--radius-sm);margin-bottom:10px;text-align:center;
  border:1px solid var(--border);
}

/* ══════════════════════════════════════════════════════════════
   Tab Labels
   ══════════════════════════════════════════════════════════════ */
button[role="tab"]{color:var(--text-primary)!important;font-weight:600!important;font-size:.95em!important;}
button[role="tab"][aria-selected="true"]{color:var(--accent-blue)!important;border-color:var(--accent-blue)!important;}

/* ══════════════════════════════════════════════════════════════
   Gradio Component Overrides
   ══════════════════════════════════════════════════════════════ */
.gr-group,.gr-panel{
  background:var(--bg-card)!important;border:1px solid var(--border)!important;
  border-radius:var(--radius)!important;box-shadow:var(--shadow-sm)!important;
}
textarea,input[type="text"]{
  background:var(--bg-secondary)!important;border:1px solid var(--border)!important;
  color:var(--text-primary)!important;border-radius:var(--radius-sm)!important;
  font-family:inherit!important;
}
textarea:focus,input:focus{
  border-color:var(--accent-blue)!important;
  box-shadow:0 0 0 3px var(--accent-blue-dim)!important;
}
label,.label-wrap span{color:#718096!important;font-weight:500!important;}
.prose h3,.markdown h3{color:var(--text-primary)!important;font-size:.9em!important;font-weight:600!important;}
.prose,.markdown{color:var(--text-secondary)!important;}

/* Buttons */
button.primary{
  background:var(--accent-blue)!important;border:none!important;color:#fff!important;
  border-radius:var(--radius-sm)!important;font-weight:600!important;
}
button.primary:hover{
  background:#4a7ae0!important;box-shadow:0 2px 8px rgba(91,141,239,.25)!important;
}
button.stop,button.secondary{
  background:#fff!important;border:1px solid var(--border)!important;
  color:#718096!important;border-radius:var(--radius-sm)!important;
}
button.stop:hover,button.secondary:hover{background:#f7fafc!important;border-color:#cbd5e0!important;}

/* ══════════════════════════════════════════════════════════════
   PDF Text Reader
   ══════════════════════════════════════════════════════════════ */
.txt-reader{
  max-height:750px;overflow-y:auto;background:var(--bg-secondary);
  border:1px solid var(--border);border-radius:var(--radius);
  padding:16px 20px;scroll-behavior:smooth;
}
.txt-empty{color:var(--text-muted);font-size:.84em;padding:20px;text-align:center;}
.txt-page{margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #edf2f7;}
.txt-page:last-child{border-bottom:none;margin-bottom:0;padding-bottom:0;}
.txt-page-hdr{
  font-family:var(--font-pixel)!important;font-size:.55em;font-weight:400;
  color:var(--accent-blue);text-transform:uppercase;letter-spacing:2px;
  margin-bottom:8px;padding:4px 8px;background:var(--accent-blue-dim);
  border-radius:4px;display:inline-block;
}
.txt-para{
  font-size:.9em;color:var(--text-primary);line-height:1.85;margin:0 0 4px;
  font-family:Georgia,'Noto Serif SC','Times New Roman',serif;
  cursor:pointer;padding:6px 8px;border-radius:var(--radius-sm);
  transition:all .2s;border-left:3px solid transparent;
}
.txt-para:hover{background:#f0f7ff;border-left-color:#cbd5e0;}
.txt-para.selected{background:#dbeafe;border-left-color:var(--accent-blue);
  box-shadow:inset 0 0 0 1px rgba(91,141,239,.15);}
.txt-para::selection{background:#bfdbfe;color:#1e3a5f;}

/* ══════════════════════════════════════════════════════════════
   Note Cards
   ══════════════════════════════════════════════════════════════ */
.nt-wrap{display:flex;flex-direction:column;gap:8px;max-height:600px;overflow-y:auto;}
.nt{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);
  padding:10px 12px;transition:box-shadow .2s,max-height .3s;cursor:default;}
.nt:hover{box-shadow:var(--shadow-md);}
.nt-top{display:flex;align-items:center;gap:8px;margin-bottom:6px;font-size:.8em;flex-wrap:wrap;}
.nt-badge{font-weight:600;color:var(--accent-blue);background:var(--accent-blue-dim);
  padding:2px 8px;border-radius:4px;font-size:.85em;}
.nt-page{color:var(--text-muted);font-size:.85em;}
.nt-page:hover{color:var(--accent-blue);text-decoration:underline;}
.nt-ts{color:#cbd5e0;font-size:.8em;margin-left:auto;}
.nt-body{font-size:.88em;color:var(--text-secondary);line-height:1.5;
  transition:max-height .3s ease,opacity .2s;}
.nt-annotation{font-size:.82em;color:var(--accent-blue);line-height:1.4;
  margin-top:4px;padding:3px 8px;background:var(--accent-blue-dim);
  border-radius:var(--radius-sm);border-left:2px solid var(--accent-blue);}

/* Note card expand/collapse */
.nt-collapsed .nt-body{max-height:60px;overflow:hidden;position:relative;}
.nt-collapsed .nt-body::after{content:'';position:absolute;bottom:0;left:0;right:0;
  height:24px;background:linear-gradient(transparent,var(--bg-card));}
.nt-expand-btn{font-size:.72em;color:var(--accent-blue);cursor:pointer;
  padding:2px 6px;border-radius:4px;transition:background .15s;margin-left:auto;}
.nt-expand-btn:hover{background:var(--accent-blue-dim);}
.nt-expanded .nt-body{max-height:none;overflow:visible;}
.nt-expanded .nt-body::after{display:none;}

/* ══════════════════════════════════════════════════════════════
   Organize
   ══════════════════════════════════════════════════════════════ */
.org-wrap{display:flex;flex-direction:column;gap:4px;}
.org-summary{font-size:.82em;color:#718096;font-weight:600;padding-bottom:6px;
  border-bottom:1px solid var(--border);margin-bottom:4px;}
.org-item{display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:var(--radius-sm);
  font-size:.84em;background:var(--bg-card);border:1px solid #f0f0f0;transition:background .15s;}
.org-item:hover{background:#f7fafc;}
.org-icon{font-size:1em;flex-shrink:0;}
.org-preview{color:var(--text-secondary);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}

/* ══════════════════════════════════════════════════════════════
   Classified Note Cards
   ══════════════════════════════════════════════════════════════ */
.cn-wrap{display:flex;flex-direction:column;gap:10px;}
.cn-card{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);
  padding:12px 14px;box-shadow:var(--shadow-sm);transition:box-shadow .2s,max-height .3s;cursor:default;}
.cn-card:hover{box-shadow:var(--shadow-md);}
.cn-top{display:flex;align-items:center;gap:8px;margin-bottom:6px;}
.cn-cat{font-size:.75em;font-weight:600;padding:2px 10px;border-radius:12px;letter-spacing:.5px;}
.cn-idx{font-size:.72em;color:var(--text-muted);font-family:var(--font-mono);margin-left:auto;}
.cn-comment{font-size:.88em;color:var(--text-secondary);line-height:1.5;margin-bottom:6px;}
.cn-body{font-size:.88em;color:var(--text-primary);line-height:1.6;margin-bottom:6px;
  padding:8px 10px;background:#f7fafc;border-radius:var(--radius-sm);border-left:3px solid var(--border);}
.cn-page{font-size:.75em;color:var(--text-muted);margin-bottom:4px;}
.cn-tags{display:flex;flex-wrap:wrap;gap:4px;}
.cn-tag{font-size:.72em;color:var(--accent-blue);background:var(--accent-blue-dim);
  padding:2px 8px;border-radius:4px;font-weight:500;}

/* Summary card */
.summary-card{background:linear-gradient(135deg,#f7fafc,#eef3ff);border:1px solid #d4e0f7;
  border-radius:var(--radius);padding:14px 16px;margin-bottom:10px;}
.summary-hdr{display:flex;align-items:center;gap:8px;margin-bottom:8px;}
.summary-badge{font-size:.75em;font-weight:600;color:#fff;background:var(--accent-blue);
  padding:2px 10px;border-radius:12px;}
.summary-domain{font-size:.78em;color:#718096;}
.summary-body{font-size:.88em;color:var(--text-primary);line-height:1.6;}

/* ══════════════════════════════════════════════════════════════
   Knowledge Tree — Expanded detail cards
   ══════════════════════════════════════════════════════════════ */
.kt-wrap{display:flex;flex-direction:column;gap:4px;max-height:700px;overflow-y:auto;}
.kt-node{display:flex;flex-direction:column;gap:4px;padding:8px 10px;border-radius:var(--radius-sm);
  cursor:pointer;transition:background .15s;font-size:.84em;
  border:1px solid transparent;margin-left:var(--kt-indent,0px);}
.kt-node:hover{background:#f0f7ff;border-color:#e2e8f0;}
.kt-node-header{display:flex;align-items:center;gap:6px;}
.kt-icon{font-size:1em;flex-shrink:0;}
.kt-cat{font-size:.68em;padding:1px 6px;border-radius:8px;font-weight:600;}
.kt-label{color:var(--text-primary);font-weight:600;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.kt-detail{font-size:.82em;color:var(--text-secondary);line-height:1.5;padding:4px 0 2px 22px;
  border-left:2px solid #edf2f7;margin-left:8px;}
.kt-tags{display:flex;flex-wrap:wrap;gap:3px;padding-left:22px;margin-left:8px;}
.kt-tag-item{font-size:.68em;color:var(--accent-purple);background:rgba(159,122,234,.08);
  padding:1px 6px;border-radius:4px;}

/* ══════════════════════════════════════════════════════════════
   File List (replaces dropdown)
   ══════════════════════════════════════════════════════════════ */
.file-list{display:flex;flex-direction:column;gap:2px;max-height:200px;overflow-y:auto;}
.file-item{display:flex;align-items:center;gap:8px;padding:6px 10px;border-radius:var(--radius-sm);
  cursor:pointer;font-size:.84em;border:1px solid transparent;transition:all .15s;}
.file-item:hover{background:#f0f7ff;border-color:#e2e8f0;}
.file-item.active{background:var(--accent-blue-dim);border-color:var(--accent-blue);color:var(--accent-blue);font-weight:600;}
.file-item-icon{font-size:1em;flex-shrink:0;}
.file-item-name{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}

/* ══════════════════════════════════════════════════════════════
   Stats Bar
   ══════════════════════════════════════════════════════════════ */
.stats-row{display:flex;flex-wrap:wrap;gap:6px;}
.si{display:flex;align-items:center;gap:5px;background:var(--bg-card);border:1px solid var(--border);
  border-radius:var(--radius-sm);padding:5px 10px;font-size:.82em;flex:1;min-width:70px;}
.si-l{color:var(--text-muted);font-size:.78em;flex:1;}
.si-v{font-weight:700;color:var(--accent-blue);font-family:var(--font-mono);}

/* ══════════════════════════════════════════════════════════════
   Agent Status
   ══════════════════════════════════════════════════════════════ */
.agent-st{font-size:.82em;color:#718096;font-family:var(--font-mono);}

/* ══════════════════════════════════════════════════════════════
   Search
   ══════════════════════════════════════════════════════════════ */
.search-result{background:#fffbeb;border:1px solid #fcd34d;border-radius:var(--radius-sm);
  padding:8px 12px;margin-bottom:8px;}
.search-result-count{font-size:.82em;color:#92400e;font-weight:600;}
.search-doc-match{font-size:.8em;color:var(--text-secondary);padding:4px 0;
  border-top:1px solid #fde68a;margin-top:4px;line-height:1.4;word-break:break-all;}
.search-doc-match b{color:var(--text-primary);}

/* ══════════════════════════════════════════════════════════════
   Knowledge Graph Container
   ══════════════════════════════════════════════════════════════ */
.graph-container{width:100%;height:600px;border:1px solid var(--border);
  border-radius:var(--radius);background:var(--bg-secondary);}
.graph-empty{display:flex;align-items:center;justify-content:center;
  height:100%;color:var(--text-muted);font-size:.9em;}

/* ══════════════════════════════════════════════════════════════
   Node Detail Panel
   ══════════════════════════════════════════════════════════════ */
.node-detail{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:16px;}
.node-detail-header{display:flex;align-items:center;gap:8px;margin-bottom:12px;
  padding-bottom:8px;border-bottom:1px solid #edf2f7;}
.node-detail-id{font-family:var(--font-mono);font-size:.8em;color:var(--text-muted);}
.node-detail-type{font-size:.75em;font-weight:600;padding:2px 8px;border-radius:4px;}
.node-detail-type.domain{background:#e6f0ff;color:var(--accent-blue);}
.node-detail-type.document{background:#e6ffed;color:var(--accent-green);}
.node-detail-type.note{background:#fefce8;color:#d69e2e;}
.node-detail-type.tag{background:#f3e8ff;color:var(--accent-purple);}
.node-detail-content{font-size:.9em;color:var(--text-primary);line-height:1.6;margin-bottom:12px;}
.node-cat-row{margin-bottom:8px;}
.node-comment{font-size:.84em;color:#718096;font-style:italic;margin-bottom:8px;
  padding:6px 10px;background:#f7fafc;border-radius:var(--radius-sm);}

/* ══════════════════════════════════════════════════════════════
   Writing Toolbar
   ══════════════════════════════════════════════════════════════ */
.write-toolbar{display:flex;flex-wrap:wrap;gap:2px;padding:6px 8px;background:#f7fafc;
  border:1px solid var(--border);border-radius:var(--radius-sm) var(--radius-sm) 0 0;
  border-bottom:none;}
.write-toolbar-btn{padding:4px 8px;border:1px solid transparent;border-radius:4px;
  cursor:pointer;font-size:.82em;color:var(--text-secondary);background:transparent;
  transition:all .15s;font-family:var(--font-body);min-width:28px;text-align:center;}
.write-toolbar-btn:hover{background:#fff;border-color:var(--border);color:var(--text-primary);}
.write-toolbar-btn.active{background:var(--accent-blue-dim);color:var(--accent-blue);
  border-color:rgba(91,141,239,.2);}
.write-toolbar-sep{width:1px;height:20px;background:var(--border);margin:0 4px;align-self:center;}

/* ══════════════════════════════════════════════════════════════
   Scrollbar
   ══════════════════════════════════════════════════════════════ */
::-webkit-scrollbar{width:5px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:#cbd5e0;border-radius:4px;}
::-webkit-scrollbar-thumb:hover{background:var(--text-muted);}

/* ══════════════════════════════════════════════════════════════
   Hidden JS communication textboxes
   ══════════════════════════════════════════════════════════════ */
#highlight-action-input, #translate-action-input, #translate-result-input,
#pdf-selector-hidden, #ai-ask-input, #selected-node-input{
  position:absolute!important;width:1px!important;height:1px!important;
  overflow:hidden!important;opacity:0!important;pointer-events:none!important;
  padding:0!important;margin:0!important;border:0!important;
  clip:rect(0,0,0,0)!important;
}

/* ══════════════════════════════════════════════════════════════
   Empty states
   ══════════════════════════════════════════════════════════════ */
.nc-empty{color:var(--text-muted);font-size:.84em;padding:16px;text-align:center;}

/* ══════════════════════════════════════════════════════════════
   Pagination
   ══════════════════════════════════════════════════════════════ */
.page-nav{display:flex;align-items:center;justify-content:center;gap:12px;padding:8px 0;margin-bottom:8px;}
.page-indicator{font-family:var(--font-mono);font-size:.8em;color:#718096;font-weight:500;}

/* ══════════════════════════════════════════════════════════════
   Floating Popup Menu
   ══════════════════════════════════════════════════════════════ */
#txt-popup{position:fixed;z-index:9999;background:var(--bg-card);
  border-radius:var(--radius);box-shadow:var(--shadow-md);
  padding:6px 10px;display:none;align-items:center;gap:6px;
  border:1px solid var(--border);flex-wrap:wrap;max-width:340px;}
#txt-popup.show{display:flex!important;}
.popup-color-btn{width:24px;height:24px;border-radius:50%;border:2px solid transparent;
  cursor:pointer;transition:transform .15s;flex-shrink:0;}
.popup-color-btn:hover{transform:scale(1.25);border-color:rgba(0,0,0,.2);}
.popup-action-btn{font-size:.78em;padding:4px 10px;border-radius:var(--radius-sm);
  border:1px solid var(--border);background:#f7fafc;cursor:pointer;
  color:var(--text-secondary);white-space:nowrap;transition:all .15s;}
.popup-action-btn:hover{background:var(--accent-blue-dim);color:var(--accent-blue);border-color:var(--accent-blue);}
.popup-divider{width:1px;height:20px;background:var(--border);flex-shrink:0;}
.popup-translate-result{font-size:.82em;color:var(--text-primary);padding:6px 8px;
  background:#f0f7ff;border-radius:var(--radius-sm);width:100%;margin-top:4px;
  line-height:1.5;border:1px solid #d4e0f7;}
.popup-annotation{width:100%;margin:4px 0 2px;padding:4px 8px;border:1px solid var(--border);
  border-radius:var(--radius-sm);font-size:.78em;outline:none;box-sizing:border-box;
  font-family:inherit;color:var(--text-primary);background:#fff;}
.popup-annotation:focus{border-color:var(--accent-blue);box-shadow:0 0 0 2px var(--accent-blue-dim);}
.popup-annotation::placeholder{color:var(--text-muted);}
.popup-toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);
  background:var(--text-primary);color:#fff;padding:6px 16px;border-radius:20px;
  font-size:.82em;z-index:10000;opacity:0;transition:opacity .3s;}
.popup-toast.show{opacity:1;}

/* ══════════════════════════════════════════════════════════════
   Highlight Marks (persisted highlights)
   ══════════════════════════════════════════════════════════════ */
mark.hl-red{background:#fed7d7;color:inherit;border-radius:3px;padding:0 2px;cursor:pointer;transition:all .15s;}
mark.hl-yellow{background:#fefcbf;color:inherit;border-radius:3px;padding:0 2px;cursor:pointer;transition:all .15s;}
mark.hl-green{background:#c6f6d5;color:inherit;border-radius:3px;padding:0 2px;cursor:pointer;transition:all .15s;}
mark.hl-purple{background:#e9d8fd;color:inherit;border-radius:3px;padding:0 2px;cursor:pointer;transition:all .15s;}
mark.hl-orange{background:#fde68a;color:inherit;border-radius:3px;padding:0 2px;cursor:pointer;transition:all .15s;}
mark.hl-blue{background:#bfdbfe;color:inherit;border-radius:3px;padding:0 2px;cursor:pointer;transition:all .15s;}

mark[data-note-id]:hover{filter:brightness(0.92);box-shadow:0 0 0 2px rgba(0,0,0,.1);}
mark[data-note-id].highlight-focus{animation:highlight-pulse 1s ease-in-out 2;box-shadow:0 0 0 3px var(--accent-blue);}

@keyframes highlight-pulse{
  0%,100%{box-shadow:0 0 0 2px rgba(91,141,239,.3);}
  50%{box-shadow:0 0 0 6px rgba(91,141,239,.5);}
}

.nt-badge.hl-red{color:var(--accent-red);background:#fed7d7;}
.nt-badge.hl-yellow{color:#d69e2e;background:#fefcbf;}
.nt-badge.hl-green{color:var(--accent-green);background:#c6f6d5;}
.nt-badge.hl-purple{color:var(--accent-purple);background:#e9d8fd;}
.nt-badge.hl-orange{color:#d97706;background:#fde68a;}
.nt-badge.hl-blue{color:var(--accent-blue);background:#bfdbfe;}
"""

# Header HTML — Pixel styled on white
HEADER_HTML = """
<div class='lab-hdr'>
  <div class='lab-title'><span>Atomic</span> Lab</div>
  <div class='lab-sub'>Read &middot; Organize &middot; Write</div>
  <div class='pixel-scan-line'></div>
</div>
"""
