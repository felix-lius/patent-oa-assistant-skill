# -*- coding: utf-8 -*-
"""
答复期限计算（对应 SKILL.md Step 2：答复期限从通知书第 8 项读取）

规则（专利法实施细则 + 审查指南）：
- 推定收到日 = 发文日 + 15 日（通知书发文日起 15 日为推定收到）
- 答复期限 = 收到日起 N 个月（发明第一次审查意见通常 4 个月，后续审查意见通常 2 个月，
  以通知书第 8 项载明的期限为准；亦可用 --days 处理按日计算的期限）
- 期限届满日遇周六/周日或法定节假日，顺延至其后第一个工作日
- 逾期不答复视为撤回申请

用法：
  python check_deadline.py --issue 2026-06-01 --months 4
  python check_deadline.py --issue 2026-06-01 --months 2 --holidays 2026-06-19
  python check_deadline.py --received 2026-06-16 --months 4

退出码：0 = 正常完成（无论是否逾期，均输出计算明细与提醒）
"""
import argparse
import calendar
import json
import sys
from datetime import date, timedelta

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 法定节假日（非调休日）。农历节日日期随年份变化，表内为已知年份；
# 年份不在表内时仅顺延周六周日。最终以国务院/国知局公告为准，可用 --holidays 增补。
STATIC_HOLIDAYS = {
    2026: [(1, 1), (2, 17), (2, 18), (2, 19), (4, 5), (5, 1), (6, 19), (9, 25), (10, 1), (10, 2), (10, 3)],
}


def add_months(d, months):
    """日期加 N 个月（月对月，处理月末如 1月31日+1月=2月28/29日）。"""
    if months <= 0:
        return d
    total = d.year * 12 + d.month - 1 + months
    y, m = divmod(total, 12)
    m += 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


def is_holiday(d, holiday_set):
    return d in holiday_set


def roll_deadline(d, holiday_set):
    """期限届满日遇周六/周日/法定节假日，顺延至其后第一个工作日。"""
    while d.weekday() >= 5 or is_holiday(d, holiday_set):
        d += timedelta(days=1)
    return d


def parse_holidays(extra):
    out = set()
    for h in extra.split(','):
        h = h.strip()
        if not h:
            continue
        out.add(date.fromisoformat(h))
    return out


def main():
    ap = argparse.ArgumentParser(description='专利OA答复 期限计算（SKILL.md Step 2）')
    ap.add_argument('--issue', help='通知书发文日（YYYY-MM-DD）')
    ap.add_argument('--received', help='收到日（YYYY-MM-DD，不填则按发文日+15日推定）')
    ap.add_argument('--months', type=int, default=4, help='答复期限月数（发明首次OA通常4，后续OA通常2，以通知书为准）')
    ap.add_argument('--days', type=int, default=0, help='附加天数（按日计算期限时用）')
    ap.add_argument('--holidays', default='', help='追加法定节假日（YYYY-MM-DD，逗号分隔，以官方公告为准）')
    ap.add_argument('--json', action='store_true', help='额外输出 JSON 报告')
    args = ap.parse_args()

    if not args.issue and not args.received:
        ap.error('必须提供 --issue 或 --received')

    issue = date.fromisoformat(args.issue) if args.issue else None
    received = date.fromisoformat(args.received) if args.received else (issue + timedelta(days=15))

    holiday_set = parse_holidays(args.holidays)
    for y, pairs in STATIC_HOLIDAYS.items():
        for mo, dy in pairs:
            holiday_set.add(date(y, mo, dy))

    raw = add_months(received, args.months) + timedelta(days=args.days)
    deadline = roll_deadline(raw, holiday_set)
    today = date.today()
    remain = (deadline - today).days

    print('答复期限计算')
    if issue:
        print('  发文日：%s' % issue)
    print('  推定收到日：%s%s' % (received, '（发文日+15日）' if args.issue else '（用户给定）'))
    print('  答复期限：%d 个月 %d 天' % (args.months, args.days))
    print('  期限届满日（顺延前）：%s' % raw)
    print('  答复截止日（顺延后）：%s' % deadline)
    if remain > 0:
        print('  剩余时间：%d 天（今天 %s）' % (remain, today))
    elif remain == 0:
        print('  截止日期就是今天：%s' % today)
    else:
        print('  提醒：已逾期 %d 天（今天 %s），逾期未答复视为撤回申请' % (-remain, today))
    print('  节假日顺延：%s（周六/周日自动顺延，表内法定节假日见 STATIC_HOLIDAYS，以官方公告为准）'
          % ('已启用' if holiday_set else '未启用'))

    if args.json:
        print(json.dumps({
            'issue': str(issue) if issue else None, 'received': str(received),
            'months': args.months, 'days': args.days,
            'raw_deadline': str(raw), 'deadline': str(deadline),
            'remaining_days': remain, 'today': str(today),
        }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
