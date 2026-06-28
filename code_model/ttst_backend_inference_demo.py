import argparse
import re
from pathlib import Path

import torch
from PIL import Image
from torchvision import transforms

from models.IEPV import IEPV
from models import vit
from models.modeling import CONFIGS, DSFI


IMAGE_EXTENSIONS = {".bmp", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}
DEFAULT_MODEL_DIR = Path("PURE_SEQUENCE_RETRAIN_AUC823/checkpoints")


def natural_key(path):
    text = str(path)
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def list_image_files(folder, recursive=False):
    folder = Path(folder)
    if not folder.exists():
        return []
    iterator = folder.rglob("*") if recursive else folder.iterdir()
    return sorted(
        [path for path in iterator if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS],
        key=natural_key,
    )


def load_rgb(path):
    with Image.open(path) as image:
        return image.convert("RGB")


class TTSTMacePredictor:
    """
    Backend-facing inference wrapper.

    Input:
      - cine_patient_dir: Final_test_data/Cine/Patient_001
      - lge_patient_dir: Final_test_data/LGE/Patient_001, optional

    Output:
      - risk_score = P(MACE) = softmax(sequence_logits)[1]
    """

    def __init__(
        self,
        cine_checkpoint=DEFAULT_MODEL_DIR / "Cine_vitpre_last2_lossbal_b128_checkpoint.pth",
        lge_checkpoint=DEFAULT_MODEL_DIR / "LGE_vitpre_last2_lossbal_b32_checkpoint.pth",
        sequence_checkpoint=DEFAULT_MODEL_DIR / "TTST_seq_selected_lossbal_ga2_checkpoint.pth",
        device=None,
        image_batch_size=16,
    ):
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.image_batch_size = int(image_batch_size)
        self.transform = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
            ]
        )

        structure = vit.get_b16_config()
        self.cine_model = self._load_image_model(structure, cine_checkpoint)
        self.lge_model = self._load_image_model(structure, lge_checkpoint)
        self.sequence_model = self._load_sequence_model(structure, sequence_checkpoint)

    def _load_image_model(self, structure, checkpoint_path):
        model = IEPV(structure, img_size=224, num_classes=2, use_mask=False)
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        model.load_state_dict(checkpoint["model"], strict=False)
        model.to(self.device)
        model.eval()
        return model

    def _load_sequence_model(self, structure, checkpoint_path):
        model = DSFI(CONFIGS["sequence"], structure, num_classes=2, zero_head=True, vis=True)
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        model.load_state_dict(checkpoint["model"], strict=False)
        model.to(self.device)
        model.eval()
        return model

    def _load_cine_tensor(self, cine_patient_dir):
        cine_patient_dir = Path(cine_patient_dir)
        sa_dir = cine_patient_dir / "SA"
        if not sa_dir.exists():
            raise FileNotFoundError(f"Cine SA folder not found: {sa_dir}")

        frame_paths = []
        for location_dir in sorted([p for p in sa_dir.iterdir() if p.is_dir()], key=natural_key):
            # Match training preprocessing: use sorted frames, at most 25 per location.
            frame_paths.extend(list_image_files(location_dir)[:25])

        if not frame_paths:
            raise RuntimeError(f"No cine frames found under: {sa_dir}")

        frame_paths = self._pad_or_truncate(frame_paths, target_length=300)
        frames = [self.transform(load_rgb(path)) for path in frame_paths]
        return torch.stack(frames, dim=0)

    def _load_lge_tensor(self, lge_patient_dir):
        if lge_patient_dir is None:
            return torch.zeros(12, 3, 224, 224), False

        lge_patient_dir = Path(lge_patient_dir)
        image_paths = list_image_files(lge_patient_dir, recursive=False)
        if not image_paths:
            image_paths = list_image_files(lge_patient_dir, recursive=True)
        if not image_paths:
            return torch.zeros(12, 3, 224, 224), False

        image_paths = self._pad_or_truncate(image_paths, target_length=12)
        images = [self.transform(load_rgb(path)) for path in image_paths]
        return torch.stack(images, dim=0), True

    @staticmethod
    def _pad_or_truncate(items, target_length):
        items = list(items)
        if len(items) >= target_length:
            return items[:target_length]
        original_length = len(items)
        index = original_length
        while len(items) < target_length:
            items.append(items[index % original_length])
            index += 1
        return items

    def _extract_features(self, model, image_tensor):
        features = []
        image_tensor = image_tensor.to(self.device)
        for start in range(0, image_tensor.shape[0], self.image_batch_size):
            chunk = image_tensor[start : start + self.image_batch_size]
            _, feature = model(chunk, mask=None, test_mode=True)
            features.append(feature)
        return torch.cat(features, dim=0).unsqueeze(0)

    @torch.no_grad()
    def predict_patient(self, cine_patient_dir, lge_patient_dir=None):
        cine_tensor = self._load_cine_tensor(cine_patient_dir)
        lge_tensor, has_lge = self._load_lge_tensor(lge_patient_dir)

        cine_features = self._extract_features(self.cine_model, cine_tensor)
        if has_lge:
            lge_features = self._extract_features(self.lge_model, lge_tensor)
        else:
            lge_features = cine_features.new_zeros(
                (1, 12, cine_features.shape[2], cine_features.shape[3])
            )

        logits = self.sequence_model(cine_features, lge_features)[0]
        probability = torch.softmax(logits, dim=1)[0, 1].item()
        return float(probability)


def main():
    parser = argparse.ArgumentParser(description="Single-patient TTST MACE inference demo.")
    parser.add_argument("--cine-patient-dir", required=True, help="Example: Final_test_data/Cine/Patient_001")
    parser.add_argument("--lge-patient-dir", default=None, help="Example: Final_test_data/LGE/Patient_001")
    parser.add_argument("--model-dir", default=str(DEFAULT_MODEL_DIR))
    parser.add_argument("--device", default=None, help="cuda, cpu, or omit for auto")
    parser.add_argument("--image-batch-size", type=int, default=16)
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    predictor = TTSTMacePredictor(
        cine_checkpoint=model_dir / "Cine_vitpre_last2_lossbal_b128_checkpoint.pth",
        lge_checkpoint=model_dir / "LGE_vitpre_last2_lossbal_b32_checkpoint.pth",
        sequence_checkpoint=model_dir / "TTST_seq_selected_lossbal_ga2_checkpoint.pth",
        device=args.device,
        image_batch_size=args.image_batch_size,
    )
    score = predictor.predict_patient(args.cine_patient_dir, args.lge_patient_dir)
    print(f"mace_score={score:.10f}")


if __name__ == "__main__":
    main()
