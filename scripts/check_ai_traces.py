# -*- coding: utf-8 -*-
"""
AI 痕迹扫描（对应 SKILL.md Step 9"无 AI 痕迹"与 Step 10 机检项，规则依据 references/style-rules.md）

扫描正文中的 AI 痕迹，五类：
  1. 文采化禁用词：设计哲学 / 设计思想 / 技术轨道 / 根本分野 / 技术思想 / 赋能 / 抓手 / 闭环 / 底层逻辑 / 范式转移
  2. AI 高频连接词：值得注意的是 / 需要强调的是 / 不难发现 / 综上所述不难看出 / 显而易见的是 / 值得一提 / 毋庸置疑 / 首先 / 其次 / 再次
     （"综上所述"单独使用是意见陈述书固定收尾语，豁免）
  3. 内部框架术语泄漏：四维比对 / 结合启示阻断 / 目的性驱动缺失 / 物理逻辑冲突检验 / 教导缺失 / 防割裂 / 反向推演 /
     核心构思统领 / 一形两用 / 移用技术障碍 / 答复前景 / 创造性贡献度 / 打分 / 权重
  4. 禁止的格式痕迹：→ 链式箭头、行首分点符号（• / -）
  5. 半角标点：中文语境中的英文逗号/句号/分号/冒号（附图标记数字与英文缩写豁免）

说明：扫描器命中后由 AI 判断改写（如"首先"在个别语境可合法使用）；
正文外附件（前缀"附件_"）豁免全部检查。

用法：
  python check_ai_traces.py --input 初稿.md
  python check_ai_traces.py --dir 输出目录 --include-docx
  python check_ai_traces.py --input 初稿.md --extra 自定义词1,自定义词2

退出码：0 = 通过（无 AI 痕迹）；1 = 检出痕迹（FAIL）
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
    ('文采化禁用词', re.compile(r'设计哲学|设计思想|技术轨道|根本分野|技术思想|赋能|抓手|闭环|底层逻辑|范式转移')),
    ('AI高频连接词', re.compile(r'值得注意的是|需要强调的是|不难发现|综上所述不难看出|综上所述不难发现|显而易见的是|值得一提|毋庸置疑|首先|其次|再次')),
    ('框架术语泄漏', re.compile(r'四维比对|结合启示阻断|目的性驱动缺失|物理逻辑冲突检验|教导缺失|防割裂|反向推演|核心构思统领|一形两用|移用技术障碍|答复前景|创造性贡献度|打分|权重')),
    ('格式痕迹-箭头', re.compile(r'→')),
    ('格式痕迹-分点', re.compile(r'^\s*[•\-]\s+', re.M)),
    ('半角标点', re.compile(r'[\u4e00-\u9fff][,.;:!?]|[,.;:!?][\u4e00-\u9fff]')),
]

# 正文外附件（内部辅助材料，提交时删除）豁免全部 AI 痕迹检查
EXEMPT_PREFIX = '附件_'


def exempted(name):
    return name.startswith(EXEMPT_PREFIX)


def scan_text(text, label):
    if exempted(label):
        return []
    hits = []
    for lineno, line in enumerate(text.split('\n'), 1):
        for cat, pat in PATTERNS:
            for m in pat.finditer(line):
                hits.append({'file': label, 'line': lineno, 'cat': cat,
                             'match': m.group(0)[:60], 'context': line.strip()[:100]})
    return hits


def scan_docx(path):
    if exempted(path.name):
        return []
    with zipfile.ZipFile(path) as zf:
        xml = zf.read('word/document.xml').decode('utf-8')
    hits = []
    for idx, para in enumerate(xml.split('</w:p>'), 1):
        text = re.sub(r'<[^>]+>', '', para).strip()
        if not text:
            continue
        for cat, pat in PATTERNS:
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
    ap = argparse.ArgumentParser(description='AI 痕迹扫描（SKILL.md Step 9 / style-rules.md）')
    ap.add_argument('--input', '-i', action='append', default=[], help='待扫描文件路径（可多次）')
    ap.add_argument('--dir', '-d', help='扫描目录下全部 .md/.txt（--include-docx 时含 .docx）')
    ap.add_argument('--include-docx', action='store_true', help='对目录内的 .docx 解包扫描正文')
    ap.add_argument('--extra', default='', help='追加自定义关键词，逗号分隔（归入文采化禁用词）')
    ap.add_argument('--json', action='store_true', help='额外输出 JSON 报告')
    args = ap.parse_args()

    if not args.input and not args.dir:
        ap.error('至少提供 --input 或 --dir')

    if args.extra:
        extra = re.compile('|'.join(re.escape(x.strip()) for x in args.extra.split(',') if x.strip()))
        PATTERNS.insert(0, ('文采化禁用词(自定义)', extra))

    files = collect_files(args)
    if not files:
        print('未找到可扫描的文件。')
        raise SystemExit(2)

    all_hits = []
    for f in files:
        try:
            if f.suffix.lower() == '.docx':
                hits = scan_docx(f)
            else:
                hits = scan_text(f.read_text(encoding='utf-8', errors='replace'), f.name)
        except (zipfile.BadZipFile, KeyError) as e:
            print('ERROR: 无法读取 %s（%s）' % (f, e))
            raise SystemExit(2)
        if hits:
            print('文件：%s' % f)
            for h in hits:
                print('  [%s] 第 %d 行：%s' % (h['cat'], h['line'], h['context']))
        all_hits.extend(hits)

    if all_hits:
        print('结果：FAIL —— 检出 %d 处 AI 痕迹（涉及 %d/%d 个文件）' % (
            len(all_hits), len({h['file'] for h in all_hits}), len(files)))
        print('处理：按 style-rules.md 改写（删除禁用词/套话、框架术语融入自然段落、')
        print('全角标点、去除箭头与分点格式）；"首先/其次"等在个别语境可合法使用，由 AI 判断。')
        if args.json:
            print(json.dumps({'files': len(files), 'hits': all_hits, 'pass': False},
                             ensure_ascii=False, indent=2))
        raise SystemExit(1)

    print('结果：PASS —— 扫描 %d 个文件，无 AI 痕迹。' % len(files))
    if args.json:
        print(json.dumps({'files': len(files), 'hits': [], 'pass': True}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
