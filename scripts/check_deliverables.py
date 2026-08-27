# -*- coding: utf-8 -*-
"""
交付物完整性检查（对应 SKILL.md Step 11 交付标准与输出规范命名规则）

固定交付标准（3 docx + 1 md，共 4 个文件，命名：前缀_<申请号>_YYYYMMDD.ext）：
  意见陈述书初稿_<申请号>_YYYYMMDD.docx
  权利要求书替换页_<申请号>_YYYYMMDD.docx
  权利要求修改对照页_<申请号>_YYYYMMDD.docx
  附件_答复辅助材料汇总_<申请号>_YYYYMMDD.md

检查项：
  1. 4 个期望文件是否都存在
  2. 命名是否符合规范（前缀 + 申请号 + 8 位日期）
  3. docx 是否为合法 Office 文档（zip 结构且含 word/document.xml）

用法：
  python check_deliverables.py --dir 输出目录

退出码：0 = 通过；1 = 缺失 / 命名不合规 / 文件损坏（FAIL）
"""
import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

EXPECTED = [
    ('意见陈述书初稿', 'docx'),
    ('权利要求书替换页', 'docx'),
    ('权利要求修改对照页', 'docx'),
    ('附件_答复辅助材料汇总', 'md'),
]

NAME_RE = re.compile(r'^(?P<prefix>.+?)_(?P<appno>[^_]+)_(?P<date>\d{8})\.(?P<ext>docx|md)$')


def is_valid_docx(path):
    if not zipfile.is_zipfile(path):
        return False
    with zipfile.ZipFile(path) as zf:
        return 'word/document.xml' in zf.namelist()


def main():
    ap = argparse.ArgumentParser(description='交付物完整性检查（SKILL.md Step 11 交付标准）')
    ap.add_argument('--dir', '-d', required=True, help='输出目录路径')
    ap.add_argument('--json', action='store_true', help='额外输出 JSON 报告')
    args = ap.parse_args()

    d = Path(args.dir)
    if not d.is_dir():
        print('ERROR: 目录不存在：%s' % d)
        raise SystemExit(2)
    files = [p.name for p in d.iterdir() if p.is_file()]

    print('交付物完整性检查（3 docx + 1 md）')
    report, problems, matched = [], [], set()
    for prefix, ext in EXPECTED:
        candidates = [n for n in files if n.startswith(prefix) and n.endswith('.' + ext)]
        if not candidates:
            report.append((prefix, 'missing', '缺失'))
            problems.append('缺失：%s（期望 %s_<申请号>_YYYYMMDD.%s）' % (prefix, prefix, ext))
            continue
        name = candidates[0]
        matched.add(name)
        m = NAME_RE.match(name)
        if not m:
            report.append((prefix, 'name', '命名不合规'))
            problems.append('%s 命名不合规：%s（应为 %s_<申请号>_YYYYMMDD.%s）' % (prefix, name, prefix, ext))
            continue
        if ext == 'docx' and not is_valid_docx(d / name):
            report.append((prefix, 'broken', '文件损坏'))
            problems.append('%s 文件损坏或不是合法 Office 文档：%s' % (prefix, name))
        else:
            report.append((prefix, 'ok', '通过'))

    extras = [n for n in files if n not in matched]
    for prefix, status, note in report:
        icon = {'ok': '  OK', 'missing': 'MISS', 'name': 'NAME', 'broken': 'BROK'}[status]
        print('  [%s] %s — %s' % (icon, prefix, note))
    if extras:
        print('  额外文件（不阻断）：' + '、'.join(extras))

    if problems:
        print('结果：FAIL —— 交付物不完整，不得交付')
        for p in problems:
            print('  - ' + p)
        if args.json:
            print(json.dumps({'dir': str(d), 'items': [
                {'name': p, 'status': s, 'note': n} for p, s, n in report
            ], 'problems': problems, 'extras': extras, 'pass': False}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    print('结果：PASS —— 4 个交付物齐备，命名合规，docx 文件有效。')
    if args.json:
        print(json.dumps({'dir': str(d), 'items': [
            {'name': p, 'status': s, 'note': n} for p, s, n in report
        ], 'problems': [], 'extras': extras, 'pass': True}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
