import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from run_test import TTSTPredictor, build_api_response, build_evaluation_api_response

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Medical Model API")
_predictor = None


class PredictPathRequest(BaseModel):
    data_path: str


def get_predictor():
    global _predictor
    if _predictor is None:
        logger.info("Loading TTST models...")
        _predictor = TTSTPredictor()
        logger.info("TTST models loaded.")
    return _predictor


def safe_upload_path(filename):
    cleaned = (filename or "upload").replace("\\", "/")
    parts = []

    for part in cleaned.split("/"):
        if not part or part in {".", ".."}:
            continue
        parts.append(part.replace(":", "_"))

    if not parts:
        parts = ["upload"]

    return Path(*parts)


async def save_upload_files(upload_files, target_root):
    saved_paths = []
    for index, upload in enumerate(upload_files):
        relative_path = safe_upload_path(upload.filename)
        target_path = target_root / relative_path

        if target_path.exists():
            target_path = target_path.with_name("{}_{}".format(index, target_path.name))

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(await upload.read())
        saved_paths.append(target_path)

    return saved_paths


@app.get("/health")
def health():
    return {
        "status": "UP",
        "model_loaded": _predictor is not None,
    }


@app.post("/predict")
async def predict(
    files: Optional[List[UploadFile]] = File(default=None),
    file: Optional[UploadFile] = File(default=None),
):
    upload_files = []
    if files:
        upload_files.extend(files)
    if file:
        upload_files.append(file)

    if not upload_files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    with TemporaryDirectory(prefix="medical_predict_") as temp_dir:
        temp_root = Path(temp_dir)
        await save_upload_files(upload_files, temp_root)

        try:
            rows = get_predictor().predict_path(temp_root)
        except Exception as exc:
            logger.exception("Prediction failed for uploaded files.")
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = build_api_response(rows)
    logger.info("Prediction completed: %s patient(s)", response["count"])
    return response


@app.post("/predict-path")
def predict_path(request: PredictPathRequest):
    try:
        rows = get_predictor().predict_path(request.data_path)
    except Exception as exc:
        logger.exception("Prediction failed for local path: %s", request.data_path)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = build_api_response(rows)
    logger.info("Prediction completed: %s patient(s)", response["count"])
    return response


@app.post("/evaluate")
async def evaluate(files: Optional[List[UploadFile]] = File(default=None)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    with TemporaryDirectory(prefix="medical_evaluate_") as temp_dir:
        temp_root = Path(temp_dir)
        await save_upload_files(files, temp_root)

        try:
            rows = get_predictor().predict_path(temp_root)
        except Exception as exc:
            logger.exception("Evaluation failed for uploaded files.")
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = build_evaluation_api_response(rows)
    logger.info("Evaluation completed: %s patient(s)", response["count"])
    return response


@app.post("/evaluate-path")
def evaluate_path(request: PredictPathRequest):
    try:
        rows = get_predictor().predict_path(request.data_path)
    except Exception as exc:
        logger.exception("Evaluation failed for local path: %s", request.data_path)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = build_evaluation_api_response(rows)
    logger.info("Evaluation completed: %s patient(s)", response["count"])
    return response
