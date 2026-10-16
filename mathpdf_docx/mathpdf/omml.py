from copy import deepcopy
from io import BytesIO
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from docx import Document
from docx.oxml.ns import qn


def normalize_latex(latex):
    """Эквивалентные команды оформления TeX; математические аргументы сохраняются."""
    changes = []
    def continued(match):
        changes.append(r'\cfrac → \frac (оформление непрерывной дроби)')
        return r'\frac'
    normalized = re.sub(r'\\cfrac(?![A-Za-z])(?:\s*\[[lr]\])?', continued, latex)
    def sized(match):
        changes.append(match.group(0) + r' → \frac (размер дроби)')
        return r'\frac'
    normalized = re.sub(r'\\[dt]frac(?![A-Za-z])', sized, normalized)
    def calligraphic(match):
        changes.append(r'{\cal X} → \mathcal{X} (оформление буквы)')
        return r'\mathcal{' + match.group(1) + '}'
    normalized = re.sub(r'\{\s*\\cal\s+([A-Za-z])\s*\}', calligraphic, normalized)
    def indexed_root(match):
        changes.append(r'\root n \of → \sqrt[n] (запись корня)')
        return r'\sqrt[' + match.group(1) + ']'
    normalized = re.sub(r'\\root\s+([A-Za-z0-9]+)\s*\\of(?=\s*\{)', indexed_root, normalized)
    def integral_limits(match):
        changes.append(r'Нижний предел интеграла: \underset → \int\limits')
        return r'\int\limits_{' + match.group(1).strip() + '}'
    # Пробельные команды сразу после предела Pandoc иногда принимает за
    # всё тело оператора. Снимаем только оформление перед интеграндом.
    normalized = re.sub(
        r'\\underset\s*\{((?:[^{}]|\{[^{}]*\})*)\}\s*\{\s*\\int\s*\}(?:\s*\\[,;!])*\s*',
        integral_limits, normalized)
    # Пустая последняя строка OCR создаёт неполную матрицу/пустой шаблон Word.
    normalized, count = re.subn(
        r'(?:\\\\\s*)+(?=\\end\{(?:cases|array|aligned|gathered|matrix|pmatrix|bmatrix)\})',
        '', normalized)
    if count:
        changes.append('Убрана пустая последняя строка математического окружения')
    def single_aligned(match):
        body = match.group(1)
        if r'\\' in body or '&' in body:
            return match.group(0)
        # Снять только пустой маркер выравнивания перед одной формулой.
        body = re.sub(r'^\s*(?:\{\s*\}\s*)+(?=\\int)', '', body)
        body = re.sub(r'^\s*(\{\s*)(?:\{\s*\}\s*)+(?=\\int)', r'\1', body)
        changes.append('Снята однострочная оболочка aligned с пустым столбцом')
        return body
    normalized = re.sub(
        r'\\begin\{aligned\}\s*(?:\{\s*\}\s*)?&\s*(.*?)\\end\{aligned\}',
        single_aligned, normalized, flags=re.DOTALL)
    return normalized.strip(), list(dict.fromkeys(changes))


def latex_to_omml(latex, pandoc=None):
    executable = pandoc or shutil.which('pandoc')
    if not executable:
        raise RuntimeError('Pandoc не найден; установите Pandoc и добавьте его в PATH.')
    if not latex.strip() or len(latex) > 12000 or '$' in latex:
        raise ValueError('Пустая, слишком длинная или неоднозначная запись LaTeX.')
    latex, _ = normalize_latex(latex)
    # stdin, без shell и чтения файлов по командам TeX; только Markdown math reader.
    with tempfile.TemporaryDirectory(prefix='mathpdf-pandoc-') as tmp:
        target = Path(tmp)/'formula.docx'
        res = subprocess.run([executable, '--from=markdown+tex_math_dollars', '--to=docx',
                              '--output', str(target)], input=f'${latex}$', text=True,
                             capture_output=True, timeout=30, cwd=tmp)
        if res.returncode or res.stderr.strip() or not target.is_file():
            raise RuntimeError('Pandoc отклонил формулу: ' + res.stderr[:500])
        doc = Document(BytesIO(target.read_bytes()))
        nodes = list(doc.element.iter(qn('m:oMath')))
        if len(nodes) != 1 or not ''.join(nodes[0].itertext()).strip():
            raise RuntimeError('Pandoc не создал проверяемый элемент OMML.')
        # Нельзя принять частичный результат с текстом, вынесенным за формулу.
        if any(t.text and t.text.replace('\u200b', '').strip() for p in doc.paragraphs for t in p._p.iter(qn('w:t'))):
            raise RuntimeError('Pandoc оставил текст вне OMML.')
        for matrix in nodes[0].iter(qn('m:m')):
            widths = [len(row.findall(qn('m:e'))) for row in matrix.findall(qn('m:mr'))]
            if not widths or min(widths) == 0 or len(set(widths)) != 1:
                raise RuntimeError('В OMML получена неполная матрица; исходная формула сохранена изображением.')
        for script in nodes[0].iter(qn('m:sSub'), qn('m:sSup'), qn('m:sSubSup')):
            base = script.find(qn('m:e'))
            if base is None or not ''.join(base.itertext()).replace('\u200b', '').strip():
                raise RuntimeError('В OMML получен индекс без основания; исходная формула сохранена изображением.')
        for operator in nodes[0].iter(qn('m:nary')):
            body = operator.find(qn('m:e'))
            if body is None or not ''.join(body.itertext()).replace('\u200b', '').strip():
                raise RuntimeError('В OMML получен пустой шаблон под оператором; исходная формула сохранена изображением.')
        return deepcopy(nodes[0])
