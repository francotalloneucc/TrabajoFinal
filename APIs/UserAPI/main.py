from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import engine, Base
from routes import router
import os

# Solo crear las tablas si no existen (NO borrar las existentes)
Base.metadata.create_all(bind=engine)

# Crear directorios si no existen
os.makedirs("uploaded_cvs", exist_ok=True)
os.makedirs("profile_pictures", exist_ok=True)  # NUEVO: Directorio para fotos de perfil

app = FastAPI(
    title="UserAPI",
    description="API de usuarios con autenticación JWT",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],  # Puerto típico de Angular dev server
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Servir archivos estáticos (CVs)
app.mount("/uploaded_cvs", StaticFiles(directory="uploaded_cvs"), name="uploaded_cvs")

# Servir fotos de perfil
app.mount("/profile_pictures", StaticFiles(directory="profile_pictures"), name="profile_pictures")  # NUEVO

# Incluir las rutas
app.include_router(router, prefix="/api/v1", tags=["users"])

@app.get("/")
async def root():
    return {"message": "UserAPI está funcionando correctamente"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)