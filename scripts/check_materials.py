# -*- coding: utf-8 -*-
"""
材料完备性检查（对应 SKILL.md Step 1 硬性门槛）

规则：
- 第 1 次 OA 必需材料：OA 通知书全文 / 申请文件（权利要求书 + 说明书）/ 审查员引用的对比文件全文
- 第 2 次及后续 OA 必需材料：以上三项 + 上次答复材料（上次《意见陈述书》+ 上次《权利要求修改对照页》）
- 任一必需项缺失或识别存疑（如 OCR 不可靠）→ 判定 FAIL：应停止流程，输出《材料缺口清单》，不进入后续步骤

**附图为可选项，缺失不阻塞（2026-09-03 修订）**：
本 skill 全程基于文本工作——区别特征比对、结合启示判断、超范围核对一律以权利要求书、
说明书与对比文件的**文字记载**为准；且按 amendment-scope-checklist，仅能从附图图形看出、
无文字记载的内容本就不能作为修改依据。既然从不解析图像内容，把附图缺失设为硬性阻塞项
并弹窗等待确认便无依据，只会在每次缺图案件上白白中断流程。故：
- 提供了附图 → 记录为已获得；
- 本案确无附图（--no-drawings）→ 记录为"本案无附图"；
- 未提供 → 仅提示一句"结构理解以文字化附图信息为准"，**不影响 PASS 与否**。

材料项编码（--present / --dubious 使用，逗号分隔）：
  oa           OA 通知书全文
  claims       权利要求书
  spec         说明书
  drawings     附图（**可选**，缺失不阻塞；可省略，也可用 --no-drawings 显式标注本案确无附图）
  contrast     审查员引用的对比文件全文（用 --contrast 指定所需篇数，默认 1）
  prior_reply  上次《意见陈述书》（仅第 2 次及后续 OA 必需）
  prior_amend  上次《权利要求修改对照页》（仅第 2 次及后续 OA 必需）

用法：
  python check_materials.py --round 1 --present oa,claims,spec,contrast
  python check_materials.py --round 1 --present oa,claims,spec,drawings,contrast
  python check_materials.py --round 2 --present oa,claims,spec,contrast,prior_reply,prior_amend --dubious spec
  python check_materials.py --round 1 --present oa,claims,spec,contrast --no-drawings

退出码：0 = 材料齐备（可进入 Step 2）；1 = 存在缺口（应停止流程）
"""
import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

REQUIRED_ROUND1 = [
    ('oa', 'OA 通知书全文'),
    ('claims', '权利要求书'),
    ('spec', '说明书'),
    ('contrast', '审查员引用的对比文件全文'),
]

REQUIRED_ROUND2_PLUS = REQUIRED_ROUND1 + [
    ('prior_reply', '上次《意见陈述书》'),
    ('prior_amend', '上次《权利要求修改对照页》'),
]

# 可选项：缺失只提示、不阻塞（理由见文件头"附图为可选项"说明）
OPTIONAL_ITEMS = [
    ('drawings', '附图'),
]


def main():
    ap = argparse.ArgumentParser(description='专利OA答复 材料完备性检查（SKILL.md Step 1 硬性门槛）')
    ap.add_argument('--round', type=int, default=1, help='第 N 次审查意见（>=2 视为后续 OA，需上次答复材料）')
    ap.add_argument('--present', default='', help='已获得材料编码，逗号分隔')
    ap.add_argument('--dubious', default='', help='识别存疑的材料编码，逗号分隔（OCR 识别存疑视为材料不完整）')
    ap.add_argument('--contrast', type=int, default=1, help='审查员引用的对比文件篇数（默认 1）')
    ap.add_argument('--no-drawings', action='store_true',
                    help='显式标注本案确无附图（附图为可选项，省略此参数同样不阻塞流程）')
    ap.add_argument('--files', default='', help='材料文件路径，逗号分隔（统计总规模，用于分流决策）')
    ap.add_argument('--json', action='store_true', help='额外输出 JSON 报告')
    args = ap.parse_args()

    required = REQUIRED_ROUND2_PLUS if args.round >= 2 else REQUIRED_ROUND1
    present = {x.strip() for x in args.present.split(',') if x.strip()}
    dubious = {x.strip() for x in args.dubious.split(',') if x.strip()}

    scale = None
    if args.files:
        total_chars, file_details, missing_files = 0, [], []
        for fp in args.files.split(','):
            fp = fp.strip()
            if not fp:
                continue
            p = Path(fp)
            if p.is_file():
                n = len(re.sub(r'\s', '', p.read_text(encoding='utf-8', errors='replace')))
                total_chars += n
                file_details.append((p.name, n))
            else:
                missing_files.append(fp)
        est_tokens = int(total_chars * 0.8)
        if total_chars > 80000:
            mode = '分步模式（> 80,000 字符）'
            advice = '强制分段执行：任务清单顶部加说明任务，Step 3 / 7 / 10 各设一个暂停点'
        elif total_chars > 40000:
            mode = '默认模式（定向读取）'
            advice = '一次跑完，但须采用定向读取：按特征关键词 / 段落号定位关键段落，禁止全量读入材料'
        else:
            mode = '默认模式'
            advice = '一次跑完，材料规模在常规范围内'
        scale = {
            'total_chars': total_chars, 'est_tokens': est_tokens,
            'mode': mode, 'advice': advice,
            'files': file_details, 'missing_files': missing_files,
        }

    rows, gaps = [], []
    for code, name in required:
        if code in dubious:
            rows.append((code, name, 'dubious', '识别存疑，视为材料不完整'))
            gaps.append((code, name, '识别存疑（OCR 等识别不可靠，需人工核对后重新确认）'))
        elif code in present:
            rows.append((code, name, 'ok', '已获得'))
        else:
            rows.append((code, name, 'missing', '缺失'))
            gaps.append((code, name, '缺失'))

    # 可选项：只记录与提示，不计入缺口、不影响退出码
    notes = []
    for code, name in OPTIONAL_ITEMS:
        if code in dubious:
            rows.append((code, name, 'dubious', '识别存疑（可选项，不影响流程）'))
            notes.append('%s 识别存疑（可选项，仅作提示）' % name)
        elif code in present:
            rows.append((code, name, 'ok', '已获得（可选项）'))
        elif args.no_drawings:
            rows.append((code, name, 'skip', '本案确无附图（--no-drawings）'))
        else:
            rows.append((code, name, 'opt', '未提供（可选项，不影响流程）'))
            notes.append('%s未提供 —— 结构理解以文字化附图信息为准'
                         '（说明书「附图说明」章节与附图标记一览表），不阻塞流程' % name)

    # 规模统计模式：仅传 --files 且未传 --present 时，只统计规模、不做完备性判定。
    # 若不做此分流，present 为空会使全部材料被判为"缺失"，在正确输出规模后误报 FAIL。
    if args.files and not args.present:
        if not scale:
            print('未获得有效文件，无法统计规模。')
            raise SystemExit(2)
        print('材料规模统计（仅统计，未做完备性判定）')
        print('  材料总规模：%d 字符（预估 %d token，共 %d 个文件）→ %s' % (
            scale['total_chars'], scale['est_tokens'], len(scale['files']), scale['mode']))
        print('  执行策略：%s' % scale['advice'])
        for fname, n in scale['files']:
            print('    - %s：%d 字符' % (fname, n))
        for fname in scale['missing_files']:
            print('    - %s：文件不存在（未计入规模）' % fname)
        print('提示：需做完备性判定时，请另附 --present <材料编码>（如 oa,claims,spec,contrast）。')
        if args.json:
            print(json.dumps({'scale': scale, 'scale_only': True, 'pass': None},
                             ensure_ascii=False, indent=2))
        return

    label = '第 %d 次审查意见' % args.round if args.round < 2 else '第 %d 次审查意见（后续 OA）' % args.round
    print('材料完备性检查（%s）' % label)
    for code, name, status, note in rows:
        icon = {'ok': '  OK', 'skip': 'SKIP', 'missing': 'MISS',
                'dubious': ' DUB', 'opt': ' OPT'}[status]
        print('  [%s] %s — %s' % (icon, name, note))
    for n in notes:
        print('  [提示] %s' % n)
    if args.contrast > 1:
        print('  （审查员引用 %d 篇对比文件，需全部获得）' % args.contrast)
    if scale:
        print('  材料总规模：%d 字符（预估 %d token，共 %d 个文件）→ %s' % (
            scale['total_chars'], scale['est_tokens'], len(scale['files']), scale['mode']))
        print('  执行策略：%s' % scale['advice'])
        for fname, n in scale['files']:
            print('    - %s：%d 字符' % (fname, n))
        for fname in scale['missing_files']:
            print('    - %s：文件不存在（未计入规模）' % fname)

    if gaps:
        print('结果：FAIL —— 材料存在缺口，按 SKILL.md Step 1 停止流程')
        print('《材料缺口清单》：')
        for _, name, why in gaps:
            print('  - %s：%s' % (name, why))
        print('缺口处理三选项（AI 不替用户选择）：')
        print('  ① 用户补充：补齐缺失材料后从 Step 1 重新运行；获取方向提示见 references/authoritative-sources.md（优先国内可访问源），AI 不代为检索。')
        print('  ② 降级处理：用户了解风险后明确要求继续，方可按 Step 1 降级模式处理（产出仅作工作底稿）。')
        print('  ③ 取消本次任务：流程终止，不生成任何初稿。')
        if args.json:
            print(json.dumps({
                'round': args.round, 'present': sorted(present), 'dubious': sorted(dubious),
                'items': [{'code': c, 'name': n, 'status': s} for c, n, s, _ in rows],
                'gaps': [{'code': c, 'name': n, 'why': w} for c, n, w in gaps],
                'scale': scale, 'pass': False,
            }, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    print('结果：PASS —— 材料齐备，可进入 Step 2 解析要素。')
    if args.json:
        print(json.dumps({
            'round': args.round, 'present': sorted(present), 'dubious': sorted(dubious),
            'items': [{'code': c, 'name': n, 'status': s} for c, n, s, _ in rows],
            'gaps': [], 'scale': scale, 'pass': True,
        }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
