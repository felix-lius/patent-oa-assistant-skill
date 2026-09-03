# -*- coding: utf-8 -*-
"""
回归测试集（覆盖 scripts/ 全部 11 个检查工具的正反用例）

自包含运行：临时目录生成样例 → 逐个调用工具子进程 → 断言退出码与输出片段。
用于每次修改 skill 或脚本后快速验证行为未退化（回应评测"无法验证效果"痛点）。

用法：
  python run_regression_tests.py

退出码：0 = 全部通过；1 = 存在失败用例
"""
import re
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
        '所述散热片（102）设置于所述壳体（101）的外表面。\n', encoding='utf-8')
    d['cite_pass'] = cite_pass

    cite_warn = tmp / '初稿_引用改写.md'
    # 实测覆盖率 76.7%（论述前缀 + 完整原文），落入 WARN 区间（60%~90%）。
    # 注：本工具按字符 3-gram 覆盖率判定，对"完整引用+论述拼接"敏感，
    # 对"轻度改写"（去"所述"、"于"改"在"）覆盖率仅约 52%，属方法固有局限，不计为用例。
    cite_warn.write_text(
        '# 意见陈述书初稿\n\n'
        '区别技术特征为所述散热片（102）设置于所述壳体（101）的外表面', encoding='utf-8')
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
    scale_small.write_text('通知正文' * 500, encoding='utf-8')  # 2000 字，≤ 40000 档
    d['scale_small'] = scale_small

    scale_mid = tmp / '材料_中规模.md'
    scale_mid.write_text('通知正文' * 15000, encoding='utf-8')  # 60000 字，40000~80000 档
    d['scale_mid'] = scale_mid

    scale_large = tmp / '材料_大规模.md'
    scale_large.write_text('通知正文' * 25000, encoding='utf-8')  # 100000 字，> 80000 档
    d['scale_large'] = scale_large

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

    # ---- 回归护栏：AI 痕迹扫描的三类豁免（历史误报，防回退）----
    ai_exempt_mandatory = tmp / '初稿_模板强制措辞.md'
    ai_exempt_mandatory.write_text(
        '# 意见陈述书\n\n'
        '一、修改说明\n\n'
        '发明人相信，经过上述陈述后，本申请文件已克服了本次审查意见中所指出的缺陷。'
        '恳请接受本意见陈述，以本次提交的文本为基础，早日批准本申请获得专利权。\n', encoding='utf-8')
    d['ai_exempt_mandatory'] = ai_exempt_mandatory

    ai_exempt_block = tmp / '初稿_含提交时删除区块.md'
    ai_exempt_block.write_text(
        '# 意见陈述书\n\n'
        '（以下为AI答复策略说明，提交时删除）\n\n'
        '## 答复策略说明\n\n'
        '首先，本案前景评估为强。其次，推荐最小必要修改。\n\n'
        '---\n\n'
        '尊敬的审查员：\n\n'
        '一、修改说明\n\n'
        '发明人对权利要求1作出限缩性修改。\n', encoding='utf-8')
    d['ai_exempt_block'] = ai_exempt_block

    ai_exempt_numdot = tmp / '初稿_含权利要求编号.md'
    ai_exempt_numdot.write_text(
        '# 意见陈述书\n\n'
        '修改后的权利要求1如下：\n\n'
        '> 1.一种3D激光雷达，其特征在于，包括竖向扫描单元，所述竖向扫描单元包括安装座(1)、'
        '固定于所述安装座(1)上的防护罩(16)；\n', encoding='utf-8')
    d['ai_exempt_numdot'] = ai_exempt_numdot

    # ---- check_amendment_risk.py ----
    amend_pass = tmp / '权利要求修改对照页_pass.md'
    amend_pass.write_text(
        '# 权利要求修改对照页\n\n'
        '| 序号 | 原权利要求文本 | 修改后文本 | 修改标记 | 修改依据出处 | 超范围风险 |\n'
        '|---|---|---|---|---|---|\n'
        '| 1 | 原文本A | 修改后文本A | 新增 | 原权利要求2 | \U0001F7E2 低 |\n'
        '| 2 | 原文本B | 修改后文本B | 新增 | 说明书第[0021]段 | \U0001F7E1 中 |\n', encoding='utf-8')
    d['amend_pass'] = amend_pass

    amend_fail = tmp / '权利要求修改对照页_fail.md'
    amend_fail.write_text(
        '# 权利要求修改对照页\n\n'
        '| 序号 | 原权利要求文本 | 修改后文本 | 修改标记 | 修改依据出处 | 超范围风险 |\n'
        '|---|---|---|---|---|---|\n'
        '| 1 | 原文本A | 修改后文本A | 新增 | 无出处 | \U0001F534 高 |\n', encoding='utf-8')
    d['amend_fail'] = amend_fail

    # 护栏：等级定义说明行含红点，但属说明文字，不得误判为高风险修改
    amend_def = tmp / '权利要求修改对照页_def.md'
    amend_def.write_text(
        '# 权利要求修改对照页\n\n'
        '| 1 | 原文本A | 修改后文本A | 新增 | 原权利要求2 | \U0001F7E2 低 |\n\n'
        '说明：超范围风险等级：\U0001F7E2 低=有明确原始出处；'
        '\U0001F7E1 中=隐含可直接确定；\U0001F534 高=无出处，此类修改一律不得列入。\n', encoding='utf-8')
    d['amend_def'] = amend_def

    amend_docx = tmp / '权利要求修改对照页_docx.docx'
    make_docx(amend_docx, '| 1 | 原文本A | 修改后文本A | 新增 | 无出处 | \U0001F534 高 |')
    d['amend_docx'] = amend_docx

    # 护栏：附件为正文外内部记录，模板要求其含"Step N 产出""（逐字引用）"等字样，
    # 此类框架术语与执行指令在附件中合法，不得判为标记残留。
    attach_frame = tmp / '附件_含框架术语.md'
    attach_frame.write_text(
        '# 附件·答复辅助材料汇总\n\n'
        '## 一、特征对应关系核查表（Step 4 产出）\n\n'
        '| # | 审查员认定 | 本申请原文（逐字引用） | 对比文件原文（逐字引用） | 核查结论 |\n'
        '|---|---|---|---|---|\n'
        '| 1 | D1 公开了A部件 | 原文A | 原文B | 真实对应 |\n\n'
        '## 二、结合启示阻断分析表（Step 7 产出）\n\n'
        '| 层次 | 论据 | 出处 |\n'
        '|---|---|---|\n'
        '| 目的性驱动缺失 | D2 该特征系为解决其自身问题而设 | D2 第[0012]段 |\n', encoding='utf-8')
    d['attach_frame'] = attach_frame

    # ---- check_amended_claims.py（三处一致性 + 多项独权重叠）----
    amd_rep = tmp / '权利要求书替换页_amd.md'
    amd_rep.write_text(
        '权利要求书替换页\n\n'
        '申请号：20240101000000.0\n'
        '发明创造名称：一种示例装置\n\n'
        '1. 一种示例装置，其特征在于，包括A部件(1)、设置于所述A部件(1)上的B位置；'
        '所述C部件(3)设置于所述B位置。\n\n'
        '2. 如权利要求1所述的一种示例装置，其特征在于，'
        '所述D部件(4)与所述C部件(3)相邻设置。\n', encoding='utf-8')
    d['amd_rep'] = amd_rep

    amd_cmp_ok = tmp / '权利要求修改对照页_amd.md'
    amd_cmp_ok.write_text(
        '# 权利要求修改对照页\n\n'
        '申请号：20240101000000.0\n'
        '发明创造名称：一种示例装置\n\n'
        '| 序号 | 原权利要求文本 | 修改后文本 | 修改标记 | 修改依据出处 | 超范围风险 |\n'
        '|---|---|---|---|---|---|\n'
        '| 1 | 原文本 | 一种示例装置，其特征在于，包括A部件(1)、设置于所述A部件(1)上的B位置；'
        '所述C部件(3)设置于所述B位置。 | 新增 | 原权利要求2 | 低 |\n', encoding='utf-8')
    d['amd_cmp_ok'] = amd_cmp_ok

    # 少写入了并入的特征 → 与替换页不一致，应 FAIL
    amd_cmp_bad = tmp / '权利要求修改对照页_amd_bad.md'
    amd_cmp_bad.write_text(
        '# 权利要求修改对照页\n\n'
        '| 序号 | 原权利要求文本 | 修改后文本 | 修改标记 | 修改依据出处 | 超范围风险 |\n'
        '|---|---|---|---|---|---|\n'
        '| 1 | 原文本 | 一种示例装置，其特征在于，包括A部件(1)、'
        '设置于所述A部件(1)上的B位置。 | 新增 | 原权利要求2 | 低 |\n', encoding='utf-8')
    d['amd_cmp_bad'] = amd_cmp_bad

    # 分段型对照页（**修改后文本** 标题 + 引用块），须与表格型同样可解析
    amd_cmp_sect = tmp / '权利要求修改对照页_sect.md'
    amd_cmp_sect.write_text(
        '# 权利要求修改对照页\n\n'
        '申请号：20240101000000.0\n'
        '发明创造名称：一种示例装置\n\n'
        '### 权利要求1（原权利要求1 + 原权利要求2）\n\n'
        '**修改后文本（完整全文）**\n\n'
        '> 1. 一种示例装置，其特征在于，包括A部件(1)、设置于所述A部件(1)上的B位置；\n'
        '> 所述C部件(3)设置于所述B位置。\n', encoding='utf-8')
    d['amd_cmp_sect'] = amd_cmp_sect

    amd_opi = tmp / '意见陈述书初稿_amd.md'
    amd_opi.write_text(
        '意见陈述书\n\n'
        '申请号：20240101000000.0\n'
        '发明创造名称：一种示例装置\n\n'
        '一、修改说明\n\n'
        '1. 将原权利要求2 的全部附加技术特征并入原权利要求1。\n\n'
        '2. 上述修改均未超出原说明书和权利要求书记载的范围，符合专利法第33条的规定。\n',
        encoding='utf-8')
    d['amd_opi'] = amd_opi

    # 两项同主题独权高度重叠 → 应提示重复保护/单一性风险（WARN，不阻断）
    amd_rep_overlap = tmp / '权利要求书替换页_overlap.md'
    amd_rep_overlap.write_text(
        '权利要求书替换页\n\n'
        '申请号：20240101000000.0\n'
        '发明创造名称：一种示例装置\n\n'
        '1. 一种示例装置，其特征在于，包括A部件(1)、设置于所述A部件(1)上的B位置；'
        '所述C部件(3)设置于所述B位置。\n\n'
        '2. 一种示例装置，其特征在于，包括A部件(1)、设置于所述A部件(1)上的B位置；'
        '所述C部件(3)设置于所述B位置，且所述C部件(3)与所述A部件(1)平行设置。\n',
        encoding='utf-8')
    d['amd_rep_overlap'] = amd_rep_overlap

    amd_rep_badapno = tmp / '权利要求书替换页_badapno.md'
    amd_rep_badapno.write_text(
        '权利要求书替换页\n\n'
        '申请号：2024099999999.9\n'
        '发明创造名称：一种示例装置\n\n'
        '1. 一种示例装置，其特征在于，包括A部件(1)、设置于所述A部件(1)上的B位置；'
        '所述C部件(3)设置于所述B位置。\n', encoding='utf-8')
    d['amd_rep_badapno'] = amd_rep_badapno

    return d


# ==================== 端到端集成测试（产物由模板派生） ====================
# 目的：单脚本单元测试覆盖不到"模板↔脚本""Step↔Step"的交叉点。
# 本组用例不手写样例，而是**从 opinion-letter-template.md 的模板代码块派生产物**，
# 再对产物跑全套机检。模板引入任何与脚本冲突的写法（如【】、框架术语、半角标点），
# 会随派生进入产物并被机检捕获，从而把"实跑才撞见"提前到"改完就 FAIL"。

ROOT = SCRIPTS.parent
TEMPLATE_MD = ROOT / 'references' / 'opinion-letter-template.md'

E2E_APPNO = '20240101000000.0'
E2E_TITLE = '一种示例装置'
E2E_DATE = '20260101'

# —— 原权利要求书（reference，供 check_citations / check_terms 作基准）——
REF_CLAIMS = (
    '(21)申请号 20240101000000.0\n'
    '(54)发明名称\n'
    '一种示例装置\n\n'
    '1. 一种示例装置，其特征在于，包括A部件(1)、设置于所述A部件(1)上的B位置。\n\n'
    '2. 如权利要求1所述的一种示例装置，其特征在于，所述C部件(3)设置于所述B位置。\n\n'
    '3. 如权利要求1所述的一种示例装置，其特征在于，所述D部件(4)与所述C部件(3)相邻设置。\n\n'
    '4. 如权利要求3所述的一种示例装置，其特征在于，所述A部件(1)上还设有安装座(5)。\n'
)

# —— 替换后的权利要求全文（对应"并入原权利要求2"后的方案）——
E2E_REPLACE = (
    '权利要求书替换页\n\n'
    '申请号：20240101000000.0\n'
    '发明创造名称：一种示例装置\n\n'
    '修改说明：本次修改为答复第一次审查意见通知书而作出。将原权利要求2 的全部附加技术特征'
    '并入原权利要求1；原权利要求3、4 作编号适应性调整。修改后的权利要求书共 3 项。'
    '上述修改均未超出原说明书和权利要求书记载的范围，符合专利法第33条的规定。\n\n'
    '1. 一种示例装置，其特征在于，包括A部件(1)、设置于所述A部件(1)上的B位置；'
    '所述C部件(3)设置于所述B位置。\n\n'
    '2. 如权利要求1所述的一种示例装置，其特征在于，所述D部件(4)与所述C部件(3)相邻设置。\n\n'
    '3. 如权利要求2所述的一种示例装置，其特征在于，所述A部件(1)上还设有安装座(5)。\n'
)

E2E_COMPARE = (
    '# 权利要求修改对照页\n\n'
    '申请号：20240101000000.0\n'
    '发明创造名称：一种示例装置\n\n'
    '| 新序号 | 原序号 | 修改动作 | 附加技术特征是否改动 |\n'
    '|---|---|---|---|\n'
    '| 1 | 1 + 2 | 特征上移合并 | 是（并入原权利要求2 全部） |\n'
    '| 2 | 3 | 编号调整 | 否 |\n'
    '| 3 | 4 | 编号调整 | 否 |\n\n'
    '| 序号 | 原权利要求文本 | 修改后文本 | 修改标记 | 修改依据出处 | 超范围风险 |\n'
    '|---|---|---|---|---|---|\n'
    '| 1 | 一种示例装置，其特征在于，包括A部件(1)、设置于所述A部件(1)上的B位置。 | '
    '一种示例装置，其特征在于，包括A部件(1)、设置于所述A部件(1)上的B位置；'
    '所述C部件(3)设置于所述B位置。 | 新增 | 原权利要求2 | 低 |\n'
)

E2E_ATTACH = (
    '# 附件·答复辅助材料汇总\n\n'
    '申请号：20240101000000.0\n'
    '发明创造名称：一种示例装置\n\n'
    '## 三、待核实事项汇总清单\n\n'
    '| # | 位置 | 待核实内容 | 处理指引 | 状态 |\n'
    '|---|---|---|---|---|\n'
    '| 1 | 第二步 | 对比文件段落号 | 对照原文补入 | 待人工复核 |\n'
)

_AMEND = (
    '1. 将原权利要求2 的全部附加技术特征并入原权利要求1。依据出处：原权利要求2。\n\n'
    '2. 对原权利要求3、4 作编号适应性调整，其附加技术特征未作实质改动。\n\n'
    '3. 上述修改均未超出原说明书和权利要求书记载的范围，符合专利法第33条的规定。'
)

_ARG = (
    '审查意见认为该设置位置属于本领域常规手段，发明人对此有不同理解。'
    '对比文件1 中的相应构件是为解决其自身的定位问题而设，其位置由该构件与相邻部件之间'
    '的配合关系决定，并不涉及本案所要处理的干涉问题。若将该构件按本案方式移至B位置，'
    '则该构件与相邻部件之间原有的配合关系即被破坏，其在对比文件1 中的作用随之丧失。'
    '因此本领域技术人员依对比文件1 的教导，不会想到将其移至本案所要求的位置。'
)
_ARG2 = (
    '就构件之间的配合关系而言，本案的C部件设置在B位置，与A部件保持确定的间距，'
    '而对比文件1 的对应构件直接与相邻部件贴合，二者依赖的配合条件并不相同。'
    '由于本案所求的是间距在整个运动过程中保持恒定，该目的无法通过对贴合式结构的'
    '简单调整而实现。审查意见就此未给出相应的依据与说理，恳请予以重新考虑。'
)
_COMBINE = (
    '即便将对比文件1 与对比文件2 及本领域公知常识结合，仍得不到本案的方案。'
    '对比文件2 中的相应结构服务于另一技术目的，与本案所要解决的干涉问题并无关联，'
    '两篇对比文件均未就如何将二者结合给出任何教导。'
)
_SYNERGY = (
    '上述区别技术特征在本案中构成相互配合的整体，A部件提供安装基准，C部件在该基准上'
    '保持确定的位置关系，D部件与之相邻设置以约束其运动范围。其中任一环节缺失，'
    '间距恒定的效果即无从达成，整体效果并非各构件单独作用的简单叠加。'
)
_DEP = (
    '在修改后的权利要求1 具有创造性的前提下，引用该权利要求的从属权利要求2 至 3 '
    '也同样具备创造性。'
)


def _extract_template_block():
    """提取模板文件中的第一个代码块（即模板正文）。"""
    out, inside = [], False
    for ln in TEMPLATE_MD.read_text(encoding='utf-8').split('\n'):
        if ln.startswith('```'):
            if inside:
                break
            inside = True
            continue
        if inside:
            out.append(ln)
    return out


def _drop_conditional(lines):
    """删除本次不启用的条件章节（N=1 时无"上次答复回顾"，本案无非创造性条款）。"""
    drop = ('一、关于上次答复的回顾', '四、其他条款处理说明')
    out, skipping = [], False
    for ln in lines:
        s = ln.strip()
        if skipping and re.match(r'^[一二三四五六七八九十]、', s):
            skipping = False
        if s.startswith(drop):
            skipping = True
            continue
        if not skipping:
            out.append(ln)
    return out


def _fill_placeholder(inner):
    """把模板中的 〔…〕 执行指令替换为实际内容。"""
    t = inner.strip()
    if '其他条款处理说明' in t and t.startswith('无'):
        return '无'
    if '分案申请' in t or '程序性要素' in t:
        return '无'
    if '纯争辩' in t:
        return '争辩+修改（最小必要并入：并入权利要求2至权1，其余保留为从权）'
    if '可修改克服' in t:
        return '无授权前景将被驳回'
    if '强' in t and '弱' in t:
        return ('🟡 中。理由：核心区别特征在两篇对比文件中均无教导，'
                '但其技术门槛不算很高，存在被认定为常规设计的风险。')
    if '列出特征及理由' in t:
        return '所述C部件(3)设置于所述B位置'
    if t == '列出':
        return '原权利要求3、4 的附加技术特征'
    if '保护范围考量' in t:
        return '保护范围不可逆，优先最小必要修改并保留渐进限缩空间'
    if '接受 /' in t or t == '反应':
        return '可能继续下发审查意见'
    if '策略名' in t:
        return '最小必要修改'
    if '并入清单' in t:
        return '原权利要求2 全部特征'
    if '限缩幅度' in t:
        return '小幅限缩'
    if '授权前景弱' in t:
        return '驳回风险高'
    if '范围损失' in t:
        return '范围损失不可逆'
    if t == '风险':
        return '需二次答复'
    if '逐字引用' in t:
        return '所述C部件(3)设置于所述B位置'
    if t == '同上':
        return '所述D部件(4)与所述C部件(3)相邻设置'
    if '客观表述' in t:
        return '如何在保持结构紧凑的同时避免相邻部件之间的运动干涉'
    if '特征名称' in t:
        return 'C部件的位置设置'
    if '完整深度论证' in t:
        return _ARG
    if '句式' in t:
        return _ARG2
    if '即便将最接近' in t:
        return _COMBINE
    if '600字' in t or '功能闭环' in t:
        return _SYNERGY
    if '首段' in t:
        return _DEP
    if '逐条列出非创造性' in t:
        return '（本次无非创造性条款）'
    if '逐项列出并入' in t:
        return _AMEND
    return '示例内容'


def _process_lines(lines):
    """处理模板中的整段/整行执行指令：删除或替换为实际内容。"""
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if s.startswith('〔'):
            # 跨行占位块：向前扫描至以 〕 结尾的行，整块替换为一个实际内容
            buf = [ln]
            i += 1
            while i < len(lines) and not lines[i].rstrip().endswith('〕'):
                buf.append(lines[i])
                i += 1
            if i < len(lines):
                buf.append(lines[i])
                i += 1
            out.append(_fill_placeholder('\n'.join(buf)))
            continue
        if s.startswith('（如有修改：'):
            while i < len(lines) and not lines[i].rstrip().endswith('）'):
                i += 1
            i += 1
            out.append(_AMEND + '\n')
            continue
        if '若审查员概括的技术问题' in s:
            i += 1
            continue
        if '同意审查员指定的最接近现有技术' in s:
            out.append('对比文件1 公开了一种示例装置，包括A部件与B位置，其整体构思与本案共有。')
            i += 1
            continue
        if '关于从属权利要求' in s and '（按用户要求' in s:
            out.append('三、关于从属权利要求2至3的创造性')
            i += 1
            continue
        out.append(ln)
        i += 1
    return out


def build_opinion_from_template():
    """由模板派生一份《意见陈述书》初稿（结构与模板当前版本严格一致）。"""
    lines = _process_lines(_drop_conditional(_extract_template_block()))
    text = '\n'.join(lines)
    for a, b in (
        ('申请号：XXXXXXXXXXX', '申请号：%s' % E2E_APPNO),
        ('发明创造名称：XXXXXXXXXX', '发明创造名称：%s' % E2E_TITLE),
        ('针对：第 N 次审查意见通知书（通知书编号：XXXX）',
         '针对：第一次审查意见通知书（发文序号：2026010100000000）'),
        ('五、结论', '四、结论'),
        ('对比文件×', '对比文件1'),
    ):
        text = text.replace(a, b)
    text = re.sub(r'〔([^〕\n]{1,200})〕', lambda m: _fill_placeholder(m.group(1)), text)
    return text


def build_e2e_fixture(tmp, d):
    """生成端到端样例产物集（3 docx + 1 md + reference）。"""
    e2e = tmp / 'e2e'
    ref = tmp / 'e2e_ref'
    e2e.mkdir(exist_ok=True)
    ref.mkdir(exist_ok=True)

    ref_claims = ref / '原权利要求书.txt'
    ref_claims.write_text(REF_CLAIMS, encoding='utf-8')
    d['e2e_ref'] = ref_claims

    stem = '意见陈述书初稿_%s_%s' % (E2E_APPNO, E2E_DATE)
    op_md = e2e / (stem + '.md')
    op_md.write_text(build_opinion_from_template(), encoding='utf-8')
    make_docx(e2e / (stem + '.docx'), op_md.read_text(encoding='utf-8'))
    d['e2e_opinion'] = op_md
    d['e2e_opinion_docx'] = e2e / (stem + '.docx')

    stem = '权利要求书替换页_%s_%s' % (E2E_APPNO, E2E_DATE)
    rp_md = e2e / (stem + '.md')
    rp_md.write_text(E2E_REPLACE, encoding='utf-8')
    make_docx(e2e / (stem + '.docx'), E2E_REPLACE)
    d['e2e_replace'] = rp_md

    stem = '权利要求修改对照页_%s_%s' % (E2E_APPNO, E2E_DATE)
    cp_md = e2e / (stem + '.md')
    cp_md.write_text(E2E_COMPARE, encoding='utf-8')
    make_docx(e2e / (stem + '.docx'), E2E_COMPARE)
    d['e2e_compare'] = cp_md

    (e2e / ('附件_答复辅助材料汇总_%s_%s.md' % (E2E_APPNO, E2E_DATE))).write_text(
        E2E_ATTACH, encoding='utf-8')

    d['e2e_dir'] = e2e
    return d


def main():
    with tempfile.TemporaryDirectory() as tmp_s:
        tmp = Path(tmp_s)
        d = setup(tmp)
        d = build_e2e_fixture(tmp, d)

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
            # 附图为可选项：未提供也不得阻塞（本 skill 不解析图像内容，2026-09-03 修订）
            ('materials_pass_drawings_optional', ('check_materials.py', '--round', '1',
             '--present', 'oa,claims,spec,contrast'), 0, '不影响流程'),
            # 回归护栏：仅 --files 时只统计规模，不得因 present 为空而误报"材料缺口"
            ('materials_scale_only_no_false_fail', ('check_materials.py', '--files', str(d['scale_small'])), 0, '材料规模统计'),
            ('materials_scale_small_default', ('check_materials.py', '--round', '1',
             '--present', 'oa,claims,spec,drawings,contrast', '--files', str(d['scale_small'])), 0, '→ 默认模式'),
            ('materials_scale_mid_directed', ('check_materials.py', '--round', '1',
             '--present', 'oa,claims,spec,drawings,contrast', '--files', str(d['scale_mid'])), 0, '定向读取'),
            ('materials_scale_large_split', ('check_materials.py', '--round', '1',
             '--present', 'oa,claims,spec,drawings,contrast', '--files', str(d['scale_large'])), 0, '分步模式'),
            # ---- check_clean_markers.py ----
            ('markers_pass_clean', ('check_clean_markers.py', '--input', str(d['good'])), 0, 'PASS'),
            ('markers_fail_bad', ('check_clean_markers.py', '--input', str(d['bad'])), 1, 'FAIL'),
            ('markers_pass_attachment_exempt', ('check_clean_markers.py', '--input', str(d['attach'])), 0, 'PASS'),
            ('markers_attachment_frame_exempt', ('check_clean_markers.py', '--input', str(d['attach_frame'])), 0, 'PASS'),
            ('markers_pass_underline_ok', ('check_clean_markers.py', '--input', str(d['underline_ok'])), 0, 'PASS'),
            # ---- check_deliverables.py ----
            ('deliverables_pass_okdir', ('check_deliverables.py', '--dir', str(d['okdir'])), 0, 'PASS'),
            ('deliverables_fail_baddir', ('check_deliverables.py', '--dir', str(d['baddir'])), 1, 'FAIL'),
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
            ('ai_traces_exempt_mandatory_closing', ('check_ai_traces.py', '--input', str(d['ai_exempt_mandatory'])), 0, 'PASS'),
            ('ai_traces_exempt_delete_block', ('check_ai_traces.py', '--input', str(d['ai_exempt_block'])), 0, 'PASS'),
            ('ai_traces_exempt_claim_numbering', ('check_ai_traces.py', '--input', str(d['ai_exempt_numdot'])), 0, 'PASS'),
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
            # 期望文本用精确锚点：结果行"未检出疑似改写引用"也含"疑似改写引用"字样，
            # 用宽松文本会让本应失败的用例假通过（2026-09-03 实测踩到）。
            ('citations_pass', ('check_citations.py', '--claims', str(d['cite_claims']),
             '--input', str(d['cite_pass'])), 0, '未检出疑似改写引用'),
            ('citations_warn_rewrite', ('check_citations.py', '--claims', str(d['cite_claims']),
             '--input', str(d['cite_warn'])), 0, '[WARN]'),
            ('citations_strict_fail', ('check_citations.py', '--claims', str(d['cite_claims']),
             '--input', str(d['cite_warn']), '--strict'), 1, '结果：FAIL'),
            # ---- check_claim_links.py ----
            ('claim_links_pass', ('check_claim_links.py', '--input', str(d['links_pass'])), 0, 'PASS'),
            ('claim_links_fail_missing', ('check_claim_links.py', '--input', str(d['links_fail'])), 1, '引用悬空'),
            ('claim_links_fail_backref', ('check_claim_links.py', '--input', str(d['links_fail_backref'])), 1, '引用错误'),
            # ---- check_argument_lengths.py ----
            ('arglen_pass', ('check_argument_lengths.py', '--input', str(d['arglen_pass'])), 0, 'PASS'),
            ('arglen_warn_short', ('check_argument_lengths.py', '--input', str(d['arglen_warn_short'])), 0, '论证不足'),
            ('arglen_warn_long', ('check_argument_lengths.py', '--input', str(d['arglen_warn_long'])), 0, '超出建议区间'),
            ('arglen_strict_fail', ('check_argument_lengths.py', '--input', str(d['arglen_warn_short']), '--strict'), 1, 'FAIL'),
            # ---- 端到端集成测试：产物由模板派生，捕获"模板↔脚本"交叉点缺陷 ----
            ('e2e_markers_opinion', ('check_clean_markers.py', '--input', str(d['e2e_opinion'])), 0, 'PASS'),
            ('e2e_markers_docx', ('check_clean_markers.py', '--input', str(d['e2e_opinion_docx']), '--include-docx'), 0, 'PASS'),
            ('e2e_ai_traces_opinion', ('check_ai_traces.py', '--input', str(d['e2e_opinion'])), 0, 'PASS'),
            ('e2e_ai_traces_docx', ('check_ai_traces.py', '--input', str(d['e2e_opinion_docx']), '--include-docx'), 0, 'PASS'),
            ('e2e_law_citations', ('check_law_citations.py', '--input', str(d['e2e_opinion'])), 0, 'PASS'),
            ('e2e_citations', ('check_citations.py', '--claims', str(d['e2e_ref']), '--input', str(d['e2e_opinion'])), 0, 'PASS'),
            ('e2e_terms', ('check_terms.py', '--reference', str(d['e2e_ref']), '--input', str(d['e2e_opinion'])), 0, 'PASS'),
            ('e2e_claim_links', ('check_claim_links.py', '--input', str(d['e2e_replace'])), 0, 'PASS'),
            ('e2e_selfcontained', ('check_claims_selfcontained.py', '--input', str(d['e2e_replace'])), 0, 'PASS'),
            ('e2e_arglen', ('check_argument_lengths.py', '--input', str(d['e2e_opinion'])), 0, 'PASS'),
            ('e2e_deliverables', ('check_deliverables.py', '--dir', str(d['e2e_dir'])), 0, 'PASS'),
            # ---- check_amendment_risk.py（🔴 级超范围拦截）----
            ('amend_risk_pass', ('check_amendment_risk.py', '--input', str(d['amend_pass'])), 0, 'PASS'),
            ('amend_risk_fail', ('check_amendment_risk.py', '--input', str(d['amend_fail'])), 1, 'FAIL'),
            ('amend_risk_defskip', ('check_amendment_risk.py', '--input', str(d['amend_def'])), 0, 'PASS'),
            ('amend_risk_docx_fail', ('check_amendment_risk.py', '--input', str(d['amend_docx']), '--include-docx'), 1, 'FAIL'),
            ('e2e_amend_risk', ('check_amendment_risk.py', '--dir', str(d['e2e_dir']), '--include-docx'), 0, 'PASS'),
            # ---- check_amended_claims.py（三处一致性 + 多项独权重叠）----
            ('amended_pass', ('check_amended_claims.py', '--input', str(d['amd_rep']),
                              '--input', str(d['amd_cmp_ok']), '--input', str(d['amd_opi'])), 0, 'PASS'),
            ('amended_fail_mismatch', ('check_amended_claims.py', '--input', str(d['amd_rep']),
                                       '--input', str(d['amd_cmp_bad'])), 1, 'FAIL'),
            ('amended_fail_apno', ('check_amended_claims.py', '--input', str(d['amd_rep_badapno']),
                                   '--input', str(d['amd_cmp_ok'])), 1, 'FAIL'),
            ('amended_sect_type', ('check_amended_claims.py', '--input', str(d['amd_rep']),
                                   '--input', str(d['amd_cmp_sect'])), 0, 'PASS'),
            ('amended_warn_overlap', ('check_amended_claims.py', '--input', str(d['amd_rep_overlap']),
                                      '--input', str(d['amd_cmp_ok'])), 0, '重复保护'),
            ('e2e_amended', ('check_amended_claims.py', '--input', str(d['e2e_replace']),
                             '--input', str(d['e2e_compare']), '--input', str(d['e2e_opinion'])), 0, 'PASS'),
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
