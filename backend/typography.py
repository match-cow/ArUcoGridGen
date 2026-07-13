from pathlib import Path

import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_NAME = "Vera"
FONT_PATH = Path(reportlab.__file__).resolve().parent / "fonts" / "Vera.ttf"
ANNOTATION_FONT_PT = 7.0


def register_fonts() -> None:
    if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_NAME, str(FONT_PATH)))


register_fonts()
