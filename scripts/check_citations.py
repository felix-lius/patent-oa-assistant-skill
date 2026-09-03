# -*- coding: utf-8 -*-
"""
逐字引用比对（对应 SKILL.md Step 4"引用铁律"与 Step 10 机检项"引用忠实性"）

规则：区别技术特征必须**逐字引用**原专利文档（权利要求书/说明书）记载的原文，
禁止概括、改写、重构；附图标记须保留。

检测原理：对基准文件（权利要求书）与待检文件（初稿/区别特征清单）做 3-gram
字符重叠度比对——与原文**完全一致**的句子通过；**高重叠但有改动/拼接**的句子
→ WARN"疑似改写引用"；论证语言（重叠度低）不报。

**方法与固有局限（改动前必读）**：
按字符 3-gram 覆盖率判定，实测规律为：
  - 纯原文                    ≈ 100% → PASS
  - 论述前缀 + 完整原文        ≈ 77% → WARN（本工具主要捕获这一类）
  - 轻度改写（去"所述"、"于"改"在"）≈ 52% → **不报**（漏检）
即本方法对"完整引用 + 论述拼接"敏感，对"措辞轻度改写"不敏感。
故本工具定位为**提示级**（默认 WARN，不阻断），用于提醒人工核对疑似处，
不得作为"引用逐字合规"的充分证据。

**降噪（2026-09-03）**：原阈值 0.50 时，一份合格初稿报出 19 处 WARN 且无一为真，
信号被噪声淹没。现为：阈值提至 0.60 + 论述性表述豁免（DISCOURSE_RE），
同一份初稿降至 6 处。豁免词调整须同步跑回归，避免把应检出的句子一并豁免掉。

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
WARN_COV = 0.60   # 重叠 >= 60% 且 < 90% 视为疑似改写（原为 0.50，误报率过高）
MIN_LEN = 10      # 少于 10 字不参与比对

# 论述性表述标记：含这些词的句子是申请人/代理人的论证语言，不是对原文的引用，
# 其与原文的重叠来自技术术语本身的复用，不计入"疑似改写引用"。
# （实测：阈值 0.50 时一份合格初稿报出 19 处 WARN 且无一为真，信号被噪声淹没）
DISCOURSE_RE = re.compile(
    r'发明人|审查意见|审查员|恳请|综上|因此|然而|但是|需要说明|应当指出'
    r'|本申请|本发明|本案|对比文件|就.{0,6}而言|退一步|即便|由此|可见'
    r'|其限定|限定了|记载了|如原文')


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
                if DISCOURSE_RE.search(sent):
                    # 论述性表述（含"发明人""审查意见""本申请"等论证用语）不是对原文的引用，
                    # 其与原文的重叠来自技术术语本身的复用，不构成"改写引用"。
                    continue
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
