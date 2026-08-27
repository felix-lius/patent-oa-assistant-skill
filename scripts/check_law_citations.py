# -*- coding: utf-8 -*-
"""
法条条号核对（对应 SKILL.md Step 10 可机检项"法条条号：全部为现行版本"）

扫描文本中的"专利法第 X 条""实施细则第 X 条"引用，与现行版本
（专利法 2020 修正 / 实施细则 2023 修订）条号映射表核对：
- 条号在表内 → OK（显示条号主题，供核对引用场景是否匹配）
- 条号不在表内 → WARN（未收录，可能为旧条号或引用错误，需人工核对官方文本）

条号映射依据 references/rejection-quick-reference.md（已按现行有效版本校正）。

用法：
  python check_law_citations.py --input 初稿.md
  python check_law_citations.py --dir 输出目录

退出码：0 = 无 WARN（或非 --strict 模式）；1 = 存在 WARN（仅 --strict 时）
"""
import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

LAW_MAP = {
    '专利法': {
        2: '发明/实用新型/外观设计定义（第2款：发明=技术方案）',
        9: '禁止重复授权（第1款）',
        22: '授权条件（第2款新颖性/第3款创造性/第4款实用性）',
        25: '不授予专利权的客体',
        26: '申请文件（第3款公开充分/第4款权利要求清楚简要）',
        29: '优先权',
        31: '单一性（第1款）',
        33: '修改不得超出原说明书和权利要求书记载的范围',
        64: '保护范围的解释（第1款：以权利要求的内容为准）',
    },
    '实施细则': {
        20: '说明书撰写要求',
        21: '附图要求',
        22: '权利要求书撰写要求',
        23: '独立权利要求/必要技术特征（第2款）',
        24: '权利要求书其他要求（一）',
        25: '权利要求书其他要求（二）',
        26: '摘要',
    },
}

CITE_RE = re.compile(r'(专利法|实施细则|细则)\s*第\s*(\d+)\s*条(?:之?第?\s*([一二三四五六七八九十\d]+)\s*款)?')


def scan_text(text, label):
    hits = []
    for lineno, line in enumerate(text.split('\n'), 1):
        for m in CITE_RE.finditer(line):
            law, art_no, para = m.group(1), int(m.group(2)), m.group(3)
            if law == '细则':
                law = '实施细则'
            theme = LAW_MAP.get(law, {}).get(art_no)
            hits.append({
                'file': label, 'line': lineno, 'law': law, 'article': art_no,
                'para': para or '', 'theme': theme, 'status': 'ok' if theme else 'warn',
                'match': m.group(0)[:60], 'context': line.strip()[:100],
            })
    return hits


def main():
    ap = argparse.ArgumentParser(description='法条条号核对（SKILL.md Step 10 机检项）')
    ap.add_argument('--input', '-i', action='append', default=[], help='待扫描文件路径（可多次）')
    ap.add_argument('--dir', '-d', help='扫描目录下全部 .md/.txt')
    ap.add_argument('--strict', action='store_true', help='存在未收录条号时判定 FAIL（默认仅提示）')
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

    if not all_hits:
        print('未检测到法条条号引用（无可核对内容）。')
    for h in all_hits:
        tag = 'WARN' if h['status'] == 'warn' else '  OK'
        theme = h['theme'] if h['theme'] else '未收录，请人工核对官方文本（可能是旧条号或引用错误）'
        print('[%s] %s（%s 第 %d 条%s）%s —— 第 %d 行' % (
            tag, h['match'], h['law'], h['article'],
            '第%s款' % h['para'] if h['para'] else '', theme, h['line']))

    warns = [h for h in all_hits if h['status'] == 'warn']
    if warns and args.strict:
        print('结果：FAIL —— 检出 %d 处未收录条号（--strict），需人工核对现行法条' % len(warns))
        if args.json:
            print(json.dumps({'hits': all_hits, 'pass': False}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    if warns:
        print('结果：PASS（含 %d 处 WARN 提示）—— 未收录条号请人工核对官方文本' % len(warns))
    else:
        print('结果：PASS —— 全部条号均在现行版本映射表内。')
    if args.json:
        print(json.dumps({'hits': all_hits, 'pass': True}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
