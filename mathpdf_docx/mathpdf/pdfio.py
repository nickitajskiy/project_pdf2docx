from pathlib import Path
import pdfplumber
import pypdfium2 as pdfium
from .schema import ConversionError


def inspect_pdf(path, max_mb=50, max_pages=100):
    path = Path(path)
    if not path.is_file() or not path.stat().st_size:
        raise ConversionError('PDF отсутствует или пуст.')
    if path.stat().st_size > max_mb * 1024**2:
        raise ConversionError(f'PDF превышает ограничение {max_mb} МБ.')
    try:
        with pdfplumber.open(path) as pdf:
            if pdf.doc.encryption:
                raise ConversionError('PDF зашифрован. Сохраните незашифрованную копию.')
            if not pdf.pages:
                raise ConversionError('В PDF нет страниц.')
            if len(pdf.pages) > max_pages:
                raise ConversionError(f'В PDF больше {max_pages} страниц.')
            pages = [{'width': p.width, 'height': p.height, 'chars': len(p.chars)} for p in pdf.pages]
            if any(p['width'] <= 0 or p['height'] <= 0 or max(p['width'],p['height']) > 3000 for p in pages):
                raise ConversionError('Неподдерживаемый размер страницы (максимум 3000 пунктов).')
            return pages
    except ConversionError:
        raise
    except Exception as e:
        raise ConversionError('Не удалось прочитать PDF: файл повреждён или защищён.') from e


def render(pdf, index, dpi=216):
    page = pdf[index]
    try:
        bitmap = page.render(scale=dpi / 72)
        try:
            return bitmap.to_pil().convert('RGB').copy()
        finally:
            bitmap.close()
    finally:
        page.close()


def crop_image(image, bbox, page_size, path):
    sx, sy = image.width / page_size[0], image.height / page_size[1]
    image.crop((int(bbox[0]*sx), int(bbox[1]*sy),
                min(image.width, int(bbox[2]*sx+1)), min(image.height, int(bbox[3]*sy+1)))).save(path)
