# -*- coding: utf-8 -*-
"""
正文零标记残留扫描（对应 SKILL.md 输出规范"正文零标记残留（最高优先级交付纪律）"）

检查正文（意见陈述书初稿 / 权利要求书替换页 / 修改对照页等交付物）是否含
不应出现在递交文件中的内容：
  1. 待核实类标记：待核实 / 待补 / 占位 / 待填 / 待确认 / 待定 / TODO / FIXME / XXX
  2. 占位符：<尖括号内容> {花括号内容} 连续下划线（____） 【待填内容】
  3. 内部框架泄漏：references/ 路径、temp_opinion、Step N、SKILL.md、skill 名称等
  4. 括号执行指令：如"（逐字引用…）""（加载 references…）""（按模板…）"

支持直接扫描 .md/.txt；--include-docx 时对 .docx 解包扫描正文段落（纯标准库 zipfile）。
自定义关键词可用 --extra 追加（追加到待核实类）。

用法：
  python check_clean_markers.py --input 初稿.md
  python check_clean_markers.py --dir 输出目录 --include-docx
  python check_clean_markers.py --input 初稿.md --extra 自定义词1,自定义词2

退出码：0 = 通过（无残留）；1 = 检出残留（FAIL）
"""
import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PATTERNS = [
    ('待核实类标记', re.compile(r'待核实|待补|占位|待填|待确认|待定|TODO|FIXME|XXX')),
    ('占位符-尖括号', re.compile(r'<(?!/?u>)[^<>\n]{1,20}>')),
    ('占位符-花括号', re.compile(r'\{[^{}\n]{1,20}\}')),
    ('占位符-下划线', re.compile(r'_{2,}')),
    ('占位符-全角方括号', re.compile(r'【[^】\n]{1,15}】')),
    ('内部框架泄漏', re.compile(r'references/|temp_opinion|SKILL\.md|Step\s*[0-9]+|invention-patent-oa-assistant')),
    ('括号执行指令', re.compile(r'[（(][^（）()]{0,40}(逐字引用|加载|写入|暂存|按.{0,10}模板)[^（）()]{0,40}[）)]')),
]


# 豁免规则集中定义于 scripts/_exempt.py（与 check_ai_traces 共享，避免规则碎片化）。
# 本脚本**有意不采用** _exempt.apply_block_exempt（区块豁免）：占位符与执行指令
# 无论出现在哪个区块都不应出现在交付物中；若模板写法被判残留，应改模板而非放宽检查。
from _exempt import exempt_cats_for, is_cat_exempt


def scan_text(text, label, exempt_cats=()):
    hits = []
    for lineno, line in enumerate(text.split('\n'), 1):
        for cat, pat in PATTERNS:
            if is_cat_exempt(cat, exempt_cats):
                continue
            for m in pat.finditer(line):
                hits.append({'file': label, 'line': lineno, 'cat': cat,
                             'match': m.group(0)[:60], 'context': line.strip()[:100]})
    return hits


def scan_docx(path, exempt_cats=()):
    with zipfile.ZipFile(path) as zf:
        xml = zf.read('word/document.xml').decode('utf-8')
    hits = []
    for idx, para in enumerate(xml.split('</w:p>'), 1):
        text = re.sub(r'<[^>]+>', '', para).strip()
        if not text:
            continue
        for cat, pat in PATTERNS:
            if is_cat_exempt(cat, exempt_cats):
                continue
            for m in pat.finditer(text):
                hits.append({'file': str(path), 'line': idx, 'cat': cat,
                             'match': m.group(0)[:60], 'context': text[:100]})
    return hits


def collect_files(args):
    files = []
    for p in args.input:
        files.append(Path(p))
    if args.dir:
        d = Path(args.dir)
        for ext in ('.md', '.txt'):
            files.extend(sorted(d.glob('*' + ext)))
        if args.include_docx:
            files.extend(sorted(d.glob('*.docx')))
    return files


def main():
    ap = argparse.ArgumentParser(description='正文零标记残留扫描（SKILL.md 输出规范最高优先级纪律）')
    ap.add_argument('--input', '-i', action='append', default=[], help='待扫描文件路径（可多次）')
    ap.add_argument('--dir', '-d', help='扫描目录下全部 .md/.txt（--include-docx 时含 .docx）')
    ap.add_argument('--include-docx', action='store_true', help='对目录内的 .docx 解包扫描正文')
    ap.add_argument('--extra', default='', help='追加自定义关键词，逗号分隔（归入待核实类）')
    ap.add_argument('--json', action='store_true', help='额外输出 JSON 报告')
    args = ap.parse_args()

    if not args.input and not args.dir:
        ap.error('至少提供 --input 或 --dir')

    if args.extra:
        extra = re.compile('|'.join(re.escape(x.strip()) for x in args.extra.split(',') if x.strip()))
        PATTERNS.insert(0, ('待核实类标记(自定义)', extra))

    files = collect_files(args)
    if not files:
        print('未找到可扫描的文件。')
        raise SystemExit(2)

    all_hits = []
    for f in files:
        exempt = exempt_cats_for(f.name)
        try:
            if f.suffix.lower() == '.docx':
                hits = scan_docx(f, exempt)
            else:
                hits = scan_text(f.read_text(encoding='utf-8', errors='replace'), str(f), exempt)
        except (zipfile.BadZipFile, KeyError) as e:
            print('ERROR: 无法读取 %s（%s）' % (f, e))
            raise SystemExit(2)
        if hits:
            print('文件：%s' % f)
            for h in hits:
                print('  [%s] 第 %d 行：%s' % (h['cat'], h['line'], h['context']))
        all_hits.extend(hits)

    total_files = len(files)
    bad_files = len({h['file'] for h in all_hits})
    if all_hits:
        print('结果：FAIL —— 检出 %d 处残留（涉及 %d/%d 个文件）' % (len(all_hits), bad_files, total_files))
        print('处理：删除或改写残留内容后重新检查；无法核实的信息统一登记到《附件·答复辅助材料汇总》')
        print('之"待核实事项清单"节，正文不得出现任何标记。')
        if args.json:
            print(json.dumps({'files': total_files, 'hits': all_hits, 'pass': False},
                             ensure_ascii=False, indent=2))
        raise SystemExit(1)

    print('结果：PASS —— 扫描 %d 个文件，无标记残留。' % total_files)
    if args.json:
        print(json.dumps({'files': total_files, 'hits': [], 'pass': True}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
