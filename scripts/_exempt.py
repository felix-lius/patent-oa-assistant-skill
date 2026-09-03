# -*- coding: utf-8 -*-
"""
豁免规则公共模块（供 check_ai_traces / check_clean_markers 等痕迹类脚本共享）

**为什么要有这个模块**：此前各痕迹类脚本各自维护一套豁免规则。给其中一个加了
区块豁免而另一个没有时，同一份产物会出现"ai_traces PASS 而 clean_markers FAIL"
的不一致（2026-09-03 实跑踩到）。集中定义后，规则只有一处，不会再发散。

**各脚本按自身职责决定采用哪些规则，不是全盘套用**：

- `apply_block_exempt()`（"提交时删除"区块豁免 + 模板强制措辞整行豁免）
  **仅 check_ai_traces 采用**：答复策略说明、策略选择页属正文外内容，其中的
  口语化与说明性表述是正常的，不应按递交正文的文风标准评判。

- check_clean_markers **有意不采用区块豁免**：占位符、执行指令、框架术语无论
  出现在哪个区块，都不应出现在交付物中。若模板某处写法会被判残留，正确解法是
  **改模板**，而不是放宽检查（见 opinion-letter-template.md 头部「注记写法约定」）。
  clean_markers 只采用 `exempt_cats_for()` 这一项（附件的待核实类标记豁免）。
"""
import re
import zipfile

# 正文外附件（内部辅助材料，提交时删除）的文件名前缀
ATTACHMENT_PREFIX = '附件_'

# 模板强制措辞：opinion-letter-template 要求"逐字采用、不得省略或改写"，
# 此类措辞本身即为合规文本，不得因扫描器规则而要求改写，整行豁免。
EXEMPT_LINE_PATTERNS = [
    re.compile(r'发明人相信.*恳请接受本意见陈述'),   # 结论收尾段（Step 9 必备要素，逐字强制）
    re.compile(r'^尊敬的审查员'),                     # 敬语开头段（逐字强制）
    re.compile(r'^您好！十分感谢您的认真审查'),       # 敬语开头段（逐字强制）
]

# "提交时删除"区块：答复策略说明、策略选择页等正文外内容，不进入递交文本。
DELETE_MARKER = '提交时删除'
BLOCK_END = re.compile(r'^(---|\*\*\*|#\s)')

# 豁免标记：表示该前缀下的文件豁免**全部**检查类别。
ALL_CATEGORIES = '__ALL__'

# 文件名前缀 → 该文件豁免的检查类别集合。
# 附件为正文外内部记录（提交时删除），模板本身就要求它出现"Step N 产出"
# "（逐字引用）"等字样，故豁免全部类别——与 check_ai_traces 对附件的处理保持一致。
EXEMPT_CATS_BY_PREFIX = {
    ATTACHMENT_PREFIX: {ALL_CATEGORIES},
    # 过程记录文件（过程_*）同为内部工作记录，非交付物，一并豁免。
    '过程_': {ALL_CATEGORIES},
}


def exempt_cats_for(name):
    """按文件名返回豁免的检查类别集合（无匹配返回空集）。"""
    for prefix, cats in EXEMPT_CATS_BY_PREFIX.items():
        if name.startswith(prefix):
            return cats
    return set()


def is_cat_exempt(cat, exempt_cats):
    """判断某检查类别在该文件上是否被豁免（支持 ALL_CATEGORIES 全豁免标记）。"""
    return ALL_CATEGORIES in exempt_cats or cat in exempt_cats


def is_attachment(name):
    """是否为正文外附件（附件专门收纳待核实信息，其中的标记字样属合法内容）。"""
    return name.startswith(ATTACHMENT_PREFIX)


def iter_lines(path):
    """产出 (行号, 文本)。.docx 按段落切分，其余按行切分。"""
    if str(path).lower().endswith('.docx'):
        with zipfile.ZipFile(path) as zf:
            xml = zf.read('word/document.xml').decode('utf-8')
        for idx, para in enumerate(xml.split('</w:p>'), 1):
            text = re.sub(r'<[^>]+>', '', para).strip()
            if text:
                yield idx, text
    else:
        with open(path, encoding='utf-8', errors='replace') as fh:
            for idx, line in enumerate(fh, 1):
                yield idx, line.rstrip('\n')


def apply_block_exempt(units):
    """过滤豁免单元后产出 (序号, 文本)。豁免两类：
    ① "提交时删除"标记起的整个区块（直至下一个 --- 或一级标题）；
    ② 模板强制措辞整行。

    仅文风类检查应调用本函数；标记残留类检查不得调用，理由见模块文档字符串。
    """
    in_block = False
    for idx, text in units:
        if DELETE_MARKER in text:
            in_block = True
            continue
        if in_block:
            if BLOCK_END.match(text.strip()):
                in_block = False
            else:
                continue
        if any(p.search(text) for p in EXEMPT_LINE_PATTERNS):
            continue
        yield idx, text
