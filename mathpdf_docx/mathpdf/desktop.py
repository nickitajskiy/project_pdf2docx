"""Оконный интерфейс. Все вызовы Tk выполняются только в главном потоке."""
from pathlib import Path
from queue import Empty, Queue
import json
import os
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from .schema import Mode


MODE_HELP = {
    Mode.IMAGES: 'Текст редактируется. Формулы — изображения из PDF. Нужна модель обнаружения Pix2Text.',
    Mode.OMML: 'Формулы Word требуют сверки с PDF. Нужны Pix2Text и Pandoc; ошибки преобразования сохраняются изображениями.',
    Mode.PAGES: 'Страницы целиком сохраняются изображениями. Текст и формулы не редактируются. Модели не нужны.',
}


def conversion_worker(events, source, mode, max_mb, max_pages, converter=None):
    """Фоновой поток общается с окном только через очередь, без Tk-вызовов."""
    try:
        if converter is None:
            from .converter import convert
            converter = convert
        result = converter(source, mode, max_mb=max_mb, max_pages=max_pages,
                           progress=lambda value, stage: events.put(('progress', (value, stage))))
        events.put(('done', result))
    except Exception as exc:
        events.put(('error', f'{type(exc).__name__}: {exc}'))


def save_result(result, destination, source):
    """Сохраняет выбранный результат и оба отчёта, не затрагивая PDF."""
    target = Path(destination).expanduser().resolve()
    if target.suffix.lower() != '.docx':
        raise ValueError('Укажите имя с расширением .docx.')
    targets = [target, target.with_suffix('.report.txt'), target.with_suffix('.report.json')]
    if Path(source).resolve() in targets:
        raise ValueError('Нельзя записать результат поверх исходного PDF.')
    # Сначала подготовить все файлы; незавершённая запись не повреждает DOCX.
    with tempfile.TemporaryDirectory(prefix='.mathpdf-save-', dir=target.parent) as tmp:
        for index, payload in enumerate([result.docx, result.report_text.encode('utf-8'),
                                        result.report_json.encode('utf-8')]):
            Path(tmp, str(index)).write_bytes(payload)
        for index, path in enumerate(targets):
            os.replace(Path(tmp, str(index)), path)
    return targets


class DesktopApp:
    def __init__(self, root):
        self.root = root
        self.events = Queue()
        self.busy = False
        self.result = None
        self.result_source = None
        self.max_mb = int(os.environ.get('MATHPDF_MAX_MB', '50'))
        self.max_pages = int(os.environ.get('MATHPDF_MAX_PAGES', '100'))
        if self.max_mb <= 0 or self.max_pages <= 0:
            raise ValueError('Ограничения размера и числа страниц должны быть положительными.')
        root.title('Математический PDF → Word')
        root.geometry('860x680')
        root.minsize(680, 560)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        frame = ttk.Frame(root, padding=18)
        frame.grid(sticky='nsew')
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(9, weight=1)
        ttk.Label(frame, text='Математический PDF → Word', font=('TkDefaultFont', 18, 'bold')).grid(sticky='w')
        ttk.Label(frame, text='Одноколоночные учебные PDF с текстовым слоем. Точная вёрстка и безошибочное распознавание не гарантируются.',
                  wraplength=780).grid(row=1, column=0, columnspan=2, sticky='ew', pady=(8, 14))
        self.source = tk.StringVar()
        self.entry = ttk.Entry(frame, textvariable=self.source)
        self.entry.grid(row=2, column=0, sticky='ew')
        self.browse = ttk.Button(frame, text='Выбрать PDF…', command=self.choose_pdf)
        self.browse.grid(row=2, column=1, padx=(10, 0))
        self.mode = tk.StringVar(value=Mode.IMAGES.value)
        self.combo = ttk.Combobox(frame, textvariable=self.mode, values=[m.value for m in Mode], state='readonly')
        self.combo.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(14, 8))
        self.combo.bind('<<ComboboxSelected>>', self.change_mode)
        self.help = ttk.Label(frame, text=MODE_HELP[Mode.IMAGES], wraplength=780)
        self.help.grid(row=4, column=0, columnspan=2, sticky='ew')
        ttk.Label(frame, text=f'Лимиты: {self.max_mb} МБ, {self.max_pages} страниц. Обработка локальная. Первый запуск моделей требует интернета.',
                  wraplength=780).grid(row=5, column=0, columnspan=2, sticky='ew', pady=(8, 12))
        actions = ttk.Frame(frame)
        actions.grid(row=6, column=0, columnspan=2, sticky='ew')
        self.convert_button = ttk.Button(actions, text='Конвертировать', command=self.start)
        self.convert_button.pack(side='left')
        self.save_button = ttk.Button(actions, text='Сохранить DOCX и отчёты…', command=self.save, state='disabled')
        self.save_button.pack(side='left', padx=10)
        self.status = tk.StringVar(value='Выберите PDF и режим конвертации.')
        ttk.Label(frame, textvariable=self.status, wraplength=780).grid(row=7, column=0, columnspan=2, sticky='ew', pady=10)
        self.progress = ttk.Progressbar(frame, maximum=100)
        self.progress.grid(row=8, column=0, columnspan=2, sticky='ew', pady=(0, 10))
        report_frame = ttk.Frame(frame)
        report_frame.grid(row=9, column=0, columnspan=2, sticky='nsew')
        report_frame.columnconfigure(0, weight=1)
        report_frame.rowconfigure(0, weight=1)
        self.report = tk.Text(report_frame, wrap='word', height=14, state='disabled')
        self.report.grid(sticky='nsew')
        scrollbar = ttk.Scrollbar(report_frame, command=self.report.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.report.configure(yscrollcommand=scrollbar.set)
        self.source.trace_add('write', self.invalidate_result)
        self.poll_id = root.after(100, self.poll)

    def show_report(self, text):
        self.report.configure(state='normal')
        self.report.delete('1.0', 'end')
        self.report.insert('1.0', text)
        self.report.configure(state='disabled')

    def choose_pdf(self):
        filename = filedialog.askopenfilename(parent=self.root, title='Выберите PDF',
                                              filetypes=[('PDF', '*.pdf'), ('Все файлы', '*')])
        if filename:
            self.source.set(filename)

    def change_mode(self, event=None):
        self.help.configure(text=MODE_HELP[Mode(self.mode.get())])
        self.invalidate_result()

    def invalidate_result(self, *args):
        if self.busy or self.result is None:
            return
        self.result = None
        self.result_source = None
        self.save_button.configure(state='disabled')
        self.progress['value'] = 0
        self.show_report('')
        self.status.set('Параметры изменены. Нажмите «Конвертировать».')

    def set_busy(self, value):
        self.busy = value
        for widget in [self.entry, self.browse, self.convert_button]:
            widget.configure(state='disabled' if value else 'normal')
        self.combo.configure(state='disabled' if value else 'readonly')
        self.save_button.configure(state='normal' if not value and self.result else 'disabled')

    def start(self):
        if self.busy:
            return
        source = Path(self.source.get().strip()).expanduser()
        if not self.source.get().strip() or not source.is_file():
            messagebox.showerror('Не выбран PDF', 'Выберите существующий PDF-файл.', parent=self.root)
            return
        # Снимок параметров: изменения окна не меняют текущую задачу.
        self.result = None
        self.result_source = source.resolve()
        mode = Mode(self.mode.get())
        self.progress['value'] = 0
        self.status.set('Подготовка. При первом запуске загрузка моделей может занять несколько минут.')
        self.show_report('')
        self.set_busy(True)
        threading.Thread(target=conversion_worker, args=(self.events, self.result_source, mode,
                         self.max_mb, self.max_pages), daemon=True).start()

    def poll(self):
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == 'progress':
                    value, stage = payload
                    self.progress['value'] = max(0, min(100, value*100))
                    self.status.set(stage)
                elif event == 'done':
                    self.result = payload
                    counts = json.loads(payload.report_json)
                    self.progress['value'] = 100
                    self.show_report(payload.report_text)
                    self.status.set(f"Готово. Страниц: {counts['pages']}. Формул Word: {counts['omml']}. "
                                    f"Формул изображениями: {counts['formula_images']}. Сверьте результат с PDF.")
                    self.set_busy(False)
                elif event == 'error':
                    self.result = None
                    self.show_report(payload)
                    self.status.set('Конвертация не завершена. Причина указана в отчёте.')
                    self.set_busy(False)
                    messagebox.showerror('Ошибка конвертации', payload+'\n\nДля сканов или недоступных моделей попробуйте «Сохранить внешний вид».', parent=self.root)
        except Empty:
            pass
        self.poll_id = self.root.after(100, self.poll)

    def save(self):
        if not self.result or self.busy:
            return
        name = filedialog.asksaveasfilename(parent=self.root, title='Сохранить DOCX и отчёты',
                    initialfile=self.result_source.stem+'.docx', defaultextension='.docx',
                    filetypes=[('Документ Word', '*.docx')])
        if not name:
            return
        try:
            target = Path(name)
            reports = [target.with_suffix('.report.txt'), target.with_suffix('.report.json')]
            if any(p.exists() for p in reports) and not messagebox.askyesno('Замена отчётов',
                    'Рядом уже есть отчёты с этим именем. Заменить их?', parent=self.root):
                return
            paths = save_result(self.result, target, self.result_source)
            self.status.set('Сохранено: '+str(paths[0])+'. Отчёты находятся рядом.')
        except Exception as exc:
            messagebox.showerror('Не удалось сохранить', f'{exc}\nВыберите доступную папку и закройте файл в Word.', parent=self.root)

    def close(self):
        if self.busy:
            messagebox.showinfo('Идёт обработка', 'Дождитесь завершения конвертации, затем закройте окно.', parent=self.root)
            return
        self.root.after_cancel(self.poll_id)
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        DesktopApp(root)
    except Exception:
        root.destroy()
        raise
    root.mainloop()
