import argparse
import csv
import logging
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch
from sklearn.metrics import accuracy_score, roc_auc_score
from torchvision import transforms
from tqdm import tqdm

from test_sequence import setup_img
from util.data_utils import my_ImageFolder


def softmax_numpy(logits):
    logits = logits - np.max(logits, axis=1, keepdims=True)
    exp_logits = np.exp(logits)
    return exp_logits / exp_logits.sum(axis=1, keepdims=True)


def patient_from_path(path):
    parts = Path(path).parts
    for part in parts:
        if part.startswith("Patient_"):
            return part
    return Path(path).stem


def evaluate_checkpoint(name, checkpoint_path, root, batch_size, device, output_dir=None):
    args = SimpleNamespace(device=device)
    args, model, _ = setup_img(args)
    checkpoint = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(checkpoint["model"], strict=False)
    model.eval()

    transform = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
        ]
    )
    dataset = my_ImageFolder(root=root, transform=transform, use_mask=False)
    loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0, pin_memory=False)

    rows = []
    with torch.no_grad():
        for batch_index, (images, targets) in enumerate(tqdm(loader, desc=f"{name}:{root}", leave=False)):
            images = images.to(device)
            logits, _ = model(images, test_mode=True)
            logits = logits.detach().cpu().numpy()
            probs = softmax_numpy(logits)
            targets = targets.numpy()
            for item_index, raw_label in enumerate(targets):
                sample_index = batch_index * batch_size + item_index
                path, _ = dataset.samples[sample_index]
                mace_label = int(raw_label)
                rows.append(
                    {
                        "model": name,
                        "root": root,
                        "path": path,
                        "patient": patient_from_path(path),
                        "true_label": mace_label,
                        "risk_score": float(probs[item_index, 1]),
                        "margin": float(logits[item_index, 1] - logits[item_index, 0]),
                    }
                )

    labels = np.asarray([row["true_label"] for row in rows])
    scores = np.asarray([row["risk_score"] for row in rows])
    margins = np.asarray([row["margin"] for row in rows])
    image_auc = roc_auc_score(labels, scores)
    image_margin_auc = roc_auc_score(labels, margins)
    image_acc_05 = accuracy_score(labels, (scores >= 0.5).astype(int))

    patient_rows = []
    for patient in sorted({row["patient"] for row in rows}):
        items = [row for row in rows if row["patient"] == patient]
        patient_rows.append(
            {
                "model": name,
                "root": root,
                "patient": patient,
                "true_label": items[0]["true_label"],
                "risk_score_mean": float(np.mean([item["risk_score"] for item in items])),
                "risk_score_median": float(np.median([item["risk_score"] for item in items])),
                "margin_mean": float(np.mean([item["margin"] for item in items])),
                "n_images": len(items),
            }
        )

    patient_labels = np.asarray([row["true_label"] for row in patient_rows])
    patient_scores = np.asarray([row["risk_score_mean"] for row in patient_rows])
    patient_margins = np.asarray([row["margin_mean"] for row in patient_rows])
    patient_auc = roc_auc_score(patient_labels, patient_scores)
    patient_margin_auc = roc_auc_score(patient_labels, patient_margins)

    summary = {
        "model": name,
        "root": root,
        "n_images": len(rows),
        "n_patients": len(patient_rows),
        "n_mace_images": int(labels.sum()),
        "n_mace_patients": int(patient_labels.sum()),
        "image_auc": float(image_auc),
        "image_margin_auc": float(image_margin_auc),
        "image_acc_05": float(image_acc_05),
        "patient_mean_auc": float(patient_auc),
        "patient_margin_auc": float(patient_margin_auc),
    }

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"{name}_{Path(root).name}".replace("\\", "_").replace("/", "_")
        image_path = output_dir / f"{safe_name}_image_scores.csv"
        patient_path = output_dir / f"{safe_name}_patient_scores.csv"
        with image_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        with patient_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(patient_rows[0].keys()))
            writer.writeheader()
            writer.writerows(patient_rows)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", action="append", nargs=2, metavar=("NAME", "PATH"), required=True)
    parser.add_argument("--root", action="append", required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()

    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", level=logging.WARNING)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    summaries = []
    for name, checkpoint_path in args.checkpoint:
        for root in args.root:
            summaries.append(evaluate_checkpoint(name, checkpoint_path, root, args.batch_size, device, args.output_dir))

    print("model,root,n_images,n_patients,image_auc,image_margin_auc,image_acc_05,patient_mean_auc,patient_margin_auc")
    for item in summaries:
        print(
            "{model},{root},{n_images},{n_patients},{image_auc:.6f},{image_margin_auc:.6f},"
            "{image_acc_05:.6f},{patient_mean_auc:.6f},{patient_margin_auc:.6f}".format(**item)
        )


if __name__ == "__main__":
    main()
