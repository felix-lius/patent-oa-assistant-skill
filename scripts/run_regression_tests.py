# -*- coding: utf-8 -*-
"""
回归测试集（覆盖 scripts/ 全部 11 个检查工具的正反用例）

自包含运行：临时目录生成样例 → 逐个调用工具子进程 → 断言退出码与输出片段。
用于每次修改 skill 或脚本后快速验证行为未退化（回应评测"无法验证效果"痛点）。

用法：
  python run_regression_tests.py

退出码：0 = 全部通过；1 = 存在失败用例
"""
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SCRIPTS = Path(__file__).resolve().parent
PY = sys.executable

CONTENT_TYPES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                 '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                 '<Default Extension="xml" ContentType="application/xml"/>'
                 '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                 '</Types>')
RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>')


def make_docx(path, text):
    """构造最小合法 docx（含 word/document.xml），供交付物检查测试用。"""
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
           '<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p></w:body></w:document>' % text)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', CONTENT_TYPES)
        zf.writestr('_rels/.rels', RELS)
        zf.writestr('word/document.xml', xml)
        zf.writestr('word/_rels/document.xml.rels', '')


def run(*args):
    p = subprocess.run([PY, str(SCRIPTS / args[0])] + list(args[1:]),
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def setup(tmp):
    """生成全部样例文件，返回路径字典。"""
    d = {}

    good = tmp / 'good.md'
    good.write_text(
        '# 意见陈述书初稿\n\n'
        '尊敬的审查员：您好！十分感谢您的认真审查和提供的意见。\n\n'
        '针对审查意见，现答复如下：权利要求1与对比文件1的区别技术特征在于A部件设置于B位置。\n\n'
        '该特征并非本领域公知常识，结合对比文件2亦无启示。\n\n'
        '综上所述，恳请接受本意见陈述，早日批准本申请获得专利权。\n', encoding='utf-8')
    d['good'] = good

    bad = tmp / 'bad.md'
    bad.write_text(
        '# 意见陈述书初稿\n\n'
        '尊敬的审查员：您好！十分感谢您的认真审查和提供的意见。\n\n'
        '针对审查意见，现答复如下：（逐字引用权利要求1原文后分析）\n\n'
        '区别技术特征在于A部件设置于B位置（待核实：附图标记是否一致）。\n\n'
        '本领域技术人员容易想到，参见 references/inventive-step-analysis.md 的模式库。\n\n'
        'Step 4 已核查该特征，temp_opinion 中暂存。\n\n'
        '具体数值为 <占位>，请补充确认。\n\n'
        '恳请接受本意见陈述，早日批准本申请获得专利权。\n', encoding='utf-8')
    d['bad'] = bad

    attach = tmp / '附件_答复辅助材料汇总_2023101234567_20260827.md'
    attach.write_text(
        '# 附件·答复辅助材料汇总\n\n'
        '## 一、待核实事项清单\n\n（本次无待核实事项）\n\n'
        '## 二、引用锚定表\n\n## 三、提交前复核清单\n', encoding='utf-8')
    d['attach'] = attach

    claims_bad = tmp / '替换页_有问题.md'
    claims_bad.write_text(
        '1. 一种装置，其特征在于：所述A部件设置于B位置，如图2所示。\n'
        '2. 根据权利要求1所述的装置，其特征在于：还包括C部件，参照说明书第[0023]段。\n'
        '3. 一种方法，其特征在于：如说明书所述执行步骤S1。\n', encoding='utf-8')
    d['claims_bad'] = claims_bad

    claims_good = tmp / '替换页_干净.md'
    claims_good.write_text(
        '1. 一种装置，其特征在于：所述A部件设置于B位置。\n'
        '2. 根据权利要求1所述的装置，其特征在于：还包括C部件。\n', encoding='utf-8')
    d['claims_good'] = claims_good

    ai_bad = tmp / '初稿_A痕迹.md'
    ai_bad.write_text(
        '# 意见陈述书初稿\n\n'
        '值得注意的是，本申请的设计哲学与传统方案存在根本分野。\n\n'
        '首先，该方案实现了闭环；其次，赋能了整体架构。\n\n'
        '从结合启示阻断的角度看，四维比对显示无技术启示。\n\n'
        '恳请接受本意见陈述，早日批准本申请获得专利权。\n', encoding='utf-8')
    d['ai_bad'] = ai_bad

    law_ok = tmp / '法条_正确.md'
    law_ok.write_text(
        '本案涉及专利法第22条第3款规定的创造性审查。\n'
        '独立权利要求缺少必要技术特征，不符合实施细则第23条第2款的规定。\n'
        '修改不得超出原说明书和权利要求书记载的范围（专利法第33条）。\n', encoding='utf-8')
    d['law_ok'] = law_ok

    law_warn = tmp / '法条_可疑.md'
    law_warn.write_text('本案引用专利法第99条规定，请核对。\n', encoding='utf-8')
    d['law_warn'] = law_warn

    okdir = tmp / 'okdir'
    okdir.mkdir()
    make_docx(okdir / '意见陈述书初稿_2023101234567_20260827.docx', '尊敬的审查员：您好！')
    make_docx(okdir / '权利要求书替换页_2023101234567_20260827.docx', '1. 一种装置')
    make_docx(okdir / '权利要求修改对照页_2023101234567_20260827.docx', '对照表')
    (okdir / '附件_答复辅助材料汇总_2023101234567_20260827.md').write_text('# 附件', encoding='utf-8')
    d['okdir'] = okdir

    baddir = tmp / 'baddir'
    baddir.mkdir()
    make_docx(baddir / '意见陈述书初稿_2023.docx', '尊敬的审查员：您好！')  # 命名不合规
    (baddir / '权利要求修改对照页_2023101234567_20260827.docx').write_text('not a zip', encoding='utf-8')  # 损坏
    (baddir / '附件_答复辅助材料汇总_2023101234567_20260827.md').write_text('# 附件', encoding='utf-8')
    # 缺：权利要求书替换页
    d['baddir'] = baddir

    # ---- check_terms.py 样例（基准 + 待检） ----
    ref_notice = tmp / 'OA通知书.md'
    ref_notice.write_text(
        '申请号：202310123456.7\n'
        '发明名称：一种改进的电路装置\n'
        '第1次审查意见通知书\n', encoding='utf-8')
    d['ref_notice'] = ref_notice

    ref_claims = tmp / '原权利要求书.md'
    ref_claims.write_text(
        '发明名称：一种改进的电路装置\n'
        '1. 一种电路装置，包括壳体（101）和散热片（102），其特征在于：'
        '所述MCD（MOS-Controlled Diode，沟道二极管）设置于所述壳体（101）内。\n', encoding='utf-8')
    d['ref_claims'] = ref_claims

    terms_ok = tmp / '意见陈述书_术语一致.md'
    terms_ok.write_text(
        '申请号：202310123456.7\n'
        '发明名称：一种改进的电路装置\n'
        '针对第1次审查意见通知书，现答复如下：壳体（101）与散热片（102）……'
        '所述MCD（MOS-Controlled Diode，沟道二极管）……\n'
        '恳请接受本意见陈述，早日批准本申请获得专利权。\n', encoding='utf-8')
    d['terms_ok'] = terms_ok

    terms_bad_appno = tmp / '意见陈述书_申请号错.md'
    terms_bad_appno.write_text(
        '申请号：202410000000.8\n'
        '发明名称：一种改进的电路装置\n'
        '针对第1次审查意见通知书……\n', encoding='utf-8')
    d['terms_bad_appno'] = terms_bad_appno

    terms_bad_title = tmp / '意见陈述书_名称错.md'
    terms_bad_title.write_text(
        '申请号：202310123456.7\n'
        '发明名称：一种改进的电路装置和方法\n'
        '针对第1次审查意见通知书……\n', encoding='utf-8')
    d['terms_bad_title'] = terms_bad_title

    terms_warn_marker = tmp / '意见陈述书_新标记.md'
    terms_warn_marker.write_text(
        '申请号：202310123456.7\n'
        '发明名称：一种改进的电路装置\n'
        '针对第1次审查意见通知书……散热片（107）……\n', encoding='utf-8')
    d['terms_warn_marker'] = terms_warn_marker

    terms_warn_abbr = tmp / '意见陈述书_缩写错.md'
    terms_warn_abbr.write_text(
        '申请号：202310123456.7\n'
        '发明名称：一种改进的电路装置\n'
        '针对第1次审查意见通知书……所述MCD（Metal Oxide Controlled Diode）……\n', encoding='utf-8')
    d['terms_warn_abbr'] = terms_warn_abbr

    # ---- check_citations.py 样例（引用比对基准 + 待检） ----
    cite_claims = tmp / '基准权利要求书_引用.md'
    cite_claims.write_text(
        '发明名称：一种改进的电路装置\n'
        '1. 一种电路装置，包括壳体（101）和散热片（102），其特征在于：'
        '所述散热片（102）设置于所述壳体（101）的外表面。\n', encoding='utf-8')
    d['cite_claims'] = cite_claims

    cite_pass = tmp / '初稿_引用一致.md'
    cite_pass.write_text(
        '# 意见陈述书初稿\n\n'
        '区别技术特征为所述散热片（102）设置于所述壳体（101）的外表面。\n', encoding='utf-8')
    d['cite_pass'] = cite_pass

    cite_warn = tmp / '初稿_引用改写.md'
    cite_warn.write_text(
        '# 意见陈述书初稿\n\n'
        '区别技术特征为散热片（102）设置在壳体（101）外表面。\n', encoding='utf-8')
    d['cite_warn'] = cite_warn

    # ---- check_claim_links.py 样例 ----
    links_pass = tmp / '替换页_引用正常.md'
    links_pass.write_text(
        '1. 一种装置，其特征在于：包括A部件。\n'
        '2. 根据权利要求1所述的装置，其特征在于：还包括B部件。\n'
        '3. 根据权利要求1或2所述的装置，其特征在于：还包括C部件。\n', encoding='utf-8')
    d['links_pass'] = links_pass

    links_fail = tmp / '替换页_引用悬空.md'
    links_fail.write_text(
        '1. 一种装置，其特征在于：包括A部件。\n'
        '2. 根据权利要求1所述的装置，其特征在于：还包括B部件。\n'
        '3. 根据权利要求5所述的装置，其特征在于：还包括C部件。\n', encoding='utf-8')
    d['links_fail'] = links_fail

    links_fail_backref = tmp / '替换页_引用倒退.md'
    links_fail_backref.write_text(
        '1. 一种装置，其特征在于：包括A部件。\n'
        '2. 根据权利要求3所述的装置，其特征在于：还包括B部件。\n'
        '3. 根据权利要求2所述的装置，其特征在于：还包括C部件。\n', encoding='utf-8')
    d['links_fail_backref'] = links_fail_backref

    # ---- check_argument_lengths.py 样例 ----
    arglen_pass = tmp / '初稿_字数正常.md'
    arglen_pass.write_text('# 意见陈述书初稿\n\n## 区别特征（1）论证\n' + '论' * 1500 + '\n', encoding='utf-8')
    d['arglen_pass'] = arglen_pass

    arglen_warn_short = tmp / '初稿_字数不足.md'
    arglen_warn_short.write_text('# 意见陈述书初稿\n\n## 区别特征（1）论证\n' + '论' * 100 + '\n', encoding='utf-8')
    d['arglen_warn_short'] = arglen_warn_short

    arglen_warn_long = tmp / '初稿_字数超限.md'
    arglen_warn_long.write_text('# 意见陈述书初稿\n\n## 区别特征（1）论证\n' + '论' * 2500 + '\n', encoding='utf-8')
    d['arglen_warn_long'] = arglen_warn_long

    # ---- check_materials.py 规模统计（--files）样例 ----
    scale_small = tmp / '材料_小通知书.md'
    scale_small.write_text('通知正文' * 500, encoding='utf-8')  # 2000 字，远低于阈值
    d['scale_small'] = scale_small

    # ---- 回归护栏：两处历史误报的防回退用例 ----
    underline_ok = tmp / '初稿_含下划线标记.md'
    underline_ok.write_text(
        '# 意见陈述书初稿\n\n'
        '尊敬的审查员：您好！\n\n'
        '修改说明：将权利要求1修改为<u>所述散热片（102）设置于所述壳体（101）的外表面</u>。\n\n'
        '恳请接受本意见陈述，早日批准本申请获得专利权。\n', encoding='utf-8')
    d['underline_ok'] = underline_ok

    ai_attachment = tmp / '附件_答复辅助材料汇总_含框架词.md'
    ai_attachment.write_text(
        '# 附件·答复辅助材料汇总\n\n'
        '## 一、待核实事项清单\n\n'
        '创造性贡献度评估详见提交前复核清单。\n', encoding='utf-8')
    d['ai_attachment'] = ai_attachment

    return d


def main():
    with tempfile.TemporaryDirectory() as tmp_s:
        tmp = Path(tmp_s)
        d = setup(tmp)

        cases = [
            # ---- check_materials.py ----
            ('materials_pass_round1', ('check_materials.py', '--round', '1',
             '--present', 'oa,claims,spec,drawings,contrast'), 0, 'PASS'),
            ('materials_fail_missing_contrast', ('check_materials.py', '--round', '1',
             '--present', 'oa,claims,spec,drawings'), 1, '审查员引用的对比文件全文'),
            ('materials_fail_round2_prior', ('check_materials.py', '--round', '2',
             '--present', 'oa,claims,spec,drawings,contrast'), 1, '上次《意见陈述书》'),
            ('materials_fail_dubious', ('check_materials.py', '--round', '1',
             '--present', 'oa,claims,spec,drawings,contrast', '--dubious', 'spec'), 1, '识别存疑'),
            ('materials_pass_no_drawings', ('check_materials.py', '--round', '1',
             '--present', 'oa,claims,spec,contrast', '--no-drawings'), 0, 'PASS'),
            ('materials_scale_output', ('check_materials.py', '--round', '1',
             '--present', 'oa,claims,spec,drawings,contrast', '--files', str(d['scale_small'])), 0, '建议 不中断模式'),
            # ---- check_clean_markers.py ----
            ('markers_pass_clean', ('check_clean_markers.py', '--input', str(d['good'])), 0, 'PASS'),
            ('markers_fail_bad', ('check_clean_markers.py', '--input', str(d['bad'])), 1, 'FAIL'),
            ('markers_pass_attachment_exempt', ('check_clean_markers.py', '--input', str(d['attach'])), 0, 'PASS'),
            ('markers_pass_underline_ok', ('check_clean_markers.py', '--input', str(d['underline_ok'])), 0, 'PASS'),
            # ---- check_deliverables.py ----
            ('deliverables_pass_okdir', ('check_deliverables.py', '--dir', str(d['okdir'])), 0, 'PASS'),
            ('deliverables_fail_baddir', ('check_deliverables.py', '--dir', str(d['baddir'])), 1, 'FAIL'),
            # ---- check_deadline.py ----
            ('deadline_basic_4m', ('check_deadline.py', '--issue', '2026-06-01', '--months', '4'), 0, '2026-10-16'),
            ('deadline_weekend_roll', ('check_deadline.py', '--received', '2026-06-06', '--months', '0'), 0, '2026-06-08'),
            ('deadline_holiday_roll', ('check_deadline.py', '--received', '2026-10-01', '--months', '0'), 0, '2026-10-05'),
            # ---- check_law_citations.py ----
            ('law_citations_ok', ('check_law_citations.py', '--input', str(d['law_ok'])), 0, 'PASS'),
            ('law_citations_warn_hint', ('check_law_citations.py', '--input', str(d['law_warn'])), 0, '未收录'),
            # ---- check_claims_selfcontained.py ----
            ('claims_fail_bad', ('check_claims_selfcontained.py', '--input', str(d['claims_bad'])), 1, 'FAIL'),
            ('claims_pass_good', ('check_claims_selfcontained.py', '--input', str(d['claims_good'])), 0, 'PASS'),
            # ---- check_ai_traces.py ----
            ('ai_traces_fail_bad', ('check_ai_traces.py', '--input', str(d['ai_bad'])), 1, 'FAIL'),
            ('ai_traces_pass_good', ('check_ai_traces.py', '--input', str(d['good'])), 0, 'PASS'),
            ('ai_traces_attachment_exempt', ('check_ai_traces.py', '--input', str(d['ai_attachment'])), 0, 'PASS'),
            # ---- check_terms.py ----
            ('terms_pass', ('check_terms.py', '--reference', str(d['ref_notice']),
             '--reference', str(d['ref_claims']), '--input', str(d['terms_ok'])), 0, 'PASS'),
            ('terms_fail_appno', ('check_terms.py', '--reference', str(d['ref_notice']),
             '--reference', str(d['ref_claims']), '--input', str(d['terms_bad_appno'])), 1, '申请号不一致'),
            ('terms_fail_title', ('check_terms.py', '--reference', str(d['ref_notice']),
             '--reference', str(d['ref_claims']), '--input', str(d['terms_bad_title'])), 1, '发明名称不一致'),
            ('terms_warn_marker', ('check_terms.py', '--reference', str(d['ref_notice']),
             '--reference', str(d['ref_claims']), '--input', str(d['terms_warn_marker'])), 0, '疑似新增附图标记'),
            ('terms_warn_abbr', ('check_terms.py', '--reference', str(d['ref_notice']),
             '--reference', str(d['ref_claims']), '--input', str(d['terms_warn_abbr'])), 0, '缩写全称不一致'),
            ('terms_strict_fail', ('check_terms.py', '--reference', str(d['ref_notice']),
             '--reference', str(d['ref_claims']), '--input', str(d['terms_warn_marker']), '--strict'), 1, 'FAIL'),
            # ---- check_citations.py ----
            ('citations_pass', ('check_citations.py', '--claims', str(d['cite_claims']),
             '--input', str(d['cite_pass'])), 0, 'PASS'),
            ('citations_warn_rewrite', ('check_citations.py', '--claims', str(d['cite_claims']),
             '--input', str(d['cite_warn'])), 0, '疑似改写引用'),
            ('citations_strict_fail', ('check_citations.py', '--claims', str(d['cite_claims']),
             '--input', str(d['cite_warn']), '--strict'), 1, 'FAIL'),
            # ---- check_claim_links.py ----
            ('claim_links_pass', ('check_claim_links.py', '--input', str(d['links_pass'])), 0, 'PASS'),
            ('claim_links_fail_missing', ('check_claim_links.py', '--input', str(d['links_fail'])), 1, '引用悬空'),
            ('claim_links_fail_backref', ('check_claim_links.py', '--input', str(d['links_fail_backref'])), 1, '引用错误'),
            # ---- check_argument_lengths.py ----
            ('arglen_pass', ('check_argument_lengths.py', '--input', str(d['arglen_pass'])), 0, 'PASS'),
            ('arglen_warn_short', ('check_argument_lengths.py', '--input', str(d['arglen_warn_short'])), 0, '论证不足'),
            ('arglen_warn_long', ('check_argument_lengths.py', '--input', str(d['arglen_warn_long'])), 0, '超出建议区间'),
            ('arglen_strict_fail', ('check_argument_lengths.py', '--input', str(d['arglen_warn_short']), '--strict'), 1, 'FAIL'),
        ]

        passed = failed = 0
        print('回归测试（%d 个用例）' % len(cases))
        for name, argv, expect_code, expect_text in cases:
            code, out = run(*argv)
            ok = (code == expect_code) and (expect_text in out)
            if ok:
                passed += 1
                print('  [PASS] %s' % name)
            else:
                failed += 1
                print('  [FAIL] %s —— 期望退出码 %d / 输出含 "%s"，实际 %d / 输出见下' %
                      (name, expect_code, expect_text, code))
                for line in out.strip().split('\n')[:12]:
                    print('        | ' + line)

        print('结果：%d 通过 / %d 失败' % (passed, failed))
        raise SystemExit(0 if failed == 0 else 1)


if __name__ == '__main__':
    main()
