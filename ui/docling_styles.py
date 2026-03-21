"""
Docling Viewer Styles
=====================
Docling PDF渲染器的CSS样式
"""

DOCLING_VIEWER_CSS = """
/* Docling Viewer 基础样式 */
.docling-viewer {
    font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    color: #333;
    max-width: 900px;
    margin: 0 auto;
    padding: 20px;
    background: #fff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

/* 文档头部 */
.doc-header {
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 20px;
    margin-bottom: 30px;
}

.doc-title {
    font-size: 28px;
    font-weight: 700;
    color: #1a202c;
    margin: 0 0 15px 0;
    line-height: 1.3;
}

.doc-metadata {
    font-size: 13px;
    color: #718096;
    display: flex;
    flex-wrap: wrap;
    gap: 15px;
}

.meta-item {
    background: #f7fafc;
    padding: 4px 10px;
    border-radius: 4px;
}

/* 章节样式 */
.doc-section {
    margin-bottom: 30px;
    padding: 20px;
    background: #fff;
    border-radius: 8px;
    border-left: 4px solid #4299e1;
}

.section-heading {
    font-size: 20px;
    font-weight: 600;
    color: #2d3748;
    margin: 0 0 15px 0;
    padding-bottom: 10px;
    border-bottom: 1px solid #e2e8f0;
}

/* 段落样式 */
.doc-paragraph {
    margin: 0 0 16px 0;
    text-align: justify;
    text-indent: 2em;
}

/* 列表样式 */
.doc-list {
    margin: 16px 0;
    padding-left: 24px;
}

.doc-list li {
    margin-bottom: 8px;
    line-height: 1.6;
}

/* 表格样式 */
.tables-section {
    margin-top: 40px;
}

.table-wrapper {
    margin: 20px 0;
    overflow-x: auto;
}

.table-caption {
    font-size: 14px;
    font-weight: 600;
    color: #4a5568;
    margin-bottom: 10px;
    padding: 8px 12px;
    background: #f7fafc;
    border-left: 3px solid #4299e1;
}

.doc-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}

.doc-table thead {
    background: #f7fafc;
}

.doc-table th {
    font-weight: 600;
    color: #2d3748;
    padding: 12px;
    text-align: left;
    border-bottom: 2px solid #e2e8f0;
}

.doc-table td {
    padding: 10px 12px;
    border-bottom: 1px solid #e2e8f0;
}

.doc-table tbody tr:hover {
    background: #f7fafc;
}

/* 表格样式变体 */
.doc-table.grid {
    border: 1px solid #e2e8f0;
}

.doc-table.grid th,
.doc-table.grid td {
    border: 1px solid #e2e8f0;
}

.doc-table.striped tbody tr:nth-child(even) {
    background: #f7fafc;
}

/* 高亮样式 */
mark {
    padding: 2px 4px;
    border-radius: 3px;
    cursor: pointer;
    transition: all 0.2s;
}

mark:hover {
    filter: brightness(0.95);
}

.hl-yellow {
    background: #fef3c7;
    color: #92400e;
}

.hl-red {
    background: #fee2e2;
    color: #991b1b;
}

.hl-green {
    background: #d1fae5;
    color: #065f46;
}

.hl-blue {
    background: #dbeafe;
    color: #1e40af;
}

.hl-purple {
    background: #e9d5ff;
    color: #6b21a8;
}

.hl-orange {
    background: #ffedd5;
    color: #9a3412;
}

/* 图片区域 */
.figures-section {
    margin-top: 40px;
    padding: 20px;
    background: #f7fafc;
    border-radius: 8px;
}

.text-muted {
    color: #a0aec0;
}

/* 页脚 */
.doc-footer {
    margin-top: 40px;
    padding-top: 20px;
    border-top: 1px solid #e2e8f0;
    text-align: center;
}

.parse-confidence {
    font-size: 12px;
    color: #718096;
    background: #f7fafc;
    padding: 4px 12px;
    border-radius: 12px;
}

/* 空状态 */
.doc-empty {
    text-align: center;
    padding: 60px 20px;
    color: #a0aec0;
}

/* 页码标记 */
[data-page]::before {
    content: attr(data-page);
    position: absolute;
    right: 10px;
    top: 10px;
    font-size: 11px;
    color: #a0aec0;
    background: #f7fafc;
    padding: 2px 8px;
    border-radius: 10px;
}

.doc-section {
    position: relative;
}

/* 打印样式 */
@media print {
    .docling-viewer {
        box-shadow: none;
        padding: 0;
    }
    
    mark {
        border: 1px solid #ccc;
    }
}

/* 响应式 */
@media (max-width: 768px) {
    .docling-viewer {
        padding: 15px;
    }
    
    .doc-title {
        font-size: 22px;
    }
    
    .section-heading {
        font-size: 18px;
    }
    
    .doc-table {
        font-size: 12px;
    }
}
"""


def get_docling_styles() -> str:
    """获取Docling viewer的CSS样式"""
    return f"<style>{DOCLING_VIEWER_CSS}</style>"
