# -*- coding: utf-8 -*-
"""
修改超范围风险拦截（对应 amendment-scope-checklist.md 第三节）

规则：**🔴 高风险修改一律不建议列入修改方案**（无出处 / 仅附图图形 / 引入新主题事项）。
本工具扫描《权利要求修改对照页》，检出 🔴 即 FAIL——把"靠 AI 自觉"变成机检硬门。

判定范围：
  - md / txt：表格行（以 | 分隔）中的 🔴；或"超范围风险"字段的显式 🔴 标注
  - docx（--include-docx）：按段落判定（docx 表格为真实表格结构，无 | 分隔符，
    单元格内容各自独立成段，故改为段落级判定）

排除（避免误判等级定义说明文字）：
  - 含"风险等级"的等级定义行（如"超范围风险等级：🟢 低=…🔴 高=…"）
  - 含"高="的等级定义片断（如"🔴 高=无出处"）
  - 以"说明""注"开头的行

用法：
  python check_amendment_risk.py --input 权利要求修改对照页_xxx.md
  python check_amendment_risk.py --dir 输出目录 --include-docx

退出码：0 = 通过；1 = 检出 🔴 高风险修改（FAIL）
"""
import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TARGET_PREFIX = '权利要求修改对照页'

RED = '🔴'
# 排除：等级定义说明（不是某一处修改的风险判定）
SKIP_PAT = re.compile(r'风险等级|高=|^\s*(说明|注[:：])')


def collect_files(args):
    files = [Path(p) for p in (args.input or [])]
    if args.dir:
        d = Path(args.dir)
        for ext in ('.md', '.txt', '.docx'):
            files.extend(sorted(d.glob('*' + ext)))
    if args.include_docx:
        out = []
        for f in files:
            if f.suffix.lower() == '.docx':
                out.append(f)
            else:
                # md 与其同名 docx 视为同一产物，避免漏检 docx 版本
                sib = f.with_suffix('.docx')
                if sib.exists():
                    out.append(sib)
                out.append(f)
        files = out
    seen, uniq = set(), []
    for f in files:
        if f.resolve() not in seen:
            seen.add(f.resolve())
            uniq.append(f)
    # 只针对对照页；其余文件不属本工具职责
    return [f for f in uniq if TARGET_PREFIX in f.name]


def iter_lines(path):
    """产出 (行号, 文本)；docx 按段落切分。"""
    if path.suffix.lower() == '.docx':
        with zipfile.ZipFile(path) as zf:
            xml = zf.read('word/document.xml').decode('utf-8')
        for idx, para in enumerate(xml.split('</w:p>'), 1):
            text = re.sub(r'<[^>]+>', '', para).strip()
            if text:
                yield idx, text
    else:
        text = path.read_text(encoding='utf-8', errors='replace')
        for idx, line in enumerate(text.split('\n'), 1):
            if line.strip():
                yield idx, line


def main():
    ap = argparse.ArgumentParser(
        description='修改超范围风险拦截（🔴 高风险修改不得列入修改方案）')
    ap.add_argument('--input', '-i', action='append', default=[], help='待检文件（可多次）')
    ap.add_argument('--dir', '-d', help='扫描目录下的对照页文件')
    ap.add_argument('--include-docx', action='store_true', help='同时扫描 docx（含表格段落）')
    ap.add_argument('--json', action='store_true', help='额外输出 JSON 报告')
    args = ap.parse_args()

    if not args.input and not args.dir:
        ap.error('至少提供 --input 或 --dir')

    files = collect_files(args)
    if not files:
        print('结果：跳过 —— 未找到《%s》文件（不属本工具职责）' % TARGET_PREFIX)
        raise SystemExit(0)

    hits = []
    for f in files:
        for lineno, text in iter_lines(f):
            if RED not in text:
                continue
            if SKIP_PAT.search(text):
                continue
            hits.append({'file': str(f), 'line': lineno, 'text': text[:100]})

    print('修改超范围风险拦截（待检 %d 个文件）' % len(files))
    for h in hits:
        print('  [FAIL] %s 第 %d 行：%s' % (h['file'], h['line'], h['text']))

    if hits:
        print('结果：FAIL —— 检出 %d 处 🔴 高风险修改。按 amendment-scope-checklist，'
              '高风险修改一律不建议列入修改方案；' % len(hits))
        print('      请改选有原始出处的修改方案，或将未采用的方案移出对照页。')
        if args.json:
            print(json.dumps({'hits': hits, 'pass': False}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    print('结果：PASS —— 未检出 🔴 高风险修改。')
    if args.json:
        print(json.dumps({'hits': [], 'pass': True}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
