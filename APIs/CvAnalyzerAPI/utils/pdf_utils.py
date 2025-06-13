import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import os

# Si estás en Windows, especificá la ruta a tesseract.exe:
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def extract_text_from_pdf(file_bytes: bytes) -> str:
    doc = fitz.open("pdf", file_bytes)
    text = ""

    for page in doc:
        # Intentar extraer texto directamente
        page_text = page.get_text().strip()
        if page_text:
            text += page_text + "\n"
        else:
            # Si no hay texto, aplicar OCR
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            ocr_text = pytesseract.image_to_string(img, lang="eng")  # podés cambiar a "spa" si el CV está en español
            text += ocr_text + "\n"

    return text
