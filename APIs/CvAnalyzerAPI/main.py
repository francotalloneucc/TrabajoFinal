from fastapi import FastAPI, UploadFile, File, HTTPException
from services.cv_processing import analyze_cv_bytes

app = FastAPI()

@app.post("/analyze/")
async def analyze(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        result = analyze_cv_bytes(contents)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
