from pathlib import Path
import hashlib
import json
import os
import tempfile
import streamlit as st
from mathpdf.converter import convert
from mathpdf.schema import Mode, ConversionError

st.set_page_config(page_title='Математический PDF → Word',page_icon='📄')
st.title('Математический PDF → Word')
st.write('Локальный учебный конвертер одноколоночных PDF с русским текстовым слоем. Точное совпадение вёрстки и распознавание всех формул не гарантируются.')
max_mb=int(os.environ.get('MATHPDF_MAX_MB','50'))
max_pages=int(os.environ.get('MATHPDF_MAX_PAGES','100'))
st.caption(f'Ограничения: {max_mb} МБ, {max_pages} страниц. PDF не отправляется внешним сервисам. При первом запуске Pix2Text может скачивать модели.')
mode=st.selectbox('Режим',list(Mode),format_func=lambda m:m.value)
if mode==Mode.PAGES:
    st.info('Каждая страница будет изображением. Текст и формулы не редактируются. Подходит для сканов и сложной вёрстки.')
elif mode==Mode.OMML:
    st.warning('Нужны модели Pix2Text и Pandoc. Распознанные формулы требуют проверки по оригиналу. Ошибки распознавания возможны даже при правильном синтаксисе. Неподдерживаемые формулы станут изображениями с предупреждением в отчёте.')
else:
    st.info('Нужна модель обнаружения Pix2Text. Текст редактируется, формулы сохраняются вырезками из оригинала. Для колонок и сканов используйте режим внешнего вида.')
upload=st.file_uploader('Выберите PDF',type=['pdf'])
key=None
if upload:
    payload=upload.getvalue()
    key=(hashlib.sha256(payload).hexdigest(),mode.value)
    if len(payload)>max_mb*1024**2: st.error(f'Файл больше {max_mb} МБ.'); st.stop()
if st.button('Конвертировать',type='primary',disabled=upload is None):
    st.session_state.pop('conversion',None)
    bar=st.progress(0,text='Подготовка')
    try:
        with tempfile.TemporaryDirectory(prefix='mathpdf-upload-') as tmp:
            path=Path(tmp)/'source.pdf'; path.write_bytes(payload)
            result=convert(path,mode,max_mb=max_mb,max_pages=max_pages,
                           progress=lambda p,s:bar.progress(p,text=s))
        st.session_state.conversion=(key,result)
    except ConversionError as e: st.error(str(e))
    except Exception as e:
        st.error(f'Не удалось завершить обработку: {type(e).__name__}: {e}. Попробуйте режим «Сохранить внешний вид».')
if 'conversion' in st.session_state and st.session_state.conversion[0]==key:
    result=st.session_state.conversion[1]
    st.success('DOCX создан. Проверьте формулы и структуру по оригиналу.')
    if mode==Mode.OMML:
        counts=json.loads(result.report_json)
        st.write(f"Редактируемых формул Word: {counts['omml']}. Формул изображениями: {counts['formula_images']}.")
        if counts['formula_images']:
            st.warning('Часть формул осталась изображениями: причины указаны в отчёте. Эти формулы не редактируются как формулы Word.')
    st.download_button('Скачать DOCX',result.docx,'result.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    st.download_button('Скачать понятный отчёт',result.report_text,'report.txt','text/plain; charset=utf-8')
    st.download_button('Скачать структуру блоков JSON',result.report_json,'blocks.json','application/json')
    with st.expander('Отчёт'): st.text(result.report_text)
