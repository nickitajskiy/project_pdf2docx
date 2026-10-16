from dataclasses import dataclass
from pathlib import Path
import tempfile
import pdfplumber
import pypdfium2 as pdfium
from .schema import Mode, Report, Block, ConversionError
from .pdfio import inspect_pdf, render, crop_image
from .layout import prepare_regions, build_paragraphs, overlap, cb, refine_detections
from .math_engine import get_engine
from .writer import write_editable, write_pages

@dataclass
class Result:
    docx: bytes
    report_text: str
    report_json: str


def convert(source, mode=Mode.IMAGES, *, max_mb=50, max_pages=100, progress=None,
            engine=None, pandoc=None, selected_pages=None):
    """Нет постоянных файлов и глобального состояния документа. engine — внедрение для тестов."""
    mode=Mode(mode)
    progress=progress or (lambda fraction, stage: None)
    report=Report(mode.value)
    progress(.02,'Проверка PDF')
    meta=inspect_pdf(source,max_mb,max_pages)
    indices=list(range(len(meta))) if selected_pages is None else [p-1 for p in selected_pages]
    if not indices or any(i<0 or i>=len(meta) for i in indices) or indices!=sorted(set(indices)):
        raise ConversionError('Неверный список страниц.')
    report.pages=len(indices)
    if mode!=Mode.PAGES and any(meta[i]['chars']<10 for i in indices):
        raise ConversionError('На части страниц нет пригодного текстового слоя. Для скана выберите «Сохранить внешний вид».')
    if mode!=Mode.PAGES and engine is None:
        progress(.05,'Загрузка локальных моделей (первый запуск может требовать интернет)')
        engine=get_engine(mode==Mode.OMML)
    if mode==Mode.PAGES:
        report.warn(0,'Страницы сохранены изображениями; весь текст и формулы не редактируются. Математические области не обнаруживались.')
    else:
        report.warn(0,'Одна колонка: структура и границы формул восстановлены приближённо. Сверьте результат с PDF. Дефисы на переносах сохранены во избежание изменения выражений.')
    with tempfile.TemporaryDirectory(prefix='mathpdf-') as tmp:
        work=Path(tmp); paragraphs=[]; images=[]; sizes=[]
        with pdfplumber.open(source) as text_pdf, pdfium.PdfDocument(str(source)) as rendered_pdf:
            for n,index in enumerate(indices):
                page=text_pdf.pages[index]
                progress(.1+.72*n/len(indices), f'Страница {index+1}: извлечение и обработка областей')
                image=render(rendered_pdf,index)
                size=(page.width,page.height)
                if mode==Mode.PAGES:
                    path=work/f'page-{index+1}.png'; image.save(path)
                    images.append(path); sizes.append(size)
                    report.blocks.append(Block(index+1,(0,0,*size),'page_image',crop=path.name,method='page_image'))
                else:
                    try:
                        detected=engine.detect(image,size)
                    except Exception as e:
                        raise ConversionError(f'Стр. {index+1}: ошибка детектора формул. Выберите «Сохранить внешний вид». Причина: {e}') from e
                    detected=refine_detections(page.chars,detected,report,index+1,image,size)
                    raw_boxes=[d['bbox'] if isinstance(d,dict) else d for d in detected]
                    regions=prepare_regions(page.chars,raw_boxes,*size,report,index+1)
                    math=[]
                    for j,bbox in enumerate(regions):
                        path=work/f'p{index+1}-math{j}.png'
                        crop_image(image,bbox,size,path)
                        inline=not any(isinstance(d,dict) and not d['inline'] and overlap(d['bbox'],bbox)>.5*(d['bbox'][2]-d['bbox'][0])*(d['bbox'][3]-d['bbox'][1]) for d in detected)
                        related=[d for d in detected if isinstance(d,dict) and d.get('anchor_y') is not None and overlap(d['bbox'],bbox)>0]
                        anchor_y=max(related,key=lambda d:overlap(d['bbox'],bbox))['anchor_y'] if related else None
                        block=Block(index+1,bbox,'math',crop=path.name,inline=inline,anchor_y=anchor_y)
                        # Полный путь нужен только сборщику. В отчёте сохраняется идентификатор.
                        block.crop=str(path); math.append(block)
                    report.math_regions+=len(math)
                    # Растровые иллюстрации: сохранить, не молча пропускать.
                    extras=[]
                    for j,im in enumerate(page.images):
                        bbox=(im['x0'],im['top'],im['x1'],im['bottom'])
                        if any(overlap(bbox,m.bbox)>0 for m in math):
                            report.warn(index+1,'Растровая иллюстрация пересекает формулу; проверьте полноту вырезки.')
                        else:
                            path=work/f'p{index+1}-figure{j}.png'; crop_image(image,bbox,size,path)
                            extras.append(Block(index+1,bbox,'figure',crop=str(path)))
                    if page.curves or page.lines or page.rects:
                        report.warn(index+1,'Есть векторные линии/контуры. Внутри математических вырезок они сохранены; отдельные рисунки требуют проверки. Для точной сохранности выберите режим внешнего вида.')
                    ps=build_paragraphs(page,math,report)
                    for paragraph in ps:
                        remaining=''.join(b.text for b in paragraph.parts).strip()
                        if not any(b.kind!='text' for b in paragraph.parts) and remaining in ['[',']','(',')','√']:
                            report.warn(index+1,f'Остаточный знак {remaining!r} рядом с формулами: проверьте, не повторяется ли он в вырезке. Автоматически не удалён.')
                    from .schema import Paragraph
                    for b in extras: ps.append(Paragraph(index+1,b.bbox,[b]))
                    ps.sort(key=lambda p:(p.bbox[1],p.bbox[0]))
                    paragraphs.extend(ps)
                image.close()
        progress(.88,'Сборка DOCX')
        output=work/'result.docx'
        if mode==Mode.PAGES:
            write_pages(images,sizes,output,report)
        else:
            write_editable(paragraphs,output,mode,report,engine,pandoc)
            report.blocks=[b for p in paragraphs for b in p.parts]
            for b in report.blocks:
                if b.crop: b.crop=Path(b.crop).name
        result=Result(output.read_bytes(),report.readable(),report.json())
    progress(1,'Готово')
    return result
