# -*- coding: utf-8 -*-
"""
逐字引用比对（对应 SKILL.md Step 4"引用铁律"与 Step 10 机检项"引用忠实性"）

规则：区别技术特征必须**逐字引用**原专利文档（权利要求书/说明书）记载的原文，
禁止概括、改写、重构；附图标记须保留。

检测原理：对基准文件（权利要求书）与待检文件（初稿/区别特征清单）做 3-gram
字符重叠度比对——与原文**完全一致**的句子通过；**高度相似但有改动**（删除"所述"、
"设置于"改"设置在"等轻度改写）→ WARN"疑似改写引用"；论证语言（重叠度低）不报。

边界说明：本工具能拦截"抄引用时顺手改词"的轻度改写；对完全同义的替换
（如"设置"→"安装"）无法识别，属语义判断，由 AI 对照原文自检。

用法：
  python check_citations.py --claims 原权利要求书.md --input 初稿.md
  python check_citations.py --claims 原权利要求书.md --dir 输出目录
  python check_citations.py --claims 原权利要求书.md --input 初稿.md --strict

退出码：0 = 通过（或仅 WARN 提示）；1 = 存在疑似改写引用（--strict 时）
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PASS_COV = 0.90   # 与原文重叠 >= 90% 视为逐字引用
WARN_COV = 0.50   # 重叠 >= 50% 且 < 90% 视为疑似改写
MIN_LEN = 10      # 少于 10 字不参与比对


def norm(s):
    return unicodedata.normalize('NFKC', s).replace(' ', '').replace('\u3000', '')


def ngrams(s, n=3):
    s = norm(s)
    if len(s) < n:
        return {s} if s else set()
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def split_sentences(text):
    return [s.strip() for s in re.split(r'[。；\n]+', text) if s.strip()]


def coverage(sent, base_ngrams):
    sg = ngrams(sent)
    if not sg:
        return 0.0
    return len(sg & base_ngrams) / len(sg)


def main():
    ap = argparse.ArgumentParser(description='逐字引用比对（SKILL.md Step 4 引用铁律机检）')
    ap.add_argument('--claims', '-c', required=True, help='基准文件：原权利要求书（引用原文来源）')
    ap.add_argument('--input', '-i', action='append', default=[], help='待检文件（初稿/区别特征清单，可多次）')
    ap.add_argument('--dir', '-d', help='扫描目录下全部 .md/.txt')
    ap.add_argument('--strict', action='store_true', help='疑似改写引用升级为 FAIL（默认 WARN 提示）')
    ap.add_argument('--json', action='store_true', help='额外输出 JSON 报告')
    args = ap.parse_args()

    if not args.input and not args.dir:
        ap.error('至少提供 --input 或 --dir')

    base_text = Path(args.claims).read_text(encoding='utf-8', errors='replace')
    base_ngrams = ngrams(base_text)

    files = [Path(p) for p in args.input]
    if args.dir:
        for ext in ('.md', '.txt'):
            files.extend(sorted(Path(args.dir).glob('*' + ext)))

    warns, checked = [], 0
    for f in files:
        text = f.read_text(encoding='utf-8', errors='replace')
        for sent in split_sentences(text):
            if len(norm(sent)) < MIN_LEN:
                continue
            cov = coverage(sent, base_ngrams)
            checked += 1
            if WARN_COV <= cov < PASS_COV:
                warns.append({'file': str(f), 'sentence': sent[:80],
                              'coverage': round(cov * 100, 1)})

    print('逐字引用比对（基准：%s / 待检 %d 个文件 / 参与比对句 %d 条）' % (
        Path(args.claims).name, len(files), checked))
    for w in warns:
        print('  [WARN] %s —— 与原文重叠 %s%%，疑似改写引用：%s' % (
            w['file'], w['coverage'], w['sentence']))

    if warns and args.strict:
        print('结果：FAIL —— 检出 %d 处疑似改写引用（--strict）' % len(warns))
        print('处理：区别特征必须逐字引用原文（含附图标记），按权利要求书原文修正后重新运行。')
        if args.json:
            print(json.dumps({'warns': warns, 'pass': False}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    if warns:
        print('结果：PASS（含 %d 处 WARN）—— 疑似改写引用请对照原文核验' % len(warns))
    else:
        print('结果：PASS —— 未检出疑似改写引用。')
    if args.json:
        print(json.dumps({'warns': warns, 'pass': True}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
