# -*- coding: utf-8 -*-
"""
材料完备性检查（对应 SKILL.md Step 1 硬性门槛）

规则：
- 第 1 次 OA 必需材料：OA 通知书全文 / 申请文件（权利要求书 + 说明书 + 附图）/ 审查员引用的对比文件全文
- 第 2 次及后续 OA 必需材料：以上三项 + 上次答复材料（上次《意见陈述书》+ 上次《权利要求修改对照页》）
- 任一必需项缺失或识别存疑（如 OCR 不可靠）→ 判定 FAIL：应停止流程，输出《材料缺口清单》，不进入后续步骤

材料项编码（--present / --dubious 使用，逗号分隔）：
  oa           OA 通知书全文
  claims       权利要求书
  spec         说明书
  drawings     附图（本案确无附图时可用 --no-drawings 跳过，如纯化学领域案件）
  contrast     审查员引用的对比文件全文（用 --contrast 指定所需篇数，默认 1）
  prior_reply  上次《意见陈述书》（仅第 2 次及后续 OA 必需）
  prior_amend  上次《权利要求修改对照页》（仅第 2 次及后续 OA 必需）

用法：
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
    ('drawings', '附图'),
    ('contrast', '审查员引用的对比文件全文'),
]

REQUIRED_ROUND2_PLUS = REQUIRED_ROUND1 + [
    ('prior_reply', '上次《意见陈述书》'),
    ('prior_amend', '上次《权利要求修改对照页》'),
]


def main():
    ap = argparse.ArgumentParser(description='专利OA答复 材料完备性检查（SKILL.md Step 1 硬性门槛）')
    ap.add_argument('--round', type=int, default=1, help='第 N 次审查意见（>=2 视为后续 OA，需上次答复材料）')
    ap.add_argument('--present', default='', help='已获得材料编码，逗号分隔')
    ap.add_argument('--dubious', default='', help='识别存疑的材料编码，逗号分隔（OCR 识别存疑视为材料不完整）')
    ap.add_argument('--contrast', type=int, default=1, help='审查员引用的对比文件篇数（默认 1）')
    ap.add_argument('--no-drawings', action='store_true', help='本案确无附图（如纯化学领域），跳过附图检查')
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
        scale = {
            'total_chars': total_chars, 'est_tokens': est_tokens,
            'mode': '分步模式' if total_chars > 30000 else '不中断模式',
            'files': file_details, 'missing_files': missing_files,
        }

    rows, gaps = [], []
    for code, name in required:
        if code == 'drawings' and args.no_drawings:
            rows.append((code, name, 'skip', '本案无附图（--no-drawings）'))
            continue
        if code in dubious:
            rows.append((code, name, 'dubious', '识别存疑，视为材料不完整'))
            gaps.append((code, name, '识别存疑（OCR 等识别不可靠，需人工核对后重新确认）'))
        elif code in present:
            rows.append((code, name, 'ok', '已获得'))
        else:
            rows.append((code, name, 'missing', '缺失'))
            gaps.append((code, name, '缺失'))

    label = '第 %d 次审查意见' % args.round if args.round < 2 else '第 %d 次审查意见（后续 OA）' % args.round
    print('材料完备性检查（%s）' % label)
    for code, name, status, note in rows:
        icon = {'ok': '  OK', 'skip': 'SKIP', 'missing': 'MISS', 'dubious': ' DUB'}[status]
        print('  [%s] %s — %s' % (icon, name, note))
    if args.contrast > 1:
        print('  （审查员引用 %d 篇对比文件，需全部获得）' % args.contrast)
    if scale:
        print('  材料总规模：%d 字符（预估 %d token，共 %d 个文件）→ 建议 %s' % (
            scale['total_chars'], scale['est_tokens'], len(scale['files']), scale['mode']))
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
