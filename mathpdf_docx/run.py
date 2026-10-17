"""Запуск окна Tkinter из IDE или командой python run.py."""
from pathlib import Path
import os
import sys


def main():
    root = Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    os.environ.setdefault('MATHPDF_MODEL_DIR', str(root/'models'))
    try:
        from mathpdf.desktop import main as launch
        launch()
    except ImportError as exc:
        print(f'Не удалось загрузить приложение: {exc}\nУстановите requirements.txt в выбранное окружение Python. '
              'Если отсутствует tkinter, установите Python с Tcl/Tk.', file=sys.stderr)
        return 1
    except Exception as exc:
        print(f'Не удалось открыть окно: {type(exc).__name__}: {exc}. Проверьте окружение командой python -m mathpdf doctor.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
