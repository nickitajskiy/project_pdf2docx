"""Ограниченные геометрические правила для одной колонки, не парсер математики."""
from statistics import median
import re
from .schema import Block, Paragraph, ConversionError


def union(boxes):
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def cb(c):
    return (c['x0'], c['top'], c['x1'], c['bottom'])


def overlap(a, b):
    return max(0, min(a[2],b[2])-max(a[0],b[0])) * max(0,min(a[3],b[3])-max(a[1],b[1]))


def center_in(c, b):
    return b[0] <= (c['x0']+c['x1'])/2 <= b[2] and b[1] <= (c['top']+c['bottom'])/2 <= b[3]


def prepare_regions(chars, detected, width, height, report, page):
    boxes = list(detected)
    # Пропуски Unicode и математические знаки — страховка к детектору, а не его замена.
    for c in chars:
        text = c['text']
        if ('(cid:' in text or any(s in text for s in '∫∑∪∩√⩽⩾∈⊂⊃∞')) and not any(center_in(c,b) or overlap(cb(c),b) > 0 for b in boxes):
            boxes.append(cb(c))
            report.warn(page, f'Дополнительная область по символу {text!r}; проверьте границы вырезки.')
    out = []
    for b in boxes:
        if len(b)!=4 or b[2]<=b[0] or b[3]<=b[1]:
            raise ConversionError(f'Стр. {page}: детектор вернул неверные координаты.')
        # Font bbox в Computer Modern может пересекать несколько соседних строк.
        # Геометрия детектора определяет видимые пределы, bbox шрифта не расширяет её.
        pad_y=1
        b=(max(0,b[0]-1), max(0,b[1]-pad_y), min(width,b[2]+1), min(height,b[3]+pad_y))
        punctuation=[cb(c) for c in chars if c['text'] in '.,;:-' and overlap(cb(c),b)>.25*max(1,(c['x1']-c['x0'])*(c['bottom']-c['top']))]
        out.append(union([b]+punctuation))
    changed = True
    while changed:
        changed = False
        for i in range(len(out)):
            for j in range(i+1,len(out)):
                if overlap(out[i],out[j]) > .20*min((out[i][2]-out[i][0])*(out[i][3]-out[i][1]), (out[j][2]-out[j][0])*(out[j][3]-out[j][1])):
                    out[i] = union([out[i],out.pop(j)])
                    changed=True
                    break
            if changed:
                break
    # Соседние строки могут иметь едва перекрывающиеся рамки детектора.
    # Разделяем только этот узкий зазор, не объединяя соседние формулы в колонку.
    out.sort(key=lambda b:(b[1],b[0]))
    for i,a in enumerate(out):
        for j in range(i+1,len(out)):
            b=out[j]
            if b[1]>=a[3]: break
            if overlap(a,b)>0 and (b[1]+b[3]-a[1]-a[3]) > .7*min(a[3]-a[1],b[3]-b[1]):
                edge=(a[3]+b[1])/2
                out[i]=(a[0],a[1],a[2],edge)
                out[j]=(b[0],edge,b[2],b[3])
                a=out[i]
    return out


def build_paragraphs(page, math_blocks, report):
    chars = page.chars
    body = median([c['size'] for c in chars if len(c['text'])==1] or [12])
    text_chars = [c for c in chars if not any(center_in(c,m.bbox) or (any(k in c['fontname'].upper() for k in ['CMEX','CMMI','CMSY','CMR','MSBM','MSAM']) and overlap(cb(c),m.bbox)>0) for m in math_blocks)]
    # Группировать сначала текст, не растягивая строки по высоким формулам.
    lines=[]
    ordinary=[c for c in text_chars if c['size']>=.86*body]
    small=[c for c in text_chars if c['size']<.86*body]
    for c in sorted(ordinary,key=lambda c:(c['top'],c['x0'])):
        candidates=[line for line in lines[-8:] if abs(c['top']-line['base']['top'])<2.5]
        if not candidates:
            lines.append({'base':c,'chars':[c], 'math':[]})
        else:
            line=min(candidates,key=lambda line:abs(c['top']-line['base']['top']))
            line['chars'].append(c)
    for c in small:
        candidates=[line for line in lines if abs((c['top']+c['bottom']-line['base']['top']-line['base']['bottom'])/2)<body]
        if candidates:
            # Верхняя отметка у номера близка по x именно к своему номеру.
            line=min(candidates,key=lambda line:min(abs(c['x0']-x['x1']) for x in line['chars'])+2*abs(c['bottom']-line['base']['bottom']))
            line['chars'].append(c)
        else:
            lines.append({'base':c,'chars':[c], 'math':[]})
    for m in math_blocks:
        candidates=[]
        for line in lines:
            if line['base'] is None:
                continue
            b=cb(line['base'])
            ov=max(0,min(m.bbox[3],b[3])-max(m.bbox[1],b[1]))
            if ov >= .5*min(b[3]-b[1],m.bbox[3]-m.bbox[1]):
                candidates.append((ov,line))
        if candidates and m.inline:
            min(candidates,key=lambda a:abs((a[1]['base']['top']+a[1]['base']['bottom'])/2-(m.anchor_y if m.anchor_y is not None else (m.bbox[1]+m.bbox[3])/2)))[1]['math'].append(m)
        else:
            lines.append({'base':None,'chars':[], 'math':[m]})
    result=[]
    for line in lines:
        cs=line['chars']; ms=line['math']
        bbox=union([cb(c) for c in cs]+[m.bbox for m in ms])
        base=line['base']
        footer = bool(cs and not ms and ''.join(c['text'] for c in sorted(cs,key=lambda c:c['x0'])).strip().isdigit()
                      and bbox[1] > page.height*.92)
        atoms=[]
        for c in cs:
            super_ = bool(base and c['size'] < .86*base['size'] and c['bottom'] < base['bottom']-1)
            atoms.append(Block(page.page_number,cb(c),'text',text=c['text'],method='text_layer',
                               superscript=super_,size=c['size'],bold=any(k in c['fontname'].lower() for k in ['bold','sfbx','cmbx'])))
        atoms += ms
        atoms.sort(key=lambda a:a.bbox[0])
        parts=[]
        prev=None
        for a in atoms:
            if prev:
                gap=a.bbox[0]-prev.bbox[2]
                if gap>max(1.2,body*.15) and not prev.text.endswith(' ') and not a.text.startswith(' '):
                    parts.append(Block(page.page_number,(prev.bbox[2],bbox[1],a.bbox[0],bbox[3]),'text',text=' ',method='geometry'))
            if parts and a.kind=='text' and parts[-1].kind=='text' and a.superscript==parts[-1].superscript and a.bold==parts[-1].bold and abs(a.size-parts[-1].size)<.5:
                parts[-1].text+=a.text; parts[-1].bbox=union([parts[-1].bbox,a.bbox])
            else: parts.append(a)
            prev=a
        text=''.join(p.text for p in parts)
        heading=bool(cs and sum(c['size'] for c in cs)/len(cs)>body*1.13 or text.startswith('Семинар №') or (cs and all(a.bold for a in atoms if a.kind=='text')))
        result.append(Paragraph(page.page_number,bbox,parts,heading,footer))
    result.sort(key=lambda p:(p.bbox[1],p.bbox[0]))
    # Ищем устойчивый пробел между колонками в исходном русском тексте.
    # Удалённые формулы не должны создавать ложные «колонки».
    prose_rows=[]
    for c in sorted((c for c in chars if re.search('[а-яА-Я]',c['text'])),key=lambda c:c['top']):
        row=next((r for r in prose_rows[-6:] if abs(r[0]['top']-c['top'])<2.5),None)
        if row is None: prose_rows.append([c])
        else: row.append(c)
    dense=[sorted(row,key=lambda c:c['x0']) for row in prose_rows if len(row)>=16]
    for x in range(int(page.width*.3),int(page.width*.7),10):
        count=0
        for row in dense:
            left=[c for c in row if c['x1']<x]; right=[c for c in row if c['x0']>x]
            if len(left)>=8 and len(right)>=8 and min(c['x0'] for c in right)-max(c['x1'] for c in left)>24:
                count+=1
        if count>=8 and count>=len(dense)*.6:
            raise ConversionError(f'Стр. {page.page_number}: признаки колонок или таблицы. Выберите «Сохранить внешний вид».')
    # Перенос PDF не равен новому абзацу. Не удалять дефисы автоматически.
    merged=[]
    for p in result:
        text=''.join(a.text for a in p.parts).strip()
        start=bool(re.match(r'^(?:\d+[0∗*]?\s*\.|[а-яa-z]\))',text))
        prev=merged[-1] if merged else None
        can_join=(prev and not start and not p.heading and not prev.heading and not p.page_number and not prev.page_number
                  and any(a.kind=='text' for a in p.parts) and any(a.kind=='text' for a in prev.parts)
                  and not any(a.kind!='text' for a in p.parts+prev.parts)
                  and -.3*body<p.bbox[1]-prev.bbox[3]<body*.8 and abs(p.bbox[0]-prev.bbox[0])<body*1.8)
        if can_join:
            prev.parts.append(Block(p.page,p.bbox,'text',text=' ',method='line_join'))
            prev.parts.extend(p.parts); prev.bbox=union([prev.bbox,p.bbox])
        else: merged.append(p)
    return merged


def refine_detections(chars, detections, report, page, image=None, page_size=None):
    """Соседние буквенные пункты задают границу строк; шрифтовой bbox не решает её."""
    body=median([c['size'] for c in chars] or [12])
    rows=[]
    for c in sorted((c for c in chars if .86*body<=c['size']<=1.15*body and '(cid:' not in c['text']),key=lambda c:c['top']):
        row=next((r for r in rows[-6:] if abs(r[0]['top']-c['top'])<1.8),None)
        if row is None: rows.append([c])
        else: row.append(c)
    anchors=[]
    for row in rows:
        row.sort(key=lambda c:c['x0'])
        text=''.join(c['text'] for c in row)
        if re.match(r'^(?:[а-яa-z]\)|\d+\.)',text):
            anchors.append((row[0]['top']+body/2,row,text))
    anchors.sort(key=lambda a:a[0])
    def math_row(anchor):
        text=anchor[2]
        return bool(re.match(r'^[а-яa-z]\)',text) and not re.search('[а-яА-Я]',text[2:]))

    def seam(a,b):
        if image is None: return (a+b)/2
        scale=image.height/page_size[1]
        left=int((min(c['x0'] for c in chars)+34)*image.width/page_size[0])
        right=int((page_size[0]-35)*image.width/page_size[0])
        top,bottom=int((a+2)*scale),int((b-2)*scale)
        if bottom<=top: return (a+b)/2
        strip=image.crop((left,top,right,bottom)).convert('L')
        runs=[]; start=None
        for y in range(strip.height):
            white=strip.crop((0,y,strip.width,y+1)).getextrema()[0]>225
            if white and start is None: start=y
            if not white and start is not None: runs.append((start,y)); start=None
        if start is not None: runs.append((start,strip.height))
        if not runs: return (a+b)/2
        lo,hi=runs[-1]
        return (top+(lo+hi)/2)/scale

    out=[]
    for d in detections:
        b=d['bbox'] if isinstance(d,dict) else d
        inline=d.get('inline',True) if isinstance(d,dict) else True
        owned=''.join(c['text'] for c in sorted(chars,key=lambda c:c['x0']) if center_in(c,b)).strip()
        left=min((c['x0'] for c in chars),default=0)
        if b[2]-b[0]<35 and (re.fullmatch(r'\d+[0∗*]?\.?',owned) or (b[0]<left+45 and re.fullmatch(r'[а-я]\)',owned))):
            continue  # номер / верхняя отметка — текст, а не формула
        if inline and image is not None:
            contained=[k for k,x in enumerate(anchors) if math_row(x) and b[1]<x[0]<b[3]]
            if contained:
                for k in contained:
                    mid=anchors[k][0]; top=b[1]; bottom=b[3]
                    if k and math_row(anchors[k-1]) and mid-anchors[k-1][0]<body*5:
                        top=seam(anchors[k-1][0],mid)
                    if k+1<len(anchors) and math_row(anchors[k+1]) and anchors[k+1][0]-mid<body*5:
                        bottom=seam(mid,anchors[k+1][0])
                    out.append({'bbox':(b[0],top+.3,b[2],bottom-.3),'inline':True,'anchor_y':mid})
                if len(contained)>1:
                    report.warn(page,'Область модели разделена по строкам математического списка; проверьте вырезки.')
                continue
        if inline and anchors:
            inside=[k for k,x in enumerate(anchors) if b[1]<x[0]<b[3]]
            if len(inside)>1 and all(anchors[v][0]-anchors[u][0]<body*2 for u,v in zip(inside,inside[1:])):
                # Модель иногда объединяет соседние формулы списка, например ODD и A=CL.
                # Разделить по номерам строк, чтобы не переставить подпункты.
                for k in inside:
                    mid=anchors[k][0]
                    top=max(b[1],(mid+anchors[k-1][0])/2+.3) if k else b[1]
                    bottom=min(max(b[3],mid+body/2),(mid+anchors[k+1][0])/2-.3) if k+1<len(anchors) else max(b[3],mid+body/2)
                    out.append({'bbox':(b[0],top,b[2],bottom),'inline':True})
                report.warn(page,'Область модели разделена по соседним пунктам списка; проверьте границы формул.')
                continue
            k=min(range(len(anchors)),key=lambda k:abs(anchors[k][0]-(b[1]+body*.6)))
            mid=anchors[k][0]
            if abs(mid-(b[1]+body*.6))<body*.8:
                top,bottom=b[1],b[3]
                if k and mid-anchors[k-1][0]<body*2:
                    top=max(top,(mid+anchors[k-1][0])/2+.3)
                if k+1<len(anchors) and anchors[k+1][0]-mid<body*2:
                    bottom=min(bottom,(mid+anchors[k+1][0])/2-.3)
                if bottom>top: b=(b[0],top,b[2],bottom)
        out.append({'bbox':b,'inline':inline})
    for mid,row,text in anchors:
        # Узкая страховка пропущенных коротких равенств в буквенном списке (A=CL).
        tail=re.sub(r'^[а-яa-z]\)','',text).strip()
        if '=' in tail and re.fullmatch(r'[A-Za-z0-9=+\-*/(),.;: ]+',tail):
            content=[c for c in row[2:] if c['text'].strip()]
            if content:
                bbox=union([cb(c) for c in content])
                area=max(1,(bbox[2]-bbox[0])*(bbox[3]-bbox[1]))
                if sum(overlap(bbox,d['bbox']) for d in out)<area*.5:
                    out.append({'bbox':bbox,'inline':True})
                    report.warn(page,'Короткое равенство в пункте списка дополнительно сохранено по геометрии; проверьте вырезку.')
    return out
