# -*- coding: utf-8 -*-
"""
术语一致性核对（对应 SKILL.md Step 10 可机检项"术语一致性（机检，全文）"）

三项检查：
  ① 文件头一致性：初稿中的申请号 / 发明名称 / 第 N 次审查意见 与基准文件
     （OA 通知书 / 权利要求书 / 说明书）保持一致（申请号写错为灾难级错误，硬性 FAIL）
  ② 附图标记一致性：初稿中出现的数字标记应可追溯至基准文件的标记集
     （防止 AI 编造附图标记，如把 107 写成 108）
  ③ 缩写-全称配对一致性：初稿中的缩写首次定义（如"MCD（MOS-Controlled Diode，沟道二极管）"）
     须与基准文件一致，不得自造缩写（"如权利要求×所述"等合法写法不在此列）

用法：
  python check_terms.py --reference 原权利要求书.md --reference 原说明书.md --input 初稿.md
  python check_terms.py --reference OA通知书.md --input 意见陈述书初稿.md --name "一种改进的电路装置"
  python check_terms.py --dir 归档目录
  python check_terms.py --input 初稿.md --strict     # ②③ 的 WARN 升级为 FAIL

说明：②③ 涉及噪声（数值范围/通用缩写等），默认输出 WARN 提示人工核对；
① 的申请号与发明名称不一致为硬性 FAIL。--strict 可将 WARN 全部升级为 FAIL。

退出码：0 = 通过（或仅提示级 WARN）；1 = 硬性不一致（或 --strict 下有 WARN）
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

APPNO_RE = re.compile(r'\b\d{8,12}\.\d\b')
TITLE_RE = re.compile(r'发明名称[：:]\s*([^\n，。；;]{2,80})')
ROUND_RE = re.compile(r'第\s*([一二三四五六七八九十百\d]+)\s*次\s*审查意见')

# 标记提取前的噪声剔除（段落号/图号/对比文件编号/行首编号/条款号）
MARKER_CLEAN = [
    re.compile(r'\[\d+\]'),          # 段落号 [0023]
    re.compile(r'第\s*\d+\s*[段条款]'),  # 第X段/条/款
    re.compile(r'图\s*\d+'),         # 图1
    re.compile(r'D\d+'),             # D1 D2
    re.compile(r'CN\s*\d+'),         # CN 公开号
    re.compile(r'^\s*\d+[.、)]\s*', re.M),  # 行首编号 1. 2、
    re.compile(r'\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日'),  # 日期 2025年03月28日
    re.compile(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}'),                # 日期 2025-03-28 / 2025/03/28
]
MARKER_RE = re.compile(r'(?<!\d)\d{1,3}(?!\d)')

ABBR_PATTERNS = [
    # 缩写在前：MCD（MOS-Controlled Diode，沟道二极管）
    re.compile(r'([A-Z][A-Z0-9\-]{1,20})\s*[（(]\s*([^（）()]{2,80})\s*[）)]'),
    # 中文在前：沟道二极管（MCD）
    re.compile(r'([\u4e00-\u9fff]{2,20})\s*[（(]\s*([A-Z][A-Z0-9\-]{1,20})\s*[）)]'),
]
NOISE_ABBR = re.compile(r'^(D\d+|CN\d+|图\d+)$')


def norm(s):
    """归一化：全角转半角 + 去空白 + 大写，用于比对。"""
    return unicodedata.normalize('NFKC', s).replace(' ', '').replace('\u3000', '').upper()


def extract_appnos(text):
    return {m.group(0) for m in APPNO_RE.finditer(text)}


def extract_titles(text):
    return [m.group(1) for m in TITLE_RE.finditer(text)]


def extract_rounds(text):
    return [m.group(1) for m in ROUND_RE.finditer(text)]


def extract_markers(text):
    clean = text
    for pat in MARKER_CLEAN:
        clean = pat.sub('', clean)
    return {m.group(0) for m in MARKER_RE.finditer(clean)}


def extract_abbrevs(text):
    pairs = {}
    for pat in ABBR_PATTERNS:
        for m in pat.finditer(text):
            a, f = (m.group(1), m.group(2)) if pat is ABBR_PATTERNS[0] else (m.group(2), m.group(1))
            if NOISE_ABBR.match(a):
                continue
            pairs.setdefault(norm(a), set()).add(norm(f))
    return pairs


def classify(path):
    """目录模式下按文件名归类：待检优先（对照页/替换页/意见陈述书），其余含基准词为基准。"""
    name = path.name
    if any(k in name for k in ('意见陈述书', '替换页', '对照页')):
        return 'input'
    if any(k in name for k in ('通知书', '权利要求', '说明书')):
        return 'reference'
    return None


def main():
    ap = argparse.ArgumentParser(description='术语一致性核对（SKILL.md Step 10 机检项）')
    ap.add_argument('--reference', '-r', action='append', default=[], help='基准文件（OA通知书/权利要求书/说明书，可多次）')
    ap.add_argument('--input', '-i', action='append', default=[], help='待检文件（初稿，可多次）')
    ap.add_argument('--dir', '-d', help='目录模式：按文件名自动归类基准/待检')
    ap.add_argument('--name', default='', help='发明名称（手动指定，覆盖自动提取）')
    ap.add_argument('--strict', action='store_true', help='②③ 的 WARN 升级为 FAIL')
    ap.add_argument('--json', action='store_true', help='额外输出 JSON 报告')
    args = ap.parse_args()

    refs, inputs = [Path(p) for p in args.reference], [Path(p) for p in args.input]
    if args.dir:
        d = Path(args.dir)
        for f in sorted(d.glob('*.md')) + sorted(d.glob('*.txt')):
            cls = classify(f)
            if cls == 'reference':
                refs.append(f)
            elif cls == 'input':
                inputs.append(f)
    if not refs:
        ap.error('至少提供一个 --reference（或 --dir 目录中含基准文件）')
    if not inputs:
        ap.error('至少提供一个 --input（或 --dir 目录中含待检文件）')

    ref_texts = [f.read_text(encoding='utf-8', errors='replace') for f in refs]
    base_appnos = set().union(*[extract_appnos(t) for t in ref_texts]) if ref_texts else set()
    base_title = args.name or (extract_titles(ref_texts[0]) or [None])[0]
    base_rounds = [r for t in ref_texts for r in extract_rounds(t)]
    base_markers = set().union(*[extract_markers(t) for t in ref_texts]) if ref_texts else set()
    base_abbrevs = {}
    for t in ref_texts:
        for a, fulls in extract_abbrevs(t).items():
            base_abbrevs.setdefault(a, set()).update(fulls)

    fails, warns = [], []
    for f in inputs:
        text = f.read_text(encoding='utf-8', errors='replace')

        # ① 申请号
        for appno in extract_appnos(text):
            if base_appnos and appno not in base_appnos:
                fails.append((f.name, '申请号不一致', appno + ' 未出现在基准文件中'))
        # ① 发明名称
        for t in extract_titles(text):
            if base_title and norm(t) != norm(base_title):
                fails.append((f.name, '发明名称不一致', '%s ≠ %s' % (t, base_title)))
        # ① 第 N 次审查意见
        for r in extract_rounds(text):
            if base_rounds and r != base_rounds[0]:
                warns.append((f.name, '第N次审查意见不一致', '第%s次 ≠ 第%s次' % (r, base_rounds[0])))

        # ② 附图标记
        new_markers = extract_markers(text) - base_markers
        for m in sorted(new_markers):
            warns.append((f.name, '疑似新增附图标记', m + ' 未出现在基准文件中，请核对是否编造'))

        # ③ 缩写-全称配对
        for a, fulls in extract_abbrevs(text).items():
            if a in base_abbrevs:
                if not fulls & base_abbrevs[a]:
                    warns.append((f.name, '缩写全称不一致', '%s（%s）与基准定义不符' % (
                        a, '、'.join(sorted(fulls)))))
            else:
                warns.append((f.name, '疑似自造缩写', '%s 未出现在基准文件中' % a))

    print('术语一致性核对（基准 %d 个文件 / 待检 %d 个文件）' % (len(refs), len(inputs)))
    if base_appnos:
        print('  基准申请号：' + '、'.join(sorted(base_appnos)))
    if base_title:
        print('  基准发明名称：%s' % base_title)
    if base_rounds:
        print('  基准第N次：第%s次审查意见' % base_rounds[0])
    print('  基准附图标记集：%d 个 / 基准缩写定义：%d 个' % (len(base_markers), len(base_abbrevs)))

    for fname, cat, detail in fails:
        print('  [FAIL] %s —— %s：%s' % (fname, cat, detail))
    for fname, cat, detail in warns:
        print('  [WARN] %s —— %s：%s' % (fname, cat, detail))

    if fails or (args.strict and warns):
        print('结果：FAIL —— %d 处硬性不一致%s' % (
            len(fails), '（--strict 下 %d 处 WARN 升级为 FAIL）' % len(warns) if args.strict and warns else ''))
        print('处理：按基准文件修正初稿（申请号/发明名称/标记/缩写定义），修正后重新运行。')
        if args.json:
            print(json.dumps({'fails': fails, 'warns': warns, 'pass': False}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    if warns:
        print('结果：PASS（含 %d 处 WARN 提示）—— 提示项请人工核对后再提交' % len(warns))
    else:
        print('结果：PASS —— 术语一致性核对全部通过。')
    if args.json:
        print(json.dumps({'fails': [], 'warns': warns, 'pass': True}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
