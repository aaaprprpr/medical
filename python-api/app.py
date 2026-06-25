import base64
import html
import io
import logging
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from ttst_backend_inference_demo import TTSTMacePredictor, natural_key

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "output"

app = FastAPI(title="Medical Model API")
_predictor = None


class PredictPathRequest(BaseModel):
    data_path: str


def get_predictor():
    global _predictor
    if _predictor is None:
        logger.info("Loading TTST MACE models from %s", MODEL_DIR)
        _predictor = TTSTMacePredictor(
            cine_checkpoint=MODEL_DIR / "Cine_vitpre_last2_lossbal_b128_checkpoint.pth",
            lge_checkpoint=MODEL_DIR / "LGE_vitpre_last2_lossbal_b32_checkpoint.pth",
            sequence_checkpoint=MODEL_DIR / "TTST_seq_selected_lossbal_ga2_checkpoint.pth",
        )
        logger.info("TTST MACE models loaded.")
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
            target_path = target_path.with_name(f"{index}_{target_path.name}")

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(await upload.read())
        saved_paths.append(target_path)

    return saved_paths


def find_child_dir(path, name):
    path = Path(path)
    if not path.exists() or not path.is_dir():
        return None

    for child in path.iterdir():
        if child.is_dir() and child.name.lower() == name.lower():
            return child

    return None


def has_cine_locations(cine_patient_dir):
    sa_dir = find_child_dir(cine_patient_dir, "SA")
    location_root = sa_dir if sa_dir is not None else Path(cine_patient_dir)

    if not location_root.exists() or not location_root.is_dir():
        return False

    return any(
        child.is_dir() and child.name.lower().startswith("location")
        for child in location_root.iterdir()
    )


def is_frontend_patient_dir(path):
    cine_dir = find_child_dir(path, "Cine")
    return cine_dir is not None and has_cine_locations(cine_dir)


def is_evaluation_root(path):
    path = Path(path)
    cine_root = find_child_dir(path, "Cine")
    lge_root = find_child_dir(path, "LGE")

    if cine_root is None or lge_root is None:
        return False

    return any(
        child.is_dir() and has_cine_locations(child)
        for child in cine_root.iterdir()
    )


def find_evaluation_root(data_path):
    data_path = Path(data_path)
    if is_evaluation_root(data_path):
        return data_path

    for child in sorted(data_path.iterdir(), key=natural_key):
        if child.is_dir() and is_evaluation_root(child):
            return child

    return None


def collect_frontend_patients(data_path):
    data_path = Path(data_path)

    if not data_path.exists():
        raise FileNotFoundError(f"data_path does not exist: {data_path}")

    if is_frontend_patient_dir(data_path):
        patient_dirs = [data_path]
    else:
        patient_dirs = [
            child
            for child in sorted(data_path.iterdir(), key=natural_key)
            if child.is_dir() and is_frontend_patient_dir(child)
        ]

    patients = []
    for patient_dir in patient_dirs:
        patients.append(
            {
                "patient_id": patient_dir.name,
                "cine_dir": find_child_dir(patient_dir, "Cine"),
                "lge_dir": find_child_dir(patient_dir, "LGE"),
            }
        )

    if not patients:
        raise RuntimeError(
            f"No frontend-format patient folders were found under {data_path}. "
            "Expected Patient/Cine[/SA]/Location_xx/Frame_xx.png"
        )

    return patients


def collect_evaluation_patients(data_path):
    data_path = Path(data_path)

    if not data_path.exists():
        raise FileNotFoundError(f"data_path does not exist: {data_path}")

    evaluation_root = find_evaluation_root(data_path)
    if evaluation_root is None:
        raise RuntimeError(
            f"No evaluation-format dataset was found under {data_path}. "
            "Expected Final_test_data/Cine/Patient_xxx/SA/Location_xx/Frame_xx.png"
        )

    cine_root = find_child_dir(evaluation_root, "Cine")
    lge_root = find_child_dir(evaluation_root, "LGE")

    patients = []
    for cine_patient_dir in sorted(cine_root.iterdir(), key=natural_key):
        if not cine_patient_dir.is_dir() or not has_cine_locations(cine_patient_dir):
            continue

        patient_id = cine_patient_dir.name
        lge_patient_dir = lge_root / patient_id
        patients.append(
            {
                "patient_id": patient_id,
                "cine_dir": cine_patient_dir,
                "lge_dir": lge_patient_dir if lge_patient_dir.exists() else None,
            }
        )

    if not patients:
        raise RuntimeError(
            f"No patient folders were found under {cine_root}"
        )

    return patients


def predict_patients(patients):
    predictor = get_predictor()
    rows = []

    for patient in patients:
        lge_dir = patient["lge_dir"]
        mace_score = predictor.predict_patient(patient["cine_dir"], lge_dir)
        result = "mace_cine" if mace_score >= 0.5 else "no_mace"
        probability = mace_score if result == "mace_cine" else 1.0 - mace_score

        rows.append(
            {
                "patient_id": patient["patient_id"],
                "filename": patient["patient_id"],
                "result": result,
                "pred_label": 1 if result == "mace_cine" else 0,
                "probability": probability,
                "prob_mace": mace_score,
                "prob_no_mace": 1.0 - mace_score,
                "has_lge": lge_dir is not None,
                "cine_dir": str(patient["cine_dir"]),
                "lge_dir": "" if lge_dir is None else str(lge_dir),
            }
        )

    return rows


def build_api_response(rows):
    response = {
        "count": len(rows),
        "results": rows,
    }

    if len(rows) == 1:
        response.update(rows[0])

    return response


def worksheet_cell_xml(cell_ref, value, is_number=False):
    if is_number:
        return f'<c r="{cell_ref}"><v>{value}</v></c>'

    return '<c r="{cell_ref}" t="inlineStr"><is><t>{value}</t></is></c>'.format(
        cell_ref=cell_ref,
        value=html.escape(str(value)),
    )


def build_output_table_xlsx(results):
    rows_xml = [
        '<row r="1">{}</row>'.format(
            worksheet_cell_xml("A1", "patient_index")
            + worksheet_cell_xml("B1", "mace_score")
        )
    ]

    for index, result in enumerate(results, start=2):
        rows_xml.append(
            '<row r="{row}">{cells}</row>'.format(
                row=index,
                cells=worksheet_cell_xml("A{}".format(index), result["patient_index"])
                + worksheet_cell_xml(
                    "B{}".format(index),
                    "{:.6f}".format(result["mace_score"]),
                    is_number=True,
                ),
            )
        )

    sheet_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    {rows}
  </sheetData>
</worksheet>
""".format(
        rows="\n    ".join(rows_xml)
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>
""",
        )
        workbook.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
""",
        )
        workbook.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
""",
        )
        workbook.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>
""",
        )
        workbook.writestr("xl/worksheets/sheet1.xml", sheet_xml)

    return buffer.getvalue()


def build_evaluation_api_response(rows):
    results = [
        {
            "patient_index": row["patient_id"],
            "mace_score": row["prob_mace"],
        }
        for row in rows
    ]
    xlsx_bytes = build_output_table_xlsx(results)

    return {
        "count": len(results),
        "results": results,
        "xlsxFilename": "output_table.xlsx",
        "xlsxBase64": base64.b64encode(xlsx_bytes).decode("ascii"),
    }


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
            patients = collect_frontend_patients(temp_root)
            rows = predict_patients(patients)
        except Exception as exc:
            logger.exception("Prediction failed for uploaded files.")
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = build_api_response(rows)
    logger.info("Prediction completed: %s patient(s)", response["count"])
    return response


@app.post("/predict-path")
def predict_path(request: PredictPathRequest):
    try:
        patients = collect_frontend_patients(request.data_path)
        rows = predict_patients(patients)
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
            patients = collect_evaluation_patients(temp_root)
            rows = predict_patients(patients)
        except Exception as exc:
            logger.exception("Evaluation failed for uploaded files.")
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = build_evaluation_api_response(rows)
    logger.info("Evaluation completed: %s patient(s)", response["count"])
    return response


@app.post("/evaluate-path")
def evaluate_path(request: PredictPathRequest):
    try:
        patients = collect_evaluation_patients(request.data_path)
        rows = predict_patients(patients)
    except Exception as exc:
        logger.exception("Evaluation failed for local path: %s", request.data_path)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = build_evaluation_api_response(rows)
    logger.info("Evaluation completed: %s patient(s)", response["count"])
    return response
