"""Узкий резерв для однострочных записей из надёжного Unicode-слоя PDF.

Не поддерживает дроби, корни, многострочные конструкции или неизвестные
глифы. Один уровень геометрических индексов; при сомнении — отказ.
"""
import re
from statistics import median


def simple_text_math(chars):
    chars = sorted(chars, key=lambda c:c['x0'])
    if not chars or len(chars)>120:
        return ''
    allowed = re.compile(r'^[A-Za-z0-9.,;:+=()\[\] −∞∈-]$')
    if any(not allowed.fullmatch(c['text']) for c in chars):
        return ''
    size = max(c['size'] for c in chars)
    base = [c for c in chars if c['size']>=.85*size]
    top = median(c['top'] for c in base)
    bottom = median(c['bottom'] for c in base)
    if any(abs(c['top']-top)>.18*size for c in base):
        return ''
    mapping={'∞':r'\infty ', '∈':r'\in ', '−':'-'}
    out=[]; previous=None; script=''
    for c in chars:
        value=mapping.get(c['text'],c['text'])
        if c['size']<.85*size:
            if (not previous or not out or not re.fullmatch('[A-Za-z0-9]',c['text'])
                or c['x0']-previous['x1']>.5*size or c['size']<.5*size):
                return ''
            kind='_' if c['top']>top+.2*size else '^' if c['bottom']<bottom-.2*size else ''
            if not kind or (script and script!=kind):
                return ''
            if script:
                out[-1]=out[-1][:-1]+value+'}'
            else:
                out.append(kind+'{'+value+'}')
            script=kind
        else:
            if previous and c['x0']-previous['x1']>max(1.2,size*.15):
                out.append(r'\,')
            out.append(value);script=''
        previous=c
    return ''.join(out).strip()
