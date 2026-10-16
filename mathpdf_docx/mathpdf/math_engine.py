"""Только локальные MFD/MFR Pix2Text; OCR обычного текста не требуется."""
from functools import lru_cache
from pathlib import Path
import os
import threading
from .schema import ConversionError

MODEL_REVISIONS = {
    'mfd-1.5':'f470a885e0fca1d3d2bfa2a54991db7ae01f1861',
    'mfr-1.5':'1cef9f0bdcd6a4c63df7de1311fb0894593340cc',
}


def prepare_model(root, name):
    # Собственный загрузчик вместо shell-команды huggingface-cli в Pix2Text.
    # Данные документов сюда не передаются. После успешной загрузки сеть не нужна.
    directory = root / name
    if not (directory / '.complete').exists():
        from huggingface_hub import snapshot_download
        snapshot_download(repo_id=f'breezedeus/pix2text-{name}', revision=MODEL_REVISIONS[name], local_dir=str(directory),
                          cache_dir=str(root / '.cache'), max_workers=2,
                          allow_patterns=['*.onnx', '*.json', '*.txt', '*.model', 'LICENSE*', 'README*'])
        if not list(directory.rglob('*.onnx')):
            raise FileNotFoundError('В скачанной модели нет ONNX')
        (directory / '.complete').touch()
    return directory


class Pix2TextEngine:
    def __init__(self, recognition=False):
        try:
            # Явные пути позволяют работать без сетевого доступа после подготовки.
            root = Path(os.environ.get('MATHPDF_MODEL_DIR', 'models')).resolve()
            root.mkdir(parents=True, exist_ok=True)
            os.environ.setdefault('HF_HOME',str(root / '.hf'))
            os.environ.setdefault('MPLCONFIGDIR',str(root / '.mpl'))
            os.environ.setdefault('YOLO_CONFIG_DIR',str(root / '.yolo'))
            from pix2text.formula_detector import MathFormulaDetector
            det_path = os.environ.get('MATHPDF_MFD_PATH')
            if not det_path:
                directory = prepare_model(root, 'mfd-1.5')
                det_path = str(next(directory.rglob('*mfd*.onnx')))
            self.detector = MathFormulaDetector(model_name='mfd-1.5', model_backend='onnx',
                                                device='cpu', root=root, model_path=det_path)
            self.recognizer = None
            if recognition:
                from pix2text.latex_ocr import LatexOCR
                self.recognizer = LatexOCR(model_name='mfr-1.5', model_backend='onnx',
                                           device='cpu', root=root,
                                           model_dir=os.environ.get('MATHPDF_MFR_DIR') or str(prepare_model(root, 'mfr-1.5')))
            self.lock = threading.RLock()
        except Exception as e:
            raise ConversionError('Модель Pix2Text недоступна. Установите requirements-math.txt, '
                                  'затем выполните python -m mathpdf doctor --load-models. '
                                  f'Доступен режим «Сохранить внешний вид». Причина: {type(e).__name__}: {e}') from e

    def detect(self, image, page_size):
        with self.lock:
            result = self.detector(image, resized_shape=1536)
        sx, sy = page_size[0]/image.width, page_size[1]/image.height
        boxes = []
        for item in result:
            box = item['box']
            xs, ys = [float(p[0])*sx for p in box], [float(p[1])*sy for p in box]
            boxes.append({'bbox':(min(xs), min(ys), max(xs), max(ys)), 'inline':item['type']=='embedding'})
        return boxes

    def recognize(self, image):
        if self.recognizer is None:
            raise ConversionError('Модель распознавания LaTeX не загружена.')
        with self.lock:
            # Не исправлять выражения постпроцессором Pix2Text.
            result = self.recognizer.recognize(image, use_post_process=False,
                                               rec_config={'max_new_tokens': 512})
        return result['text'].strip()

@lru_cache(maxsize=2)
def get_engine(recognition=False):
    return Pix2TextEngine(recognition)
