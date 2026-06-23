from __future__ import absolute_import, division, print_function

import argparse
import base64
import contextlib
import html
import io
import logging
import math
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

import torch
import torch.nn.functional as F
from PIL import Image, ImageFile
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

from models import vit
import models.IEPV as iepv_module
from models.modeling import CONFIGS, DSFI

ImageFile.LOAD_TRUNCATED_IMAGES = True

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
IMAGE_EXTENSIONS = {".bmp", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}
CLASS_TO_LABEL = {"mace_cine": 0, "no_mace": 1}
LABEL_TO_CLASS = {0: "mace_cine", 1: "no_mace"}
CLASS_NAME_ALIASES = {
    "mace": "mace_cine",
    "mace_cine": "mace_cine",
    "no_mace": "no_mace",
}
LOCATION_DIR_RE = re.compile(r"^location[_-]?(\d+)$", re.IGNORECASE)
FRAME_IMAGE_RE = re.compile(
    r"^frame[_-]?(\d+)\.(bmp|jpg|jpeg|png|tif|tiff)$", re.IGNORECASE
)
LGE_IMAGE_RE = re.compile(
    r"^location[_-]?(\d+)\.(bmp|jpg|jpeg|png|tif|tiff)$", re.IGNORECASE
)


@dataclass
class InferenceConfig:
    img_size: int = 224
    cine_length: int = 300
    lge_length: int = 12
    frames_per_location: int = 25
    batch_size: int = 1
    num_workers: int = 0
    max_patients: int = None
    device: object = None
    cine_checkpoint: Path = BASE_DIR / "output" / "Cine_img_model_checkpoint.pth"
    lge_checkpoint: Path = BASE_DIR / "output" / "LGE_img_model_checkpoint.pth"
    sequence_checkpoint: Path = (
        BASE_DIR / "output" / "TTST_SequenceTraining_checkpoint.pth"
    )


class RuntimeMultiHeadVoting(torch.nn.Module):
    """Device-neutral replacement for the project module's CUDA-only voting op."""

    def __init__(self, config, vote_perhead=24):
        super(RuntimeMultiHeadVoting, self).__init__()
        self.num_heads = config.num_heads
        self.vote_perhead = vote_perhead
        kernel = (
            torch.tensor(
                [[1, 2, 1], [2, 4, 2], [1, 2, 1]],
                dtype=torch.float32,
            )
            .unsqueeze(0)
            .unsqueeze(0)
        )
        self.register_buffer("kernel", kernel, persistent=False)

    def forward(self, x, select_num=None, enhance=True):
        batch_size = x.shape[0]
        patch_num = x.shape[3] - 1
        select_num = select_num or self.vote_perhead
        count_dtype = torch.float16 if x.device.type == "cuda" else torch.float32
        count = torch.zeros(
            (batch_size, patch_num),
            dtype=count_dtype,
            device=x.device,
        )

        score = x[:, :, 0, 1:]
        _, select = torch.topk(score, self.vote_perhead, dim=-1)
        select = select.reshape(batch_size, -1)

        for i, selected_index in enumerate(select):
            bincount = torch.bincount(selected_index, minlength=patch_num)
            count[i, :] += bincount.to(device=x.device, dtype=count.dtype)

        if enhance:
            count = self.enhace_local(count)

        _, patch_idx = torch.sort(count, dim=-1, descending=True)
        patch_idx += 1
        return patch_idx[:, :select_num]

    def enhace_local(self, count):
        batch_size = count.shape[0]
        height = math.ceil(math.sqrt(count.shape[1]))
        kernel = self.kernel.to(device=count.device, dtype=count.dtype)
        count = count.reshape(batch_size, height, -1)
        return F.conv2d(count.unsqueeze(1), kernel, stride=1, padding=1).reshape(
            batch_size, -1
        )


iepv_module.MultiHeadVoting = RuntimeMultiHeadVoting
IEPV = iepv_module.IEPV


@dataclass
class PatientInfo:
    patient_id: str
    cine_dir: Path
    lge_dir: Path
    class_name: str
    label: int


def pil_loader(path):
    with open(path, "rb") as handle:
        image = Image.open(handle)
        return image.convert("RGB")


def list_image_files(path):
    if path is None or not path.exists() or not path.is_dir():
        return []
    return [
        child
        for child in sorted(path.iterdir(), key=natural_sort_key)
        if child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS
    ]


def natural_sort_key(path):
    name = path.name if isinstance(path, Path) else str(path)
    return tuple(
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", name)
    )


def regex_number_sort_key(pattern, path):
    match = pattern.match(path.name)
    if match:
        return 0, int(match.group(1))
    return 1, natural_sort_key(path)


def find_child_dir(path, name):
    if path is None or not path.exists() or not path.is_dir():
        return None
    for child in path.iterdir():
        if child.is_dir() and child.name.lower() == name.lower():
            return child
    return None


def resolve_cine_location_root(patient_dir):
    cine_dir = find_child_dir(patient_dir, "Cine")
    if cine_dir is None:
        return None

    sa_dir = find_child_dir(cine_dir, "SA")
    return sa_dir if sa_dir is not None else cine_dir


def is_frontend_patient_dir(path):
    cine_root = resolve_cine_location_root(path)
    if cine_root is None:
        return False
    return any(
        child.is_dir() and LOCATION_DIR_RE.match(child.name)
        for child in cine_root.iterdir()
    )


def resolve_evaluation_cine_location_root(cine_patient_dir):
    sa_dir = find_child_dir(cine_patient_dir, "SA")
    return sa_dir if sa_dir is not None else cine_patient_dir


def is_evaluation_patient_dir(path):
    cine_location_root = resolve_evaluation_cine_location_root(path)
    return bool(list_cine_location_dirs(cine_location_root))


def parse_class_dir_label(name):
    class_name = CLASS_NAME_ALIASES.get(str(name).strip().lower())
    if class_name is None:
        return "", -1
    return class_name, CLASS_TO_LABEL[class_name]


def resolve_labeled_lge_root(lge_root, class_dir_name, class_name):
    candidates = [class_dir_name, class_name]
    for candidate_name in candidates:
        candidate = find_child_dir(lge_root, candidate_name)
        if candidate is not None:
            return candidate
    return lge_root


def is_evaluation_root(path):
    if is_frontend_patient_dir(path):
        return False

    cine_root = find_child_dir(path, "Cine")
    lge_root = find_child_dir(path, "LGE")
    if cine_root is None or lge_root is None:
        return False

    for child in cine_root.iterdir():
        if not child.is_dir():
            continue

        if is_evaluation_patient_dir(child):
            return True

        class_name, _ = parse_class_dir_label(child.name)
        if not class_name:
            continue

        for patient_dir in child.iterdir():
            if patient_dir.is_dir() and is_evaluation_patient_dir(patient_dir):
                return True

    return False


def find_evaluation_root(data_path):
    if is_evaluation_root(data_path):
        return data_path

    for child in sorted(data_path.iterdir(), key=natural_sort_key):
        if child.is_dir() and is_evaluation_root(child):
            return child
    return None


def list_cine_location_dirs(cine_root):
    if cine_root is None or not cine_root.exists() or not cine_root.is_dir():
        return []
    return [
        child
        for child in sorted(
            cine_root.iterdir(),
            key=lambda item: regex_number_sort_key(LOCATION_DIR_RE, item),
        )
        if child.is_dir() and LOCATION_DIR_RE.match(child.name)
    ]


def list_cine_frame_files(location_dir):
    if location_dir is None or not location_dir.exists() or not location_dir.is_dir():
        return []
    return [
        child
        for child in sorted(
            location_dir.iterdir(),
            key=lambda item: regex_number_sort_key(FRAME_IMAGE_RE, item),
        )
        if child.is_file() and FRAME_IMAGE_RE.match(child.name)
    ]


def list_lge_location_files(lge_dir):
    if lge_dir is None or not lge_dir.exists() or not lge_dir.is_dir():
        return []
    return [
        child
        for child in sorted(
            lge_dir.iterdir(),
            key=lambda item: regex_number_sort_key(LGE_IMAGE_RE, item),
        )
        if child.is_file() and LGE_IMAGE_RE.match(child.name)
    ]


def parse_label(value):
    if value is None:
        return "", -1
    value = str(value).strip()
    class_name = CLASS_NAME_ALIASES.get(value.lower())
    if class_name is not None:
        return class_name, CLASS_TO_LABEL[class_name]
    if value in {"0", "1"}:
        label = int(value)
        return LABEL_TO_CLASS[label], label
    raise ValueError("label must be one of mace, mace_cine, no_mace, 0, 1")


def resolve_lge_dir(patient_dir, lge_root=None):
    if lge_root:
        root = Path(lge_root)
        candidates = [root / patient_dir.name, root]
        for candidate in candidates:
            if list_lge_location_files(candidate):
                return candidate

    lge_dir = find_child_dir(patient_dir, "LGE")
    if lge_dir is not None:
        return lge_dir

    return patient_dir / "LGE"


def collect_patients(data_path, lge_root=None, label=None, max_patients=None):
    data_path = Path(data_path)
    override_class, override_label = parse_label(label)

    if not data_path.exists():
        raise FileNotFoundError("data_path does not exist: {}".format(data_path))

    patient_dirs = []
    if is_frontend_patient_dir(data_path):
        patient_dirs.append(data_path)
    else:
        evaluation_root = find_evaluation_root(data_path)
        if evaluation_root is not None:
            return collect_evaluation_patients(
                evaluation_root,
                label=label,
                max_patients=max_patients,
            )

        for child in sorted(data_path.iterdir(), key=natural_sort_key):
            if child.is_dir() and is_frontend_patient_dir(child):
                patient_dirs.append(child)

    if max_patients is not None:
        patient_dirs = patient_dirs[:max_patients]

    patients = []
    for patient_dir in patient_dirs:
        cine_dir = resolve_cine_location_root(patient_dir)
        patients.append(
            PatientInfo(
                patient_id=patient_dir.name,
                cine_dir=cine_dir,
                lge_dir=resolve_lge_dir(patient_dir, lge_root),
                class_name=override_class,
                label=override_label,
            )
        )

    if not patients:
        raise RuntimeError(
            "No frontend-format patient folders were found under {}. Expected Patient/Cine[/SA]/Location_xx/Frame_xx.png".format(
                data_path
            )
        )
    return patients


def collect_evaluation_patients(data_path, label=None, max_patients=None):
    data_path = Path(data_path)
    override_class, override_label = parse_label(label)
    cine_root = find_child_dir(data_path, "Cine")
    lge_root = find_child_dir(data_path, "LGE")

    if cine_root is None or lge_root is None:
        raise RuntimeError(
            "Evaluation root must contain Cine and LGE folders: {}".format(data_path)
        )

    patients = []
    for child in sorted(cine_root.iterdir(), key=natural_sort_key):
        if not child.is_dir():
            continue

        if is_evaluation_patient_dir(child):
            cine_location_root = resolve_evaluation_cine_location_root(child)
            patients.append(
                PatientInfo(
                    patient_id=child.name,
                    cine_dir=cine_location_root,
                    lge_dir=lge_root / child.name,
                    class_name=override_class,
                    label=override_label,
                )
            )
            continue

        dir_class, dir_label = parse_class_dir_label(child.name)
        if not dir_class:
            continue

        lge_class_root = resolve_labeled_lge_root(lge_root, child.name, dir_class)
        for cine_patient_dir in sorted(child.iterdir(), key=natural_sort_key):
            if not cine_patient_dir.is_dir() or not is_evaluation_patient_dir(
                cine_patient_dir
            ):
                continue

            cine_location_root = resolve_evaluation_cine_location_root(cine_patient_dir)
            patients.append(
                PatientInfo(
                    patient_id=cine_patient_dir.name,
                    cine_dir=cine_location_root,
                    lge_dir=lge_class_root / cine_patient_dir.name,
                    class_name=override_class or dir_class,
                    label=override_label if override_label != -1 else dir_label,
                )
            )

    if max_patients is not None:
        patients = patients[:max_patients]

    if not patients:
        raise RuntimeError(
            "No evaluation-format patient folders were found under {}. Expected Final_test_data/Cine/Patient_xxx/SA/Location_xx/Frame_xx.png or Final_test_data/Cine/mace/Patient_xxx/SA/Location_xx/Frame_xx.png".format(
                data_path
            )
        )

    return patients


class TTSTInferenceDataset(Dataset):
    """Inference dataset for frontend-format patient folders."""

    def __init__(
        self,
        patients,
        img_size=224,
        cine_length=300,
        lge_length=12,
        frames_per_location=25,
    ):
        self.patients = patients
        self.cine_length = cine_length
        self.lge_length = lge_length
        self.frames_per_location = frames_per_location
        self.transform = transforms.Compose(
            [
                transforms.Resize((img_size, img_size)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
            ]
        )
        self.zero_lge = torch.zeros([lge_length, 3, img_size, img_size])

    def __len__(self):
        return len(self.patients)

    def __getitem__(self, index):
        patient = self.patients[index]
        cine = self.load_cine_sequence(patient.cine_dir)
        lge, has_lge = self.load_lge_sequence(patient.lge_dir)
        return {
            "cine": cine,
            "lge": lge,
            "label": patient.label,
            "patient_id": patient.patient_id,
            "class_name": patient.class_name,
            "cine_dir": str(patient.cine_dir),
            "lge_dir": str(patient.lge_dir),
            "has_lge": has_lge,
        }

    def load_cine_sequence(self, cine_root):
        sample_paths = []
        location_dirs = list_cine_location_dirs(cine_root)
        if not location_dirs:
            raise FileNotFoundError(
                "No Cine Location_xx folders found under {}".format(cine_root)
            )

        for location_dir in location_dirs:
            location_images = list_cine_frame_files(location_dir)
            sample_paths.extend(location_images[: self.frames_per_location])

        if not sample_paths:
            raise RuntimeError(
                "No Cine Frame_xx images found under {}".format(cine_root)
            )

        sample_paths = pad_or_truncate(sample_paths, self.cine_length)
        images = [self.transform(pil_loader(image_path)) for image_path in sample_paths]
        return torch.stack(images, dim=0)

    def load_lge_sequence(self, lge_dir):
        lge_paths = list_lge_location_files(lge_dir)
        if not lge_paths:
            return self.zero_lge.clone(), False

        lge_paths = pad_or_truncate(lge_paths, self.lge_length)
        images = [self.transform(pil_loader(image_path)) for image_path in lge_paths]
        return torch.stack(images, dim=0), True


def pad_or_truncate(items, target_length):
    if not items:
        return []
    if len(items) >= target_length:
        return items[:target_length]

    result = list(items)
    original_length = len(result)
    index = original_length
    while index < target_length:
        result.append(result[index % original_length])
        index += 1
    return result


def collate_patient_batch(batch):
    return {
        "cine": torch.stack([item["cine"] for item in batch], dim=0),
        "lge": torch.stack([item["lge"] for item in batch], dim=0),
        "label": torch.tensor([item["label"] for item in batch], dtype=torch.long),
        "patient_id": [item["patient_id"] for item in batch],
        "class_name": [item["class_name"] for item in batch],
        "cine_dir": [item["cine_dir"] for item in batch],
        "lge_dir": [item["lge_dir"] for item in batch],
        "has_lge": [item["has_lge"] for item in batch],
    }


def load_state_dict(model, checkpoint_path, device, strict=True):
    checkpoint = torch.load(checkpoint_path, map_location=device)
    state_dict = (
        checkpoint["model"]
        if isinstance(checkpoint, dict) and "model" in checkpoint
        else checkpoint
    )

    if any(key.startswith("module.") for key in state_dict.keys()):
        state_dict = {
            key.replace("module.", "", 1): value for key, value in state_dict.items()
        }

    missing, unexpected = model.load_state_dict(state_dict, strict=strict)
    if missing:
        logger.warning("Missing keys while loading %s: %s", checkpoint_path, missing)
    if unexpected:
        logger.warning(
            "Unexpected keys while loading %s: %s", checkpoint_path, unexpected
        )


def resolve_device(device=None):
    if isinstance(device, torch.device):
        return device
    if device:
        return torch.device(device)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def build_models(args):
    structure = vit.get_b16_config()
    with contextlib.redirect_stdout(io.StringIO()):
        cine_model = IEPV(structure, args.img_size, num_classes=2).to(args.device)
        lge_model = IEPV(structure, args.img_size, num_classes=2).to(args.device)

        sequence_config = CONFIGS["sequence"]
        sequence_model = DSFI(
            sequence_config, structure, num_classes=2, zero_head=True, vis=True
        ).to(args.device)

    load_state_dict(cine_model, args.cine_checkpoint, args.device, strict=False)
    load_state_dict(lge_model, args.lge_checkpoint, args.device, strict=False)
    load_state_dict(sequence_model, args.sequence_checkpoint, args.device, strict=True)

    cine_model.eval()
    lge_model.eval()
    sequence_model.eval()
    return cine_model, lge_model, sequence_model


def infer_batch(args, batch, cine_model, lge_model, sequence_model):
    cine_images = batch["cine"].to(args.device, non_blocking=True)
    lge_images = batch["lge"].to(args.device, non_blocking=True)
    missing_lge = lge_images.flatten(start_dim=1).abs().sum(dim=1).eq(0)

    with torch.no_grad():
        cine_features = []
        for index in range(cine_images.shape[1]):
            _, feature = cine_model(cine_images[:, index, :, :, :], test_mode=True)
            cine_features.append(feature)
        cine_features = torch.stack(cine_features, dim=1)

        lge_features = []
        for index in range(lge_images.shape[1]):
            _, feature = lge_model(lge_images[:, index, :, :, :], test_mode=True)
            lge_features.append(feature)
        lge_features = torch.stack(lge_features, dim=1)

        if missing_lge.any():
            lge_features[missing_lge] = torch.zeros_like(lge_features[missing_lge])

        logits = sequence_model(cine_features, lge_features)[0]
        probabilities = torch.softmax(logits, dim=-1)

    return logits.detach().cpu(), probabilities.detach().cpu()


def format_result_rows(batch, logits, probabilities):
    rows = []
    for index, patient_id in enumerate(batch["patient_id"]):
        prob_mace = float(probabilities[index, 0])
        prob_no_mace = float(probabilities[index, 1])
        pred_label = int(torch.argmax(probabilities[index]).item())
        true_label = int(batch["label"][index].item())
        rows.append(
            {
                "patient_id": patient_id,
                "pred_label": pred_label,
                "pred_class": LABEL_TO_CLASS[pred_label],
                "prob_mace": prob_mace,
                "prob_no_mace": prob_no_mace,
                "logit_mace": float(logits[index, 0]),
                "logit_no_mace": float(logits[index, 1]),
                "true_label": "" if true_label < 0 else true_label,
                "true_class": batch["class_name"][index],
                "has_lge": batch["has_lge"][index],
                "cine_dir": batch["cine_dir"][index],
                "lge_dir": batch["lge_dir"][index],
            }
        )
    return rows


def compact_result(row):
    probability = max(row["prob_mace"], row["prob_no_mace"])
    return {
        "patient_id": row["patient_id"],
        "result": row["pred_class"],
        "pred_label": row["pred_label"],
        "probability": probability,
        "prob_mace": row["prob_mace"],
        "prob_no_mace": row["prob_no_mace"],
        "has_lge": row["has_lge"],
    }


def build_api_response(rows):
    results = [compact_result(row) for row in rows]
    response = {
        "count": len(results),
        "results": results,
    }
    if len(results) == 1:
        response.update(results[0])
    return response


def build_evaluation_results(rows):
    return [
        {
            "patient_index": row["patient_id"],
            "mace_score": row["prob_mace"],
        }
        for row in rows
    ]


def worksheet_cell_xml(cell_ref, value, is_number=False):
    if is_number:
        return '<c r="{cell_ref}"><v>{value}</v></c>'.format(
            cell_ref=cell_ref,
            value=value,
        )

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
                cells=worksheet_cell_xml(
                    "A{}".format(index), result["patient_index"]
                )
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
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="output_table" sheetId="1" r:id="rId1"/>
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
    results = build_evaluation_results(rows)
    xlsx_bytes = build_output_table_xlsx(results)
    return {
        "count": len(results),
        "results": results,
        "xlsxFilename": "output_table.xlsx",
        "xlsxBase64": base64.b64encode(xlsx_bytes).decode("ascii"),
    }


class TTSTPredictor:
    """Reusable inference service. The API layer should hold one instance."""

    def __init__(self, config=None):
        self.config = config or InferenceConfig()
        self.config.device = resolve_device(self.config.device)
        logger.info("Using device: %s", self.config.device)
        self.cine_model, self.lge_model, self.sequence_model = build_models(self.config)

    def predict_path(self, data_path, lge_root=None, label=None, max_patients=None):
        patients = collect_patients(
            data_path=data_path,
            lge_root=lge_root,
            label=label,
            max_patients=(
                max_patients if max_patients is not None else self.config.max_patients
            ),
        )
        logger.info("Found %d patient(s)", len(patients))
        return self.predict_patients(patients)

    def predict_patients(self, patients):
        dataset = TTSTInferenceDataset(
            patients,
            img_size=self.config.img_size,
            cine_length=self.config.cine_length,
            lge_length=self.config.lge_length,
            frames_per_location=self.config.frames_per_location,
        )
        loader = DataLoader(
            dataset,
            batch_size=self.config.batch_size,
            shuffle=False,
            num_workers=self.config.num_workers,
            pin_memory=self.config.device.type == "cuda",
            collate_fn=collate_patient_batch,
        )

        rows = []
        for batch in loader:
            logits, probabilities = infer_batch(
                self.config,
                batch,
                self.cine_model,
                self.lge_model,
                self.sequence_model,
            )
            rows.extend(format_result_rows(batch, logits, probabilities))
        return rows


def print_results(rows):
    print("\npatient_id\tpred_class\tprob_mace\tprob_no_mace\ttrue_class\thas_lge")
    for row in rows:
        print(
            "{patient_id}\t{pred_class}\t{prob_mace:.6f}\t{prob_no_mace:.6f}\t{true_class}\t{has_lge}".format(
                **row
            )
        )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run TTST inference on frontend-format patient folder(s)."
    )
    parser.add_argument(
        "--data_path",
        default=str(BASE_DIR / "test_input"),
        help="Single patient folder or a root folder containing patient folders.",
    )
    parser.add_argument(
        "--lge_root",
        default=None,
        help="Optional LGE override root. Usually not needed for frontend input.",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Optional label for unlabeled input: mace_cine/no_mace/0/1.",
    )
    parser.add_argument("--img_size", default=224, type=int)
    parser.add_argument("--cine_length", default=300, type=int)
    parser.add_argument("--lge_length", default=12, type=int)
    parser.add_argument("--frames_per_location", default=25, type=int)
    parser.add_argument("--batch_size", default=1, type=int)
    parser.add_argument("--num_workers", default=0, type=int)
    parser.add_argument("--max_patients", default=None, type=int)
    parser.add_argument(
        "--device",
        default=None,
        help="Example: cuda, cuda:0, or cpu. Defaults to CUDA when available.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        level=logging.INFO,
    )

    config = InferenceConfig(
        img_size=args.img_size,
        cine_length=args.cine_length,
        lge_length=args.lge_length,
        frames_per_location=args.frames_per_location,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        max_patients=args.max_patients,
        device=args.device,
    )
    predictor = TTSTPredictor(config)
    rows = predictor.predict_path(
        args.data_path, lge_root=args.lge_root, label=args.label
    )
    print_results(rows)


if __name__ == "__main__":
    main()
