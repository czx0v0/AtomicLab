"""
UI Styles
=========
CSS styles for Atomic Lab interface.
"""

CSS = """
/* ══════════════════════════════════════════════════════════════
   Global Styles
   ══════════════════════════════════════════════════════════════ */
.gradio-container{
  background:#fafaf8!important;color:#2d3748!important;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans SC',sans-serif!important;
  max-width:100%!important;
}
.dark .gradio-container{background:#fafaf8!important;color:#2d3748!important;}

/* ══════════════════════════════════════════════════════════════
   Header
   ══════════════════════════════════════════════════════════════ */
.lab-hdr{text-align:center;padding:10px 0 6px;}
.lab-title{font-size:1.2em;font-weight:700;color:#2d3748;letter-spacing:2px;}
.lab-title span{color:#5b8def;}
.lab-sub{font-size:.72em;color:#a0aec0;letter-spacing:1px;margin-top:2px;}

/* ══════════════════════════════════════════════════════════════
   Tip Bar
   ══════════════════════════════════════════════════════════════ */
.tip{font-size:.82em;color:#718096;padding:8px 14px;background:#f7fafc;
  border-radius:6px;margin-bottom:10px;text-align:center;border:1px solid #e2e8f0;}

/* ══════════════════════════════════════════════════════════════
   Tab Labels
   ══════════════════════════════════════════════════════════════ */
button[role="tab"]{color:#2d3748!important;font-weight:600!important;font-size:.95em!important;}
button[role="tab"][aria-selected="true"]{color:#5b8def!important;border-color:#5b8def!important;}

/* ══════════════════════════════════════════════════════════════
   Gradio Component Overrides
   ══════════════════════════════════════════════════════════════ */
.gr-group{background:#fff!important;border:1px solid #e2e8f0!important;border-radius:8px!important;box-shadow:0 1px 3px rgba(0,0,0,.04)!important;}
textarea,input[type="text"]{background:#fff!important;border:1px solid #e2e8f0!important;
  color:#2d3748!important;border-radius:6px!important;font-family:inherit!important;}
textarea:focus,input:focus{border-color:#5b8def!important;box-shadow:0 0 0 3px rgba(91,141,239,.12)!important;}
label,.label-wrap span{color:#718096!important;font-weight:500!important;}
button.primary{background:#5b8def!important;border:none!important;color:#fff!important;border-radius:6px!important;font-weight:600!important;}
button.primary:hover{background:#4a7ae0!important;box-shadow:0 2px 8px rgba(91,141,239,.25)!important;}
button.stop{background:#fff!important;border:1px solid #e2e8f0!important;color:#718096!important;border-radius:6px!important;}
button.stop:hover{background:#f7fafc!important;border-color:#cbd5e0!important;}
.prose h3,.markdown h3{color:#2d3748!important;font-size:.9em!important;font-weight:600!important;}
.prose,.markdown{color:#4a5568!important;}

/* ══════════════════════════════════════════════════════════════
   PDF Text Reader
   ══════════════════════════════════════════════════════════════ */
.txt-reader{max-height:750px;overflow-y:auto;background:#fff;border:1px solid #e2e8f0;
  border-radius:8px;padding:16px 20px;}
.txt-empty{color:#a0aec0;font-size:.84em;padding:20px;text-align:center;}
.txt-page{margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #edf2f7;}
.txt-page:last-child{border-bottom:none;margin-bottom:0;padding-bottom:0;}
.txt-page-hdr{font-size:.75em;font-weight:700;color:#5b8def;text-transform:uppercase;
  letter-spacing:1px;margin-bottom:8px;padding:4px 8px;background:#eef3ff;
  border-radius:4px;display:inline-block;}
.txt-para{font-size:.9em;color:#2d3748;line-height:1.75;margin:0 0 6px;
  font-family:Georgia,'Noto Serif SC','Times New Roman',serif;
  cursor:pointer;padding:4px 6px;border-radius:4px;transition:background .15s;}
.txt-para:hover{background:#f0f7ff;}
.txt-para.selected{background:#e6f0ff;border-left:3px solid #5b8def;}

/* ══════════════════════════════════════════════════════════════
   Note Cards (Tab 1)
   ══════════════════════════════════════════════════════════════ */
.nt-wrap{display:flex;flex-direction:column;gap:8px;max-height:520px;overflow-y:auto;}
.nt{background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px;
  transition:box-shadow .2s;}
.nt:hover{box-shadow:0 2px 8px rgba(0,0,0,.06);}
.nt-top{display:flex;align-items:center;gap:8px;margin-bottom:6px;font-size:.8em;}
.nt-badge{font-weight:600;color:#5b8def;background:#eef3ff;padding:2px 8px;border-radius:4px;font-size:.85em;}
.nt-page{color:#a0aec0;font-size:.85em;}
.nt-ts{color:#cbd5e0;font-size:.8em;margin-left:auto;}
.nt-body{font-size:.88em;color:#4a5568;line-height:1.5;}

/* ══════════════════════════════════════════════════════════════
   Organize Summary (Tab 2)
   ══════════════════════════════════════════════════════════════ */
.org-wrap{display:flex;flex-direction:column;gap:4px;}
.org-summary{font-size:.82em;color:#718096;font-weight:600;padding-bottom:6px;border-bottom:1px solid #e2e8f0;margin-bottom:4px;}
.org-item{display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:6px;font-size:.84em;
  background:#fff;border:1px solid #f0f0f0;transition:background .15s;}
.org-item:hover{background:#f7fafc;}
.org-icon{font-size:1em;flex-shrink:0;}
.org-preview{color:#4a5568;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}

/* ══════════════════════════════════════════════════════════════
   Atom Cards (Scrivener-style Index Cards)
   ══════════════════════════════════════════════════════════════ */
.nc-wrap{display:flex;flex-direction:column;gap:10px;}
.nc-meta{font-size:.78em;color:#a0aec0;padding-bottom:4px;}
.nc-empty{color:#a0aec0;font-size:.84em;padding:16px;text-align:center;}
.nc{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px;
  box-shadow:0 1px 4px rgba(0,0,0,.05);transition:box-shadow .2s,transform .15s;}
.nc:hover{box-shadow:0 4px 12px rgba(0,0,0,.08);transform:translateY(-1px);}
.nc-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;}
.nc-tag{font-size:.7em;font-weight:600;color:#5b8def;background:#eef3ff;padding:2px 8px;border-radius:4px;letter-spacing:.5px;}
.nc-code{font-size:.72em;color:#a0aec0;font-family:'SF Mono',Menlo,monospace;}
.nc-axiom{font-size:.95em;font-weight:600;color:#1a202c;line-height:1.45;margin-bottom:6px;}
.nc-detail{font-size:.82em;color:#718096;line-height:1.4;margin-bottom:2px;}
.nc-lbl{font-size:.75em;font-weight:600;color:#a0aec0;text-transform:uppercase;letter-spacing:.5px;margin-right:4px;}
.nc-bnd{font-style:italic;color:#a0aec0;}
.nc-foot{display:flex;align-items:center;gap:8px;margin-top:10px;padding-top:8px;border-top:1px solid #f0f0f0;}
.nc-src{font-size:.75em;color:#a0aec0;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}

/* ══════════════════════════════════════════════════════════════
   Stats Bar
   ══════════════════════════════════════════════════════════════ */
.stats-row{display:flex;flex-wrap:wrap;gap:6px;}
.si{display:flex;align-items:center;gap:5px;background:#fff;border:1px solid #e2e8f0;
  border-radius:6px;padding:5px 10px;font-size:.82em;flex:1;min-width:70px;}
.si-i{font-size:1em;}
.si-l{color:#a0aec0;font-size:.78em;flex:1;}
.si-v{font-weight:700;color:#2d3748;}

/* ══════════════════════════════════════════════════════════════
   Agent Status
   ══════════════════════════════════════════════════════════════ */
.agent-st{font-size:.82em;color:#718096;font-family:'SF Mono',Menlo,monospace;}

/* ══════════════════════════════════════════════════════════════
   Search Bar
   ══════════════════════════════════════════════════════════════ */
.search-bar{display:flex;gap:8px;margin-bottom:12px;}
.search-bar input{flex:1;}
.search-result{background:#fffbeb;border:1px solid #fcd34d;border-radius:6px;padding:8px 12px;margin-bottom:8px;}
.search-result-count{font-size:.82em;color:#92400e;font-weight:600;}

/* ══════════════════════════════════════════════════════════════
   Knowledge Graph Container
   ══════════════════════════════════════════════════════════════ */
.graph-container{width:100%;height:600px;border:1px solid #e2e8f0;border-radius:8px;background:#fff;}
.graph-empty{display:flex;align-items:center;justify-content:center;height:100%;color:#a0aec0;font-size:.9em;}

/* ══════════════════════════════════════════════════════════════
   Node Detail Panel
   ══════════════════════════════════════════════════════════════ */
.node-detail{background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:16px;}
.node-detail-header{display:flex;align-items:center;gap:8px;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid #edf2f7;}
.node-detail-id{font-family:'SF Mono',Menlo,monospace;font-size:.8em;color:#a0aec0;}
.node-detail-type{font-size:.75em;font-weight:600;padding:2px 8px;border-radius:4px;}
.node-detail-type.domain{background:#e6f0ff;color:#5b8def;}
.node-detail-type.atom{background:#e6ffed;color:#48bb78;}
.node-detail-type.note{background:#fefce8;color:#d69e2e;}
.node-detail-type.concept{background:#f3e8ff;color:#9f7aea;}
.node-detail-content{font-size:.9em;color:#2d3748;line-height:1.6;margin-bottom:12px;}
.node-annotations{margin-top:12px;padding-top:12px;border-top:1px solid #edf2f7;}
.node-annotation{background:#f7fafc;border-radius:6px;padding:8px 10px;margin-bottom:6px;font-size:.84em;}
.node-annotation-agent{font-size:.75em;color:#5b8def;font-weight:600;margin-bottom:4px;}

/* ══════════════════════════════════════════════════════════════
   Scrollbar
   ══════════════════════════════════════════════════════════════ */
::-webkit-scrollbar{width:5px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:#cbd5e0;border-radius:4px;}
::-webkit-scrollbar-thumb:hover{background:#a0aec0;}
"""

# Header HTML
HEADER_HTML = """
<div class='lab-hdr'>
  <div class='lab-title'><span>Atomic</span> Lab</div>
  <div class='lab-sub'>Read &middot; Organize &middot; Write</div>
</div>
"""
