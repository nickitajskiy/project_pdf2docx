from dataclasses import dataclass, field, asdict
from enum import Enum
import json

class Mode(str, Enum):
    IMAGES = 'Редактируемый текст, формулы изображениями'
    OMML = 'Редактируемые формулы'
    PAGES = 'Сохранить внешний вид'

class ConversionError(Exception):
    """Сообщение, пригодное для показа пользователю."""

@dataclass
class Block:
    page: int
    bbox: tuple[float, float, float, float]
    kind: str
    text: str = ''
    latex: str = ''
    latex_for_omml: str = ''
    latex_normalizations: list[str] = field(default_factory=list)
    crop: str = ''
    method: str = ''
    warnings: list[str] = field(default_factory=list)
    anchor_y: float | None = None
    inline: bool = True
    superscript: bool = False
    size: float = 12
    bold: bool = False

@dataclass
class Paragraph:
    page: int
    bbox: tuple
    parts: list[Block]
    heading: bool = False
    page_number: bool = False

@dataclass
class Report:
    mode: str
    pages: int = 0
    math_regions: int = 0
    omml: int = 0
    formula_images: int = 0
    page_images: int = 0
    warnings: list[dict] = field(default_factory=list)
    blocks: list[Block] = field(default_factory=list)

    def warn(self, page, message):
        self.warnings.append({'page': page, 'message': message})

    def json(self):
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    def readable(self):
        lines = [f'Режим: {self.mode}', f'Обработано страниц: {self.pages}',
                 f'Математических областей: {self.math_regions}', f'OMML: {self.omml}',
                 f'Формул изображениями: {self.formula_images}',
                 f'Страниц изображениями: {self.page_images}',
                 'Счётчики не являются оценкой точности.',
                 'Все результаты распознавания LaTeX требуют проверки по оригиналу.']
        lines += [f"Стр. {w['page'] or '—'}: {w['message']}" for w in self.warnings]
        for b in self.blocks:
            if b.latex:
                lines.append(f'Стр. {b.page}, {b.bbox}: непроверенный LaTeX: {b.latex} [{b.method}]')
                if b.latex_normalizations:
                    lines.append('  Для OMML: ' + b.latex_for_omml)
                    lines.extend('  Совместимость: '+change for change in b.latex_normalizations)
        return '\n'.join(lines)
