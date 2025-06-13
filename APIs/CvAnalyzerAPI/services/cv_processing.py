import os
import json
from dotenv import load_dotenv
import google.generativeai as genai
from utils.pdf_utils import extract_text_from_pdf

# Cargar API key desde .env
load_dotenv()
GENAI_API_KEY = os.getenv("GENAI_API_KEY")
if not GENAI_API_KEY:
    raise RuntimeError("Falta definir GENAI_API_KEY en el archivo .env")

# Configurar modelo Gemini
genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel(
    "gemini-1.5-flash",
    generation_config={"temperature": 0.2, "top_p": 1.0, "max_output_tokens": 2048}
)

# Validar si el texto parece un CV real
def validate_cv_with_gemini(text: str) -> bool:
    prompt = (
        "Sos un especialista en RRHH. Analizá el siguiente texto y devolveme solo 'Sí' si es un currículum vitae (CV) "
        "de una persona (con educación, experiencia, etc), o 'No' si no lo es. No des ninguna explicación.\n\n"
        f"Texto:\n{text[:4000]}"
    )
    resp = model.generate_content(prompt)
    ans = resp.text.strip().lower()
    return ans.startswith("sí") or ans.startswith("si")

# Extraer campos estructurados del CV
def extract_cv_fields_with_gemini(text: str) -> dict:
    prompt = (
        "Sos un especialista en RRHH y tu tarea es estandarizar CVs para insertarlos en una base de datos. "
        "Del siguiente texto de CV, devolvé SOLO un JSON válido (sin explicación ni texto adicional) con esta estructura exacta:\n\n"
        "{\n"
        '  "experiencia": [\n'
        '    {"puesto": "", "empresa": "", "funciones": "", "años_experiencia": ""}\n'
        "  ],\n"
        '  "educacion": [\n'
        '    {"titulo": "", "institucion": "", "certificaciones": []}\n'
        "  ],\n"
        '  "habilidades_tecnicas": [],\n'
        '  "habilidades_blandas": [],\n'
        '  "nivel_dominio": {"habilidad": "nivel"},\n'
        '  "idiomas": [ {"idioma": "", "nivel": ""} ],\n'
        '  "proyectos_relevantes": [ {"nombre": "", "descripcion": ""} ],\n'
        '  "ubicacion_actual": {"pais": "", "provincia": "", "ciudad": ""},\n'
        '  "disponibilidad": {"jornada": "", "disponibilidad_inmediata": false, "modalidad": ""}\n'
        "}\n\n"
        "⚠️ INSTRUCCIONES IMPORTANTES:\n"
        "- Extraé cada bloque por separado, no combines varios puestos o títulos en uno.\n"
        "- Asociá cada título exclusivamente con su institución más cercana. No asumas ni completes si no está claro.\n"
        "- Si un campo no aparece en el texto, ponelo vacío o null según corresponda.\n"
        "- No inventes información. Solo usá lo que está explícitamente presente.\n"
        "- Para idiomas y niveles de dominio, usá los que estén expresados o implícitos (ej: 'fluido en inglés' → nivel alto).\n"
        "- En disponibilidad, inferí jornada (full-time, part-time), modalidad (remoto, presencial, híbrido), y si está disponible ahora.\n"
        "- En ubicación, usá solo la ciudad/país mencionados, sin adivinar si no están claros.\n\n"
        f"Texto del CV:\n{text[:9000]}"
    )

    resp = model.generate_content(prompt)
    raw = resp.text.strip()
    print("==== RESPUESTA DE GEMINI (CV ESTANDARIZADO) ====")
    print(raw)
    print("=================================================")
    try:
        return json.loads(raw)
    except Exception:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            return json.loads(raw[start:end+1])
        raise ValueError(f"No se pudo extraer JSON válido. Respuesta:\n{raw}")

# Lógica principal para analizar un PDF
def analyze_cv_bytes(file_bytes: bytes) -> dict:
    text = extract_text_from_pdf(file_bytes)
    if not validate_cv_with_gemini(text):
        raise ValueError("El archivo no parece un CV válido según Gemini.")
    return extract_cv_fields_with_gemini(text)
