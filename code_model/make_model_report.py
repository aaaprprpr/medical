import argparse
import csv
import html
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

from test_sequence import setup_img, model_sequence_setup
from util.data_utils import get_loader


EVENT_PREFIX = "events.out.tfevents"


def load_image_model(args, checkpoint_path):
    args, model, structure = setup_img(args)
    checkpoint = torch.load(checkpoint_path, map_location=args.device)
    model.load_state_dict(checkpoint["model"], strict=False)
    model.eval()
    return args, model, structure


def load_sequence_model(args, structure, checkpoint_path):
    model = model_sequence_setup(args, structure)
    checkpoint = torch.load(checkpoint_path, map_location=args.device)
    model.load_state_dict(checkpoint["model"])
    model.eval()
    return model


def softmax_numpy(logits):
    logits = logits - np.max(logits, axis=1, keepdims=True)
    exp_logits = np.exp(logits)
    return exp_logits / exp_logits.sum(axis=1, keepdims=True)


def clean_patient_name(patient_key):
    for prefix in ("mace_cine_", "no_mace_"):
        if patient_key.startswith(prefix):
            return patient_key[len(prefix):]
    return patient_key


def collect_predictions(args):
    args.eval_batch_size = 1
    args.train_batch_size = max(1, int(args.train_batch_size))
    args, cine_model, structure = load_image_model(args, args.cine_checkpoint)
    args, lge_model, structure = load_image_model(args, args.lge_checkpoint)
    sequence_model = load_sequence_model(args, structure, args.sequence_checkpoint)

    _, test_loader = get_loader(args)
    rows = []

    with torch.no_grad():
        for index, batch in enumerate(test_loader):
            batch = tuple(t.to(args.device) for t in batch)
            if args.use_mask:
                cine_images, cine_masks, lge_images, lge_masks, target = batch
            else:
                cine_images, lge_images, target = batch

            cine_features = []
            for frame_index in range(cine_images.shape[1]):
                frame = cine_images[:, frame_index, :, :, :]
                frame_mask = cine_masks[:, frame_index, :, :, :] if args.use_mask else None
                _, feature = cine_model(frame, mask=frame_mask, test_mode=True)
                cine_features.append(feature)
            cine_features = torch.stack(cine_features, dim=1)

            lge_is_zero = list(torch.equal(item, torch.zeros_like(item)) for item in torch.split(lge_images, 1))
            lge_features = []
            for frame_index in range(lge_images.shape[1]):
                frame = lge_images[:, frame_index, :, :, :]
                frame_mask = lge_masks[:, frame_index, :, :, :] if args.use_mask else None
                _, feature = lge_model(frame, mask=frame_mask, test_mode=True)
                lge_features.append(feature)
            lge_features = torch.stack(lge_features, dim=1)

            lge_feature_list = list(torch.split(lge_features, 1))
            for feature_index, is_zero in enumerate(lge_is_zero):
                if is_zero:
                    lge_feature_list[feature_index] = torch.zeros_like(lge_feature_list[feature_index])
            lge_features = torch.cat(lge_feature_list, dim=0)

            logits = sequence_model(cine_features, lge_features)[0]
            logits_np = logits.detach().cpu().numpy()
            prob_np = softmax_numpy(logits_np)
            raw_label = int(target.detach().cpu().numpy()[0])
            mace_label = raw_label
            patient_key = test_loader.dataset.getitem_index_key[index]

            rows.append(
                {
                    "patient": clean_patient_name(patient_key),
                    "patient_key": patient_key,
                    "true_label": mace_label,
                    "true_class": "mace" if mace_label == 1 else "no_mace",
                    "risk_score": float(prob_np[0, 1]),
                    "logit_margin": float(logits_np[0, 1] - logits_np[0, 0]),
                    "logit_mace": float(logits_np[0, 1]),
                    "logit_no_mace": float(logits_np[0, 0]),
                    "has_lge": int(not any(lge_is_zero)),
                }
            )

    return rows


def labels_and_scores(rows):
    labels = np.asarray([row["true_label"] for row in rows], dtype=np.int64)
    scores = np.asarray([row["risk_score"] for row in rows], dtype=np.float64)
    margins = np.asarray([row["logit_margin"] for row in rows], dtype=np.float64)
    return labels, scores, margins


def threshold_metrics(labels, scores, threshold):
    preds = (scores >= threshold).astype(np.int64)
    tn, fp, fn, tp = confusion_matrix(labels, preds, labels=[0, 1]).ravel()
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    sensitivity = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(labels, preds)),
        "precision": float(precision_score(labels, preds, zero_division=0)),
        "recall": float(recall_score(labels, preds, zero_division=0)),
        "specificity": float(specificity),
        "f1": float(f1_score(labels, preds, zero_division=0)),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def find_best_thresholds(labels, scores):
    candidates = sorted(set(float(score) for score in scores))
    eps = 1e-12
    thresholds = [candidates[0] - eps]
    thresholds.extend((left + right) / 2.0 for left, right in zip(candidates[:-1], candidates[1:]))
    thresholds.append(candidates[-1] + eps)
    all_metrics = [threshold_metrics(labels, scores, threshold) for threshold in thresholds]
    best_accuracy = max(all_metrics, key=lambda item: (item["accuracy"], item["f1"], item["recall"]))
    best_youden = max(all_metrics, key=lambda item: (item["recall"] + item["specificity"], item["accuracy"]))
    return all_metrics, best_accuracy, best_youden


def compute_summary(rows):
    labels, scores, margins = labels_and_scores(rows)
    auc = roc_auc_score(labels, scores)
    ap = average_precision_score(labels, scores)
    default = threshold_metrics(labels, scores, 0.5)
    all_threshold_metrics, best_accuracy, best_youden = find_best_thresholds(labels, scores)

    summary = {
        "n_patients": int(len(rows)),
        "n_mace": int(labels.sum()),
        "n_no_mace": int((labels == 0).sum()),
        "auc": float(auc),
        "average_precision": float(ap),
        "brier_score": float(brier_score_loss(labels, scores)),
        "log_loss": float(log_loss(labels, np.clip(scores, 1e-7, 1 - 1e-7), labels=[0, 1])),
        "default_threshold": default,
        "best_accuracy_threshold": best_accuracy,
        "best_youden_threshold": best_youden,
        "score_min": float(scores.min()),
        "score_max": float(scores.max()),
        "score_mean": float(scores.mean()),
        "margin_min": float(margins.min()),
        "margin_max": float(margins.max()),
    }
    return summary, all_threshold_metrics


def write_csvs(rows, all_threshold_metrics, output_dir):
    detailed_path = output_dir / "predictions_with_labels.csv"
    with detailed_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "patient",
                "patient_key",
                "true_label",
                "true_class",
                "risk_score",
                "logit_margin",
                "logit_mace",
                "logit_no_mace",
                "has_lge",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    submission_path = output_dir / "teacher_submission.csv"
    with submission_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["patient", "risk_score"])
        writer.writeheader()
        for row in rows:
            writer.writerow({"patient": row["patient"], "risk_score": row["risk_score"]})

    threshold_path = output_dir / "threshold_metrics.csv"
    with threshold_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_threshold_metrics[0].keys()))
        writer.writeheader()
        writer.writerows(all_threshold_metrics)

    return detailed_path, submission_path, threshold_path


def find_event_files(log_dirs):
    event_files = []
    for raw_path in log_dirs:
        path = Path(raw_path)
        if path.is_file() and path.name.startswith(EVENT_PREFIX):
            event_files.append(path)
        elif path.is_dir():
            event_files.extend(path.rglob(f"{EVENT_PREFIX}*"))
    return sorted(event_files, key=lambda item: (str(item.parent), item.stat().st_size, item.name))


def read_event_scalars(log_dirs):
    runs = []
    for event_file in find_event_files(log_dirs):
        if event_file.stat().st_size < 100:
            continue
        accumulator = EventAccumulator(str(event_file), size_guidance={"scalars": 100000})
        try:
            accumulator.Reload()
        except Exception:
            continue
        tags = accumulator.Tags().get("scalars", [])
        if not tags:
            continue
        scalars = {}
        for tag in tags:
            values = accumulator.Scalars(tag)
            scalars[tag] = [(item.step, item.value) for item in values]
        runs.append({"name": event_file.parent.name, "event_file": str(event_file), "scalars": scalars})
    return runs


def plot_training_curves(runs, output_dir):
    if not runs:
        return None
    preferred_tags = ["train/loss", "test/AUC", "test/accuracy", "train/lr"]
    available_tags = []
    for tag in preferred_tags:
        if any(tag in run["scalars"] for run in runs):
            available_tags.append(tag)
    if not available_tags:
        return None

    fig, axes = plt.subplots(len(available_tags), 1, figsize=(10, 3.2 * len(available_tags)), constrained_layout=True)
    if len(available_tags) == 1:
        axes = [axes]
    for axis, tag in zip(axes, available_tags):
        for run in runs:
            if tag not in run["scalars"]:
                continue
            points = run["scalars"][tag]
            steps = [point[0] for point in points]
            values = [point[1] for point in points]
            axis.plot(steps, values, marker="o", linewidth=1.7, markersize=3, label=run["name"])
        axis.set_title(tag)
        axis.set_xlabel("step")
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8)
    path = output_dir / "training_curves.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_roc_pr(labels, scores, output_dir):
    fpr, tpr, _ = roc_curve(labels, scores)
    precision, recall, _ = precision_recall_curve(labels, scores)
    auc = roc_auc_score(labels, scores)
    ap = average_precision_score(labels, scores)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    axes[0].plot(fpr, tpr, linewidth=2.2, label=f"AUC = {auc:.3f}")
    axes[0].plot([0, 1], [0, 1], linestyle="--", color="#999999", linewidth=1)
    axes[0].set_title("ROC Curve")
    axes[0].set_xlabel("False Positive Rate")
    axes[0].set_ylabel("True Positive Rate")
    axes[0].grid(alpha=0.25)
    axes[0].legend()

    axes[1].plot(recall, precision, linewidth=2.2, color="#2a9d8f", label=f"AP = {ap:.3f}")
    axes[1].set_title("Precision-Recall Curve")
    axes[1].set_xlabel("Recall")
    axes[1].set_ylabel("Precision")
    axes[1].set_ylim(0, 1.05)
    axes[1].grid(alpha=0.25)
    axes[1].legend()

    path = output_dir / "roc_pr_curves.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_threshold_sweep(all_threshold_metrics, output_dir):
    thresholds = [item["threshold"] for item in all_threshold_metrics]
    fig, axis = plt.subplots(figsize=(9, 4.8), constrained_layout=True)
    for metric, color in [("accuracy", "#1f77b4"), ("recall", "#d62728"), ("specificity", "#2ca02c"), ("f1", "#9467bd")]:
        axis.plot(thresholds, [item[metric] for item in all_threshold_metrics], marker="o", linewidth=1.8, label=metric, color=color)
    axis.set_title("Threshold Sweep")
    axis.set_xlabel("risk_score threshold")
    axis.set_ylabel("metric")
    axis.set_ylim(-0.02, 1.02)
    axis.grid(alpha=0.25)
    axis.legend()
    path = output_dir / "threshold_sweep.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_confusion_matrices(labels, scores, summary, output_dir):
    configs = [("Default threshold 0.5", summary["default_threshold"]), ("Best accuracy threshold", summary["best_accuracy_threshold"])]
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.2), constrained_layout=True)
    for axis, (title, metric) in zip(axes, configs):
        preds = (scores >= metric["threshold"]).astype(np.int64)
        cm = confusion_matrix(labels, preds, labels=[0, 1])
        axis.imshow(cm, cmap="Blues")
        axis.set_title(f"{title}\nthreshold={metric['threshold']:.6f}, acc={metric['accuracy']:.3f}")
        axis.set_xticks([0, 1], labels=["pred no_mace", "pred mace"])
        axis.set_yticks([0, 1], labels=["true no_mace", "true mace"])
        for row in range(2):
            for col in range(2):
                axis.text(col, row, str(cm[row, col]), ha="center", va="center", fontsize=14)
    path = output_dir / "confusion_matrices.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_scores(rows, output_dir):
    labels, scores, _ = labels_and_scores(rows)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    axes[0].hist(scores[labels == 1], bins=8, alpha=0.75, label="mace", color="#d62728")
    axes[0].hist(scores[labels == 0], bins=8, alpha=0.75, label="no_mace", color="#1f77b4")
    axes[0].set_title("Risk Score Distribution")
    axes[0].set_xlabel("risk_score = P(MACE)")
    axes[0].set_ylabel("count")
    axes[0].legend()
    axes[0].grid(alpha=0.2)

    ordered = sorted(rows, key=lambda row: row["risk_score"])
    y = np.arange(len(ordered))
    colors = ["#d62728" if row["true_label"] == 1 else "#1f77b4" for row in ordered]
    axes[1].barh(y, [row["risk_score"] for row in ordered], color=colors)
    axes[1].set_yticks(y, labels=[row["patient"] for row in ordered], fontsize=8)
    axes[1].set_title("Patient Risk Ranking")
    axes[1].set_xlabel("risk_score = P(MACE)")
    axes[1].grid(axis="x", alpha=0.2)

    path = output_dir / "score_distribution_and_ranking.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def write_summary_json(summary, output_dir):
    path = output_dir / "metrics_summary.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    return path


def write_html_report(output_dir, summary, image_paths, csv_paths):
    def rel(path):
        return html.escape(Path(path).name)

    rows = [
        ("Patients", summary["n_patients"]),
        ("MACE / no_mace", f"{summary['n_mace']} / {summary['n_no_mace']}"),
        ("AUC", f"{summary['auc']:.5f}"),
        ("Average precision", f"{summary['average_precision']:.5f}"),
        ("Default threshold accuracy", f"{summary['default_threshold']['accuracy']:.5f} @ 0.5"),
        (
            "Best threshold accuracy",
            f"{summary['best_accuracy_threshold']['accuracy']:.5f} @ {summary['best_accuracy_threshold']['threshold']:.8f}",
        ),
        (
            "Youden threshold",
            f"{summary['best_youden_threshold']['threshold']:.8f}",
        ),
        ("Brier score", f"{summary['brier_score']:.5f}"),
        ("Log loss", f"{summary['log_loss']:.5f}"),
    ]
    metric_rows = "\n".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k, v in rows)
    image_html = "\n".join(f"<section><img src='{rel(path)}' alt='{rel(path)}'></section>" for path in image_paths if path)
    csv_links = "\n".join(f"<li><a href='{rel(path)}'>{rel(path)}</a></li>" for path in csv_paths)

    content = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Model Evaluation Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 28px; color: #17202a; background: #f7f8fa; }}
    h1 {{ margin-bottom: 8px; }}
    table {{ border-collapse: collapse; background: white; margin: 16px 0 24px; min-width: 560px; }}
    th, td {{ border: 1px solid #d7dce2; padding: 8px 12px; text-align: left; }}
    th {{ background: #eef2f7; }}
    section {{ background: white; padding: 14px; margin: 18px 0; border: 1px solid #d7dce2; }}
    img {{ max-width: 100%; display: block; }}
    code {{ background: #eef2f7; padding: 2px 4px; }}
  </style>
</head>
<body>
  <h1>Model Evaluation Report</h1>
  <p><code>risk_score</code> 是 softmax 后的 MACE 风险分数，AUC 只依赖排序，不要求 0.5 是合理阈值。</p>
  <table>{metric_rows}</table>
  <h2>Files</h2>
  <ul>{csv_links}</ul>
  <h2>Figures</h2>
  {image_html}
</body>
</html>
"""
    path = output_dir / "index.html"
    path.write_text(content, encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser(description="Generate prediction CSVs and report figures for the TTST sequence model.")
    parser.add_argument("--cine-checkpoint", required=True)
    parser.add_argument("--lge-checkpoint", required=True)
    parser.add_argument("--sequence-checkpoint", required=True)
    parser.add_argument("--sequence-feature-source", choices=["selected", "encoded"], default="selected")
    parser.add_argument("--train-data-folder", default=r"Dataset\train")
    parser.add_argument("--test-data-folder", default=r"Dataset\test")
    parser.add_argument("--img-size", type=int, default=224)
    parser.add_argument("--train-batch-size", type=int, default=1)
    parser.add_argument("--eval-batch-size", type=int, default=1)
    parser.add_argument("--log-dir", action="append", default=[])
    parser.add_argument("--output-dir", default=r"reports\latest")
    args = parser.parse_args()

    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", level=logging.WARNING)
    args.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    args.use_mask = False

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = collect_predictions(SimpleNamespace(**vars(args)))
    summary, all_threshold_metrics = compute_summary(rows)
    labels, scores, _ = labels_and_scores(rows)

    detailed_path, submission_path, threshold_path = write_csvs(rows, all_threshold_metrics, output_dir)
    summary_path = write_summary_json(summary, output_dir)
    runs = read_event_scalars(args.log_dir)

    image_paths = [
        plot_training_curves(runs, output_dir),
        plot_roc_pr(labels, scores, output_dir),
        plot_threshold_sweep(all_threshold_metrics, output_dir),
        plot_confusion_matrices(labels, scores, summary, output_dir),
        plot_scores(rows, output_dir),
    ]
    html_path = write_html_report(
        output_dir,
        summary,
        image_paths,
        [detailed_path, submission_path, threshold_path, summary_path],
    )

    print(f"Report: {html_path}")
    print(f"Teacher submission: {submission_path}")
    print(f"Detailed predictions: {detailed_path}")
    print(f"AUC: {summary['auc']:.5f}")
    print(f"Accuracy @ 0.5: {summary['default_threshold']['accuracy']:.5f}")
    print(
        "Best accuracy threshold: "
        f"{summary['best_accuracy_threshold']['threshold']:.8f}, "
        f"accuracy={summary['best_accuracy_threshold']['accuracy']:.5f}, "
        f"recall={summary['best_accuracy_threshold']['recall']:.5f}, "
        f"specificity={summary['best_accuracy_threshold']['specificity']:.5f}"
    )
    print(
        "Best Youden threshold: "
        f"{summary['best_youden_threshold']['threshold']:.8f}, "
        f"accuracy={summary['best_youden_threshold']['accuracy']:.5f}, "
        f"recall={summary['best_youden_threshold']['recall']:.5f}, "
        f"specificity={summary['best_youden_threshold']['specificity']:.5f}"
    )


if __name__ == "__main__":
    main()
