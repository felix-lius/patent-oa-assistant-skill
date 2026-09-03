# -*- coding: utf-8 -*-
"""
修改后权利要求书检查（三处一致性 + 多项独权重叠提示）

**为什么需要这个脚本**：
- M1：《意见陈述书》"修改说明"、《权利要求修改对照页》、《权利要求书替换页》三者的
  一致性此前**没有任何脚本校验**，全靠人工核对——这是最大的校验盲区。三份文件由同一次
  生成产出，一旦某处漏改或改错，文书读起来依然完整，极难肉眼发现。
- M3：多项独立权利要求高度重叠时，实务上可能引专利法第 31 条第 1 款单一性或重复
  保护问题，此前同样无任何提示。

**检查项**：
  1. 替换页 ↔ 对照页：逐条比对权利要求文本（归一化后），不一致即 **FAIL**
  2. 三件交付物的申请号、发明名称一致（不一致 FAIL）
  3. 存在修改条目时，意见陈述书须有"修改说明"章节并含专利法第 33 条声明（缺失 WARN）
  4. 多项独立权利要求两两重叠度超阈值 → **WARN**（判断需人工，不阻断）

**支持的对照页格式**：
  - 表格型：`| 序号 | 原权利要求文本 | 修改后文本 | 修改标记 | 依据出处 | 风险 |`
  - 分段型：`**修改后文本（…）**` 标题之后以 `>` 引用的完整全文

用法：
  python check_amended_claims.py --dir 输出目录
  python check_amended_claims.py --input 替换页.md --input 对照页.md --input 意见陈述书.md

退出码：0 = 通过（或仅 WARN）；1 = 一致性 FAIL
"""
import argparse
import difflib
import json
import re
import sys
import zipfile
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PREFIX_REPLACE = '权利要求书替换页'
PREFIX_COMPARE = '权利要求修改对照页'
PREFIX_OPINION = '意见陈述书初稿'

OVERLAP_WARN = 0.60   # 多项独权重叠度告警阈值
TEXT_SIM_OK = 0.98    # 替换页与对照页文本相似度下限（低于此即判不一致）

APNO_RE = re.compile(r'申请号[：:]\s*([0-9A-Za-z.]+)')
TITLE_RE = re.compile(r'发明(?:创造)?名称[：:]\s*(.+)')


def norm(s):
    """归一化：去加粗/删除线/反引号、去空白、统一括号与引号。"""
    s = re.sub(r'\*\*|~~|`', '', s or '')
    s = re.sub(r'\s+', '', s)
    s = s.replace('（', '(').replace('）', ')')
    s = s.replace('“', '"').replace('”', '"')
    return s


def read_text(path):
    if str(path).lower().endswith('.docx'):
        with zipfile.ZipFile(path) as zf:
            xml = zf.read('word/document.xml').decode('utf-8')
        paras = [re.sub(r'<[^>]+>', '', p).strip()
                 for p in xml.split('</w:p>')]
        return '\n'.join(p for p in paras if p)
    return Path(path).read_text(encoding='utf-8', errors='replace')


def parse_replacement(text):
    """从替换页提取 {序号: 权利要求全文}。"""
    claims, cur, buf = {}, None, []
    for line in text.split('\n'):
        s = line.strip()
        m = re.match(r'^(\d+)\.\s*(\S.*)$', s)
        if m:
            if cur is not None:
                claims[cur] = ' '.join(buf)
            cur, buf = int(m.group(1)), [m.group(2)]
        elif cur is not None:
            if s == '':
                claims[cur] = ' '.join(buf)
                cur, buf = None, []
            elif not s.startswith('权') and '利要求书' not in s:
                buf.append(s)
    if cur is not None:
        claims[cur] = ' '.join(buf)
    return claims


def subject(text):
    """提取权利要求的主题名称（"一种XX，其特征在于…"中的 XX）。"""
    m = re.match(r'^一种\s*([^，,、；;]{2,20})', text or '')
    return m.group(1).strip() if m else ''


def _strip_leading_no(s):
    """去掉"1. "这类行首编号。"""
    return re.sub(r'^\s*\d+\.\s*', '', s or '')


def parse_compare_table(text):
    """表格型对照页：定位含"修改后文本"列的表头后，按该列解析数据行。

    注意：对照页常同时含"编号对照总表"（新序号/原序号/修改动作）与"逐条修改对照表"。
    只有后者才含"修改后文本"列，必须按表头定位，否则会把"修改动作"列误当作修改后文本。
    """
    lines = text.split('\n')
    for i, line in enumerate(lines):
        s = line.strip()
        if not (s.startswith('|') and '修改后文本' in s):
            continue
        cells = [c.strip() for c in s.strip('|').split('|')]
        col = next((k for k, c in enumerate(cells) if '修改后文本' in c), None)
        if col is None:
            continue
        out = {}
        for ln in lines[i + 1:]:
            t = ln.strip()
            if not t.startswith('|'):
                break
            cs = [c.strip() for c in t.strip('|').split('|')]
            if len(cs) <= col or set(cs[0]) <= set('-: '):
                continue
            m = re.match(r'^(\d+)$', cs[0])
            if m:
                out[int(m.group(1))] = _strip_leading_no(cs[col])
        if out:
            return out
    return {}


def parse_compare_sections(text):
    """分段型对照页：**修改后文本（…）** 之后的引用块。"""
    out, lines, cur = {}, text.split('\n'), None
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r'^#{2,4}\s*权利要求\s*(\d+)', line.strip())
        if m:
            cur = int(m.group(1))
        if '修改后文本' in line and cur is not None:
            buf = []
            i += 1
            # 标题与引用块之间常有空行，先跳过；再连续收集 ">" 引用行
            while i < len(lines) and lines[i].strip() == '':
                i += 1
            while i < len(lines) and lines[i].strip().startswith('>'):
                buf.append(re.sub(r'^\s*>\s?', '', lines[i].strip()))
                i += 1
            if buf:
                out[cur] = _strip_leading_no(''.join(buf))
            continue
        i += 1
    return out


def parse_compare(text):
    out = parse_compare_table(text)
    if not out:
        out = parse_compare_sections(text)
    return out


def parse_numbering_table(text):
    """解析"编号对照总表"的新序号集合（表头含"新序号"）。

    用途：仅作编号调整的权项不会在逐条修改对照中单列，但在编号对照总表里有记录，
    不应因"对照页无对应条目"而告警。
    """
    out = set()
    lines = text.split('\n')
    for i, line in enumerate(lines):
        s = line.strip()
        if not (s.startswith('|') and '新序号' in s):
            continue
        for ln in lines[i + 1:]:
            t = ln.strip()
            if not t.startswith('|'):
                break
            cs = [c.strip() for c in t.strip('|').split('|')]
            if set(cs[0]) <= set('-: '):
                continue
            m = re.match(r'^(\d+)$', cs[0])
            if m:
                out.add(int(m.group(1)))
        break
    return out


def pick(files, prefix):
    for f in files:
        if prefix in Path(f).name:
            return f
    return None


def main():
    ap = argparse.ArgumentParser(
        description='修改后权利要求书检查（三处一致性 + 多项独权重叠提示）')
    ap.add_argument('--input', '-i', action='append', default=[], help='待检文件（可多次）')
    ap.add_argument('--dir', '-d', help='扫描目录（识别三类交付物）')
    ap.add_argument('--overlap', type=float, default=OVERLAP_WARN, help='独权重叠告警阈值')
    ap.add_argument('--json', action='store_true', help='额外输出 JSON 报告')
    args = ap.parse_args()

    if not args.input and not args.dir:
        ap.error('至少提供 --input 或 --dir')

    files = [Path(p) for p in args.input]
    if args.dir:
        d = Path(args.dir)
        for ext in ('.md', '.txt', '.docx'):
            files.extend(sorted(d.glob('*' + ext)))

    f_rep = pick(files, PREFIX_REPLACE)
    f_cmp = pick(files, PREFIX_COMPARE)
    f_opi = pick(files, PREFIX_OPINION)

    print('修改后权利要求书检查（替换页 / 对照页 / 意见陈述书）')
    if not f_rep or not f_cmp:
        print('结果：跳过 —— 需同时提供《%s》与《%s》' % (PREFIX_REPLACE, PREFIX_COMPARE))
        raise SystemExit(0)

    repl = parse_replacement(read_text(f_rep))
    cmp_text = read_text(f_cmp)
    comp = parse_compare(cmp_text)
    numbered = parse_numbering_table(cmp_text)

    fails, warns = [], []

    # 1) 逐条文本一致性
    if not repl:
        fails.append('未能从替换页解析出权利要求条目，请检查编号格式（应为"1. "开头）')
    if not comp:
        fails.append('未能从对照页解析出"修改后文本"，请检查为表格型或分段型格式')
    else:
        for idx in sorted(set(repl) | set(comp)):
            r, c = repl.get(idx), comp.get(idx)
            if r is None:
                fails.append('对照页有第 %d 条，替换页缺失' % idx)
                continue
            if c is None:
                if idx in numbered:
                    continue  # 编号对照总表已覆盖（仅编号调整，无实质修改）
                warns.append('替换页第 %d 条在对照页中无对应条目'
                             '（既未列入逐条修改对照，也不在编号对照总表中）' % idx)
                continue
            nr, nc = norm(r), norm(c)
            if nr == nc:
                continue
            sim = difflib.SequenceMatcher(None, nr, nc).ratio()
            if sim < TEXT_SIM_OK:
                fails.append('第 %d 条文本不一致（相似度 %.1f%%）：替换页与对照页"修改后文本"不同'
                             % (idx, sim * 100))

    # 2) 三件交付物的申请号 / 发明名称一致
    meta = {}
    for key, f in (('意见陈述书', f_opi), ('替换页', f_rep), ('对照页', f_cmp)):
        if not f:
            continue
        t = read_text(f)
        a = APNO_RE.search(t)
        ti = TITLE_RE.search(t)
        meta[key] = (a.group(1) if a else None, ti.group(1).strip() if ti else None)
    apnos = {v[0] for v in meta.values() if v[0]}
    titles = {v[1] for v in meta.values() if v[1]}
    if len(apnos) > 1:
        fails.append('申请号在交付物之间不一致：%s' % ' / '.join(sorted(apnos)))
    if len(titles) > 1:
        fails.append('发明名称在交付物之间不一致：%s' % ' / '.join(sorted(titles)))

    # 3) 存在修改时，意见陈述书须有修改说明与 A33 声明
    if comp and f_opi:
        opi = read_text(f_opi)
        # 允许 md 标题前缀（如"## 一、修改说明"）：模板以 md 标题层级组织章节，
        # 若只匹配行首中文序号，传 md 时会误报"未检出修改说明章节"。
        m = re.search(r'^#{0,4}\s*[一二三四五六七八九十]、\s*修改说明', opi, re.M)
        if not m:
            warns.append('对照页存在修改条目，但意见陈述书未检出"修改说明"章节')
        elif '专利法第33条' not in opi and '专利法第 33 条' not in opi:
            warns.append('意见陈述书"修改说明"中未检出专利法第33条声明')

    # 4) 多项独立权利要求重叠度
    #    主题名称不同者（如"一种3D激光雷达"与"一种清洁机器人"）不构成重复保护风险，跳过。
    indep = {k: v for k, v in repl.items() if not re.match(r'^(如|按照|依)', v)}
    keys = sorted(indep)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            if subject(indep[keys[i]]) != subject(indep[keys[j]]):
                continue
            a, b = norm(indep[keys[i]]), norm(indep[keys[j]])
            if not a or not b:
                continue
            ratio = difflib.SequenceMatcher(None, a, b).ratio()
            if ratio >= args.overlap:
                warns.append('独立权利要求 %d 与 %d 主题相同且文本重叠度 %.1f%%，'
                             '请人工确认是否涉及单一性（专利法第31条第1款）或重复保护'
                             % (keys[i], keys[j], ratio * 100))

    for w in warns:
        print('  [WARN] %s' % w)
    for f in fails:
        print('  [FAIL] %s' % f)

    if fails:
        print('结果：FAIL —— 检出 %d 处不一致（另 %d 处 WARN）' % (len(fails), len(warns)))
        if args.json:
            print(json.dumps({'fails': fails, 'warns': warns, 'pass': False},
                             ensure_ascii=False, indent=2))
        raise SystemExit(1)

    print('结果：PASS —— 三处一致（替换页 %d 条 / 对照页 %d 条）%s'
          % (len(repl), len(comp),
             '，另 %d 处 WARN' % len(warns) if warns else ''))
    if args.json:
        print(json.dumps({'fails': [], 'warns': warns, 'pass': True},
                         ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
