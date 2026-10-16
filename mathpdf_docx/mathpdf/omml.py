from copy import deepcopy
from io import BytesIO
from pathlib import Path
import shutil
import subprocess
import tempfile
from docx import Document
from docx.oxml.ns import qn


def latex_to_omml(latex, pandoc=None):
    executable = pandoc or shutil.which('pandoc')
    if not executable:
        raise RuntimeError('Pandoc не найден; установите Pandoc и добавьте его в PATH.')
    if not latex.strip() or len(latex) > 12000 or '$' in latex:
        raise ValueError('Пустая, слишком длинная или неоднозначная запись LaTeX.')
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
        return deepcopy(nodes[0])
