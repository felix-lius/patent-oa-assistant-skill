# -*- coding: utf-8 -*-
"""
权利要求自足性扫描（对应 SKILL.md Step 10 可机检项"权利要求自足性（机检，替换页）"）

规则：替换页中全部权利要求不得以"引用形式"记载特征——
禁止出现"参照/参见说明书第×段""如说明书所述""如图×所示"等引用形式
（专利法第 26 条第 4 款"清楚、简要"要求，审查指南禁止权利要求以引用
说明书/附图的方式限定特征）；所有特征必须直接、完整写入权利要求文本。

注意："如权利要求 1 所述""根据权利要求 1 所述的"是从属权利要求的合法
标准写法，不属于本扫描范围。

用法：
  python check_claims_selfcontained.py --input 替换页.md
  python check_claims_selfcontained.py --dir 输出目录

退出码：0 = 通过；1 = 检出引用形式记载特征（FAIL）
"""
import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PATTERNS = [
    ('引用说明书', re.compile(r'说明书第\s*[0-9一二三四五六七八九十百千]+[段节]')),
    ('如说明书所述', re.compile(r'如说明书[所述所载所示]')),
    ('参照/参见说明书', re.compile(r'(参照|参见)说明书')),
    ('如图X所示', re.compile(r'如图\s*[0-9一二三四五六七八九十百千]+\s*所示')),
    ('如附图所述', re.compile(r'如附图[所述所示]')),
    ('参照/参见附图', re.compile(r'(参照|参见|见)附图')),
]


def scan_text(text, label):
    hits = []
    for lineno, line in enumerate(text.split('\n'), 1):
        for cat, pat in PATTERNS:
            for m in pat.finditer(line):
                hits.append({'file': label, 'line': lineno, 'cat': cat,
                             'match': m.group(0)[:60], 'context': line.strip()[:100]})
    return hits


def main():
    ap = argparse.ArgumentParser(description='权利要求自足性扫描（SKILL.md Step 10 机检项）')
    ap.add_argument('--input', '-i', action='append', default=[], help='待扫描文件路径（可多次）')
    ap.add_argument('--dir', '-d', help='扫描目录下全部 .md/.txt')
    ap.add_argument('--json', action='store_true', help='额外输出 JSON 报告')
    args = ap.parse_args()

    if not args.input and not args.dir:
        ap.error('至少提供 --input 或 --dir')

    files = [Path(p) for p in args.input]
    if args.dir:
        for ext in ('.md', '.txt'):
            files.extend(sorted(Path(args.dir).glob('*' + ext)))

    all_hits = []
    for f in files:
        all_hits.extend(scan_text(f.read_text(encoding='utf-8', errors='replace'), str(f)))

    for h in all_hits:
        print('文件：%s' % h['file'])
        print('  [%s] 第 %d 行：%s' % (h['cat'], h['line'], h['context']))

    if all_hits:
        print('结果：FAIL —— 检出 %d 处引用形式记载特征，违反专利法第 26 条第 4 款' % len(all_hits))
        print('处理：将引用形式改为直接、完整地写入权利要求文本（特征可源自说明书，')
        print('但不得以引用形式替代特征本身的记载）。')
        if args.json:
            print(json.dumps({'hits': all_hits, 'pass': False}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    print('结果：PASS —— 未检出引用形式记载特征，权利要求自足性检查通过。')
    if args.json:
        print(json.dumps({'hits': [], 'pass': True}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
