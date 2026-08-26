# -*- coding: utf-8 -*-
"""
专利意见陈述书 docx 生成器（纯标准库实现，零第三方依赖）
输入：Markdown（意见陈述书初稿 md），输出：行业通行格式的 .docx

排版规范（行业通行格式）：
- 字体：正文华文仿宋（回退仿宋），西文 Times New Roman
- 字号：正文小四(12pt)、一级标题三号(16pt)、二级标题四号(14pt)、三级小四加粗
- 首行缩进 2 字符、1.5 倍行距
- 编号体系：md 标题层级映射（## 一、→一级；### （一）→二级；#### 1.→三级）
- 支持内联：**加粗**、~~删除线~~、<u>下划线</u>、`代码`
用法：python generate_docx.py --input 初稿.md --output 初稿.docx
"""
import argparse
import re
import zipfile
from xml.sax.saxutils import escape
from pathlib import Path

NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def runs(text):
    """把内联 markdown 拆成 (文本, 样式) run 列表。样式: b=加粗 s=删除线 u=下划线 c=代码"""
    out = []
    pattern = re.compile(r'(\*\*.+?\*\*|~~.+?~~|<u>.+?</u>|`.+?`)')
    for seg in pattern.split(text):
        if not seg:
            continue
        if seg.startswith('**') and seg.endswith('**'):
            out.append((seg[2:-2], 'b'))
        elif seg.startswith('~~') and seg.endswith('~~'):
            out.append((seg[2:-2], 's'))
        elif seg.startswith('<u>') and seg.endswith('</u>'):
            out.append((seg[3:-4], 'u'))
        elif seg.startswith('`') and seg.endswith('`'):
            out.append((seg[1:-1], 'c'))
        else:
            out.append((seg, ''))
    return out


def run_xml(text, style, size=24, bold=False):
    rpr = [f'<w:rFonts w:ascii="Times New Roman" w:eastAsia="华文仿宋"/>', f'<w:sz w:val="{size}"/>']
    if bold or 'b' in style:
        rpr.append('<w:b/>')
    if 's' in style:
        rpr.append('<w:strike/>')
    if 'u' in style:
        rpr.append('<w:u w:val="single"/>')
    return f'<w:r><w:rPr>{"".join(rpr)}</w:rPr><w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def para_xml(segments, style='body', size=24, bold=False):
    """style: body(正文缩进2字符) / plain(无缩进) / center(居中)"""
    ppr = ['<w:spacing w:line="360" w:lineRule="auto"/>']
    if style == 'body':
        ppr.append('<w:ind w:firstLineChars="200" w:firstLine="480"/>')
    elif style == 'center':
        ppr.append('<w:jc w:val="center"/>')
    runs_xml = ''.join(run_xml(t, s, size, bold) for t, s in segments)
    return f'<w:p><w:pPr>{"".join(ppr)}</w:pPr>{runs_xml}</w:p>'


def table_xml(rows):
    borders = ('<w:tblBorders>'
               + ''.join(f'<w:{side} w:val="single" w:sz="4" w:color="999999"/>'
                         for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'))
               + '</w:tblBorders>')
    # 按每列最大内容长度分配列宽（A4 可用宽约 9026 twips）
    n_cols = max(len(r) for r in rows)
    weights = []
    for c in range(n_cols):
        weights.append(max(len(str(r[c])) for r in rows if c < len(r)))
    total_w = max(sum(weights), 1)
    widths = [max(int(9026 * w / total_w), 500) for w in weights]
    grid = ''.join(f'<w:gridCol w:w="{wd}"/>' for wd in widths)
    xml = ['<w:tbl><w:tblPr><w:tblW w:w="9026" w:type="dxa"/>'
           '<w:tblLayout w:type="fixed"/>' + borders + '</w:tblPr>'
           f'<w:tblGrid>{grid}</w:tblGrid>']
    for r_idx, row in enumerate(rows):
        xml.append('<w:tr>')
        for c_idx, cell in enumerate(row[:n_cols]):
            segs = runs(cell)  # 解析单元格内联标记（**加粗/~~删除线~~/<u>下划线</u>/`代码`）
            xml.append(f'<w:tc><w:tcPr><w:tcW w:w="{widths[c_idx]}" w:type="dxa"/></w:tcPr>'
                       + para_xml(segs, style='plain', size=21, bold=(r_idx == 0))
                       + '</w:tc>')
        xml.append('</w:tr>')
    xml.append('</w:tbl>')
    return ''.join(xml)


def convert(md_text):
    lines = md_text.split('\n')
    out, i, n = [], 0, len(lines)
    # 跳过 frontmatter
    if lines and lines[0].strip() == '---':
        i = 1
        while i < n and lines[i].strip() != '---':
            i += 1
        i += 1
    while i < n:
        ln = lines[i].rstrip()
        if not ln.strip():
            i += 1
            continue
        m = re.match(r'^(#{1,4})\s+(.*)$', ln)
        if m:
            lvl = len(m.group(1))
            if lvl == 1:
                out.append(para_xml(runs(m.group(2)), 'center', 32, True))
            elif lvl == 2:
                out.append(para_xml(runs(m.group(2)), 'plain', 28, True))
            elif lvl == 3:
                out.append(para_xml(runs(m.group(2)), 'plain', 24, True))
            else:
                out.append(para_xml(runs(m.group(2)), 'body', 24, True))
            i += 1
            continue
        if ln.strip().startswith('|') and i + 1 < n and re.match(r'^\s*\|[\s:|-]+\|\s*$', lines[i + 1]):
            rows = []
            hdr = [c.strip() for c in ln.strip().strip('|').split('|')]
            rows.append(hdr)
            i += 2
            while i < n and lines[i].strip().startswith('|'):
                rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')])
                i += 1
            out.append(table_xml(rows))
            continue
        if re.match(r'^\s*[-*]\s+', ln):
            items = []
            while i < n and re.match(r'^\s*[-*]\s+', lines[i]):
                items.append(re.sub(r'^\s*[-*]\s+', '', lines[i]))
                i += 1
            for it in items:
                out.append(para_xml(runs('• ' + it), 'body', 24))
            continue
        if re.match(r'^\s*\d+\.\s+', ln):
            items = []
            while i < n and re.match(r'^\s*\d+\.\s+', lines[i]):
                items.append(re.sub(r'^\s*\d+\.\s+', '', lines[i]))
                i += 1
            for idx, it in enumerate(items, 1):
                out.append(para_xml(runs(f'{idx}. {it}'), 'body', 24))
            continue
        para = [ln.strip()]
        i += 1
        while i < n and lines[i].strip() and not lines[i].startswith('#') \
                and not lines[i].strip().startswith('|') and not re.match(r'^\s*[-*]', lines[i]) \
                and not re.match(r'^\s*\d+\.\s+', lines[i]):
            para.append(lines[i].strip())
            i += 1
        out.append(para_xml(runs(' '.join(para)), 'body', 24))
    return '\n'.join(out)


CONTENT_TYPES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''

RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

DOC_RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>'''


def build_docx(md_text):
    body = convert(md_text)
    document = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                f'<w:document {NS}><w:body>{body}\n'
                f'<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" '
                f'w:bottom="1440" w:left="1440" w:header="851" w:footer="992" w:gutter="0"/></w:sectPr>'
                f'</w:body></w:document>')
    return {
        '[Content_Types].xml': CONTENT_TYPES,
        '_rels/.rels': RELS,
        'word/document.xml': document,
        'word/_rels/document.xml.rels': DOC_RELS,
    }


def main():
    ap = argparse.ArgumentParser(description='专利意见陈述书 docx 生成器（纯标准库）')
    ap.add_argument('--input', '-i', required=True, help='输入 Markdown 文件路径')
    ap.add_argument('--output', '-o', required=True, help='输出 docx 文件路径')
    ap.add_argument('--skip-check', action='store_true', help='跳过必备要素完整性校验（不推荐）')
    args = ap.parse_args()
    md_text = Path(args.input).read_text(encoding='utf-8')

    # 必备要素完整性校验（意见陈述书）：敬语开头段 + 结论收尾段（机检硬门槛，缺失即拒绝输出）
    if not args.skip_check and '意见陈述书' in Path(args.input).name:
        missing = []
        if '尊敬的审查员' not in md_text or '您好！' not in md_text:
            missing.append('敬语开头段（"尊敬的审查员：您好！……"）')
        if '恳请接受本意见陈述' not in md_text or '早日批准本申请获得专利权' not in md_text:
            missing.append('结论收尾段（"恳请接受本意见陈述……早日批准本申请获得专利权"）')
        if missing:
            print('ERROR: 意见陈述书缺少必备要素：' + '、'.join(missing))
            print('请先补写后再生成（参见 SKILL.md Step 9 必备要素硬清单）。')
            raise SystemExit(1)

    parts = build_docx(md_text)
    with zipfile.ZipFile(args.output, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, content in parts.items():
            zf.writestr(name, content)
    print('OK ->', args.output)


if __name__ == '__main__':
    main()
