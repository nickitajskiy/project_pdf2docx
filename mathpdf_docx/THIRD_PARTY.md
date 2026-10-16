# Сторонние компоненты

Это сведения, а не перелицензирование компонентов. При распространении пакетов или моделей сохраняйте их собственные LICENSE/NOTICE и сверяйте конкретные версии.

| Компонент | Лицензия / источник |
|---|---|
| Python | PSF |
| pdfplumber | MIT — https://github.com/jsvine/pdfplumber |
| pdfminer.six | MIT — https://github.com/pdfminer/pdfminer.six |
| pypdfium2 | Apache-2.0 / BSD-3-Clause; PDFium и его зависимости имеют отдельные notices — https://github.com/pypdfium2-team/pypdfium2 |
| python-docx | MIT — https://github.com/python-openxml/python-docx |
| Pillow | MIT-CMU / HPND — https://github.com/python-pillow/Pillow |
| Streamlit | Apache-2.0 — https://github.com/streamlit/streamlit |
| Pix2Text | MIT — https://github.com/breezedeus/Pix2Text |
| CnSTD / CnOCR | Apache-2.0 — https://github.com/breezedeus/CnSTD ; https://github.com/breezedeus/CnOCR |
| Transformers / Optimum | Apache-2.0 — https://github.com/huggingface/transformers ; https://github.com/huggingface/optimum |
| PyTorch | BSD-3-Clause — https://github.com/pytorch/pytorch |
| ONNX Runtime | MIT — https://github.com/microsoft/onnxruntime |
| Pandoc (отдельная программа) | GPL-2.0-or-later — https://pandoc.org/license.html |
| pytest / ReportLab (тесты) | MIT / BSD — https://github.com/pytest-dev/pytest ; https://www.reportlab.com/ |

Pix2Text транзитивно устанавливает PyMuPDF (AGPL-3.0 либо коммерческая лицензия) и doclayout-yolo / Ultralytics (AGPL-3.0 по upstream). Конвертер не использует их для извлечения или анализа макета, но их присутствие в дистрибутиве окружения нужно учитывать. ZIP содержит исходники проекта, не Python-пакеты.

Открытые веса MFD/MFR имеют отдельные карточки: https://huggingface.co/breezedeus/pix2text-mfd-1.5 и https://huggingface.co/breezedeus/pix2text-mfr-1.5 . Карточки обеих загруженных моделей при проверке указали MIT (`license: mit`). Лицензия кода Pix2Text не является автоматической лицензией всех других весов. Перед распространением загруженных файлов сверяйте LICENSE/метаданные конкретной ревизии. Платные pro-модели не используются. Веса, шрифты и исходный пользовательский PDF не включаются в архив проекта.

Тестовые DOCX содержат материал пользовательского PDF. Лицензия MIT исходного кода не распространяется автоматически на содержание этого PDF.
