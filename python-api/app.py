from fastapi import FastAPI, File, UploadFile



app = FastAPI(title="Mock Medical Model API")


@app.get("/health")
def health():
    return {
        "status": "UP"
    }


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    return {
        "result": "POSITIVE",
        "probability": 0.8732,
        "filename": file.filename
    }

