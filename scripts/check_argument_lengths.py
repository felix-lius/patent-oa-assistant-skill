# -*- coding: utf-8 -*-
"""
特征论证字数区间检查（对应 SKILL.md Step 7"每个特征 1200~1800 字为建议区间"）

规则：每个区别技术特征的深度论证建议 1200~1800 字（论证充分为准，不为凑字数注水，
也不因字数硬性目标牺牲简洁）——字数不是硬纪律，本工具输出 WARN 提示：
  - 低于下限：论证可能不足
  - 高于上限：可能注水，建议精简

实现：按 Markdown 标题（## / ###）将初稿切分为节，统计每节字数并对照区间。

用法：
  python check_argument_lengths.py --input 初稿.md
  python check_argument_lengths.py --dir 输出目录
  python check_argument_lengths.py --input 初稿.md --min 1000 --max 2000

退出码：0 = 通过（或仅 WARN 提示）；1 = 存在越界节（--strict 时）
"""
import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HEADING = re.compile(r'^(#{2,3})\s+(.*)$')


def split_sections(text):
    sections = []
    cur_title, cur = '(文件头)', []
    for ln in text.split('\n'):
        m = HEADING.match(ln)
        if m:
            if cur:
                sections.append((cur_title, ''.join(cur)))
            cur_title = m.group(2)
            cur = []
        else:
            cur.append(ln)
    if cur:
        sections.append((cur_title, ''.join(cur)))
    return sections


def char_count(s):
    return len(re.sub(r'\s', '', s))


def main():
    ap = argparse.ArgumentParser(description='特征论证字数区间检查（SKILL.md Step 7 建议区间）')
    ap.add_argument('--input', '-i', action='append', default=[], help='待检文件（可多次）')
    ap.add_argument('--dir', '-d', help='扫描目录下全部 .md/.txt')
    ap.add_argument('--min', type=int, default=1200, help='每特征论证建议字数下限（默认 1200）')
    ap.add_argument('--max', type=int, default=1800, help='每特征论证建议字数上限（默认 1800）')
    ap.add_argument('--strict', action='store_true', help='越界节升级为 FAIL（默认 WARN 提示）')
    ap.add_argument('--json', action='store_true', help='额外输出 JSON 报告')
    args = ap.parse_args()

    if not args.input and not args.dir:
        ap.error('至少提供 --input 或 --dir')

    files = [Path(p) for p in args.input]
    if args.dir:
        for ext in ('.md', '.txt'):
            files.extend(sorted(Path(args.dir).glob('*' + ext)))

    warns, total = [], 0
    for f in files:
        text = f.read_text(encoding='utf-8', errors='replace')
        total = char_count(text)
        for title, body in split_sections(text):
            n = char_count(body)
            if n == 0 or title == '(文件头)':
                continue
            if n < args.min:
                warns.append({'file': str(f), 'section': title, 'chars': n,
                              'level': '论证不足（低于 %d 字）' % args.min})
            elif n > args.max:
                warns.append({'file': str(f), 'section': title, 'chars': n,
                              'level': '超出建议区间（高于 %d 字，可能注水）' % args.max})

    print('特征论证字数区间检查（区间 %d~%d 字 / 待检 %d 个文件）' % (args.min, args.max, len(files)))
    for w in warns:
        print('  [WARN] %s —— 节"%s"：%d 字，%s' % (w['file'], w['section'], w['chars'], w['level']))
    if files:
        print('  待检文件总字数：%d' % total)

    if warns and args.strict:
        print('结果：FAIL —— 检出 %d 节越界（--strict）' % len(warns))
        if args.json:
            print(json.dumps({'warns': warns, 'pass': False}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    if warns:
        print('结果：PASS（含 %d 处 WARN）—— 字数仅为建议区间，论证充分与否以实质为准' % len(warns))
    else:
        print('结果：PASS —— 各节字数均在建议区间内。')
    if args.json:
        print(json.dumps({'warns': warns, 'pass': True}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
