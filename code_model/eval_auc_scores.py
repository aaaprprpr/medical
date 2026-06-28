import argparse
import logging
from types import SimpleNamespace

import numpy as np
import torch
from sklearn.metrics import roc_auc_score

from test_sequence import setup_img, model_sequence_setup
from util.data_utils import get_loader


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


def evaluate_run(run_name, cine_checkpoint, lge_checkpoint, sequence_checkpoint, base_args):
    args = SimpleNamespace(**vars(base_args))
    args, cine_model, structure = load_image_model(args, cine_checkpoint)
    args, lge_model, structure = load_image_model(args, lge_checkpoint)
    sequence_model = load_sequence_model(args, structure, sequence_checkpoint)

    _, test_loader = get_loader(args)
    names, labels, scores = [], [], []

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

            lge_features = []
            lge_is_zero = list(torch.equal(item, torch.zeros_like(item)) for item in torch.split(lge_images, 1))
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
            score = torch.softmax(logits, dim=1)[:, 1].detach().cpu().numpy()

            raw_label = target.detach().cpu().numpy()
            auc_label = raw_label

            patient_name = test_loader.dataset.getitem_index_key[index]
            names.append(patient_name)
            labels.append(auc_label[0])
            scores.append(score[0])

    labels = np.asarray(labels)
    scores = np.asarray(scores)
    auc = roc_auc_score(labels, scores)
    order = np.argsort(-scores)

    print(f"\n== {run_name} ==")
    print(f"AUC: {auc:.5f}")
    print("rank\tlabel\tscore\tpatient")
    for rank, idx in enumerate(order, 1):
        print(f"{rank}\t{int(labels[idx])}\t{scores[idx]:.6f}\t{names[idx]}")

    return {"name": run_name, "names": names, "labels": labels, "scores": scores, "auc": auc}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run",
        action="append",
        nargs=4,
        metavar=("NAME", "CINE_CKPT", "LGE_CKPT", "SEQ_CKPT"),
        required=True,
        help="Evaluate one run. Can be passed multiple times.",
    )
    parser.add_argument("--train_data_folder", default=r"Dataset\train")
    parser.add_argument("--test_data_folder", default=r"Dataset\test")
    parser.add_argument("--img_size", type=int, default=224)
    parser.add_argument("--train_batch_size", type=int, default=1)
    parser.add_argument("--eval_batch_size", type=int, default=1)
    args = parser.parse_args()

    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", level=logging.WARNING)
    args.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    args.use_mask = False

    results = [evaluate_run(*run, args) for run in args.run]
    if len(results) > 1:
        labels = results[0]["labels"]
        names = results[0]["names"]
        all_scores = np.stack([result["scores"] for result in results], axis=0)
        mean_scores = all_scores.mean(axis=0)
        auc = roc_auc_score(labels, mean_scores)
        order = np.argsort(-mean_scores)
        print("\n== mean_ensemble ==")
        print(f"AUC: {auc:.5f}")
        print("rank\tlabel\tscore\tpatient")
        for rank, idx in enumerate(order, 1):
            print(f"{rank}\t{int(labels[idx])}\t{mean_scores[idx]:.6f}\t{names[idx]}")


if __name__ == "__main__":
    main()
