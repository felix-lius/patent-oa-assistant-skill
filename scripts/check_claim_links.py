# -*- coding: utf-8 -*-
"""
引用链条闭合检查（对应 SKILL.md Step 8"合并后检查引用链条是否闭合"）

规则：修改合并权利要求后，每个从属权利要求的引用基础必须存在、且只能引用
在前面的权项（"如权利要求 1 所述""根据权利要求 1 或 2 所述"等）。
缺失引用基础（悬空）或引用不存在的编号 → 硬性 FAIL（提交后会被形式审查驳回）。

用法：
  python check_claim_links.py --input 权利要求书替换页.md
  python check_claim_links.py --dir 输出目录

退出码：0 = 引用链条闭合；1 = 存在悬空/错误引用（FAIL）
"""
import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

CLAIM_START = re.compile(r'^\s*(\d+)\s*[.、．]\s*', re.M)
REF_RE = re.compile(r'(?:根据|如|按照)\s*权利要求\s*([0-9]+(?:\s*[、和或及至\-]+\s*[0-9]+)*)\s*所述')


def extract_claims(text):
    """按行首编号切分权项：{编号: 文本块}。"""
    claims = {}
    cur_no, cur = None, []
    for ln in text.split('\n'):
        m = CLAIM_START.match(ln)
        if m:
            if cur_no is not None:
                claims[cur_no] = '\n'.join(cur)
            cur_no = int(m.group(1))
            cur = [ln]
        elif cur_no is not None:
            cur.append(ln)
    if cur_no is not None:
        claims[cur_no] = '\n'.join(cur)
    return claims


def ref_nums(ref_str):
    return {int(x) for x in re.findall(r'\d+', ref_str)}


def scan_text(text):
    claims = extract_claims(text)
    problems = []
    links = []
    for no, body in sorted(claims.items()):
        refs = set()
        for m in REF_RE.finditer(body):
            refs |= ref_nums(m.group(1))
        for r in sorted(refs):
            links.append((no, r))
            if r not in claims:
                problems.append((no, r, '引用悬空：权利要求 %d 引用的权利要求 %d 不存在' % (no, r)))
            elif r >= no:
                problems.append((no, r, '引用错误：权利要求 %d 不能引用在其之后/同位的权利要求 %d' % (no, r)))
    return claims, links, problems


def scan_docx(path):
    with zipfile.ZipFile(path) as zf:
        xml = zf.read('word/document.xml').decode('utf-8')
    text = re.sub(r'<[^>]+>', '\n', xml)
    return scan_text(text)


def main():
    ap = argparse.ArgumentParser(description='权利要求引用链条闭合检查（SKILL.md Step 8 机检）')
    ap.add_argument('--input', '-i', action='append', default=[], help='待检文件（替换页，可多次）')
    ap.add_argument('--dir', '-d', help='扫描目录下全部 .md/.txt（--include-docx 时含 .docx）')
    ap.add_argument('--include-docx', action='store_true', help='对目录内的 .docx 解包扫描')
    ap.add_argument('--json', action='store_true', help='额外输出 JSON 报告')
    args = ap.parse_args()

    if not args.input and not args.dir:
        ap.error('至少提供 --input 或 --dir')

    files = [Path(p) for p in args.input]
    if args.dir:
        for ext in ('.md', '.txt'):
            files.extend(sorted(Path(args.dir).glob('*' + ext)))
        if args.include_docx:
            files.extend(sorted(Path(args.dir).glob('*.docx')))

    all_problems, total_claims = [], 0
    for f in files:
        try:
            claims, links, problems = scan_docx(f) if f.suffix.lower() == '.docx' else scan_text(
                f.read_text(encoding='utf-8', errors='replace'))
        except (zipfile.BadZipFile, KeyError) as e:
            print('ERROR: 无法读取 %s（%s）' % (f, e))
            raise SystemExit(2)
        total_claims += len(claims)
        print('文件：%s —— 识别 %d 项权利要求' % (f, len(claims)))
        for no, r in links:
            print('  权利要求 %d → 引用 %d' % (no, r))
        for no, r, msg in problems:
            print('  [FAIL] %s' % msg)
        all_problems.extend((str(f),) + p for p in problems)

    if all_problems:
        print('结果：FAIL —— 检出 %d 处引用问题（悬空/错误引用，提交后将被形式审查驳回）' % len(all_problems))
        print('处理：修正引用编号（或保留被引用的权利要求）后重新运行。')
        if args.json:
            print(json.dumps({'problems': [
                {'file': p[0], 'claim': p[1], 'ref': p[2], 'msg': p[3]} for p in all_problems
            ], 'pass': False}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    print('结果：PASS —— %d 项权利要求引用链条闭合。' % total_claims)
    if args.json:
        print(json.dumps({'problems': [], 'pass': True}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
