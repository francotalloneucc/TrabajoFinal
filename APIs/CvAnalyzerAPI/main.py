from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from services.cv_processing import analyze_cv_bytes

app = FastAPI(
    title="CvAnalyzerAPI",
    description="API para análisis y validación de CVs usando IA",
    version="1.0.0"
)

# Configurar CORS para permitir conexiones desde tu frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://localhost:8000"],  # Frontend y UserAPI
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "CvAnalyzerAPI está funcionando correctamente"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "CvAnalyzerAPI"}

@app.post("/analyze/")
async def analyze(file: UploadFile = File(...)):
    """
    Analiza un archivo PDF para validar si es un CV y extraer datos estructurados
    """
    try:
        # Verificar que sea un PDF
        if not file.content_type.startswith('application/pdf'):
            raise HTTPException(
                status_code=400, 
                detail="El archivo debe ser un PDF"
            )
        
        contents = await file.read()
        result = analyze_cv_bytes(contents)
        
        return {
            "valid": True,
            "message": "CV analizado exitosamente",
            "data": result
        }
    except ValueError as e:
        # Error de validación (no es un CV)
        raise HTTPException(
            status_code=400, 
            detail=str(e)
        )
    except Exception as e:
        # Error general
        raise HTTPException(
            status_code=500, 
            detail=f"Error al procesar el CV: {str(e)}"
        )

# IMPORTANTE: Configurar puerto 8001 por defecto
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)