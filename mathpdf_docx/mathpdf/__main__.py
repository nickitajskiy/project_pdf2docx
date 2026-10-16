import argparse
import importlib.metadata as md
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from .schema import Mode, ConversionError


def doctor(load_models=False, recognition=False):
    data={'python':sys.version.split()[0], 'pandoc':shutil.which('pandoc'), 'packages':{}}
    for name in ['pdfplumber','pypdfium2','python-docx','streamlit','pix2text','transformers','optimum','cnstd']:
        try: data['packages'][name]=md.version(name)
        except md.PackageNotFoundError: data['packages'][name]='не установлен'
    data['models']='не загружались (это не проверка доступности весов)'
    if load_models:
        try:
            from .math_engine import get_engine
            from PIL import Image
            engine=get_engine(recognition)
            engine.detect(Image.new('RGB',(400,300),'white'),(400,300))
            data['models']='MFD загружен, выполнен пробный inference'
            if recognition:
                data['models']+='; MFR загружен (проверка OCR выполняется на реальной формуле отдельно)'
        except Exception as e: data['models']=str(e)
    print(json.dumps(data,ensure_ascii=False,indent=2))
    return data


def main():
    parser=argparse.ArgumentParser(description='Локальная конвертация математического PDF в DOCX')
    sub=parser.add_subparsers(dest='command',required=True)
    d=sub.add_parser('doctor'); d.add_argument('--load-models',action='store_true'); d.add_argument('--recognition',action='store_true')
    c=sub.add_parser('convert'); c.add_argument('pdf',type=Path); c.add_argument('docx',type=Path)
    c.add_argument('--mode',choices=['images','omml','pages'],default='images')
    c.add_argument('--pages',help='Номера через запятую, например 1,2,5,8')
    c.add_argument('--max-mb',type=int,default=50); c.add_argument('--max-pages',type=int,default=100)
    args=parser.parse_args()
    if args.command=='doctor':
        data=doctor(args.load_models,args.recognition)
        return int(args.load_models and 'недоступна' in data['models'])
    from .converter import convert
    try:
        if args.pdf.resolve()==args.docx.resolve():
            raise ConversionError('Выходной файл должен отличаться от исходного PDF.')
        pages=[int(p) for p in args.pages.split(',')] if args.pages else None
        result=convert(args.pdf,{'images':Mode.IMAGES,'omml':Mode.OMML,'pages':Mode.PAGES}[args.mode],
                       max_mb=args.max_mb,max_pages=args.max_pages,selected_pages=pages,
                       progress=lambda _,s:print(s))
        args.docx.parent.mkdir(parents=True,exist_ok=True)
        args.docx.write_bytes(result.docx)
        args.docx.with_suffix('.report.txt').write_text(result.report_text,encoding='utf-8')
        args.docx.with_suffix('.report.json').write_text(result.report_json,encoding='utf-8')
        return 0
    except Exception as e:
        print(f'Ошибка: {e}',file=sys.stderr); return 1

if __name__=='__main__':
    raise SystemExit(main())
