import argparse
import re
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from ttst_backend_inference_demo import TTSTMacePredictor, natural_key


def patient_sort_key(path):
    return natural_key(Path(path).name)


def find_patients(final_test_data):
    final_test_data = Path(final_test_data)
    cine_root = final_test_data / "Cine"
    if not cine_root.exists():
        raise FileNotFoundError(f"Cine folder not found: {cine_root}")
    patients = sorted([path for path in cine_root.iterdir() if path.is_dir()], key=patient_sort_key)
    if not patients:
        raise RuntimeError(f"No patient folders found under: {cine_root}")
    return patients


def main():
    parser = argparse.ArgumentParser(
        description="Generate output_table.xlsx for task-1 acceptance data."
    )
    parser.add_argument(
        "--data-root",
        default="Final_test_data",
        help="Folder containing Cine/ and LGE/ subfolders.",
    )
    parser.add_argument(
        "--output-xlsx",
        default="output_table.xlsx",
        help="Required acceptance output xlsx path.",
    )
    parser.add_argument(
        "--output-csv",
        default=None,
        help="Optional CSV copy, e.g. output_table.csv.",
    )
    parser.add_argument(
        "--model-dir",
        default="PURE_SEQUENCE_RETRAIN_AUC823/checkpoints",
        help="Folder containing the selected 3 checkpoints.",
    )
    parser.add_argument("--device", default=None, help="cuda, cpu, or omit for auto")
    parser.add_argument("--image-batch-size", type=int, default=16)
    args = parser.parse_args()

    data_root = Path(args.data_root)
    lge_root = data_root / "LGE"
    model_dir = Path(args.model_dir)

    predictor = TTSTMacePredictor(
        cine_checkpoint=model_dir / "Cine_vitpre_last2_lossbal_b128_checkpoint.pth",
        lge_checkpoint=model_dir / "LGE_vitpre_last2_lossbal_b32_checkpoint.pth",
        sequence_checkpoint=model_dir / "TTST_seq_selected_lossbal_ga2_checkpoint.pth",
        device=args.device,
        image_batch_size=args.image_batch_size,
    )

    rows = []
    for cine_patient_dir in tqdm(find_patients(data_root), desc="Predicting patients"):
        patient_index = cine_patient_dir.name
        lge_patient_dir = lge_root / patient_index
        if not lge_patient_dir.exists():
            lge_patient_dir = None
        mace_score = predictor.predict_patient(cine_patient_dir, lge_patient_dir)
        rows.append({"patient_index": patient_index, "mace_score": mace_score})

    table = pd.DataFrame(rows, columns=["patient_index", "mace_score"])
    table.to_excel(args.output_xlsx, index=False)
    if args.output_csv:
        table.to_csv(args.output_csv, index=False)

    print(f"Wrote {args.output_xlsx}")
    if args.output_csv:
        print(f"Wrote {args.output_csv}")
    print(f"Patients: {len(table)}")
    print(f"Score range: {table['mace_score'].min():.6f} - {table['mace_score'].max():.6f}")


if __name__ == "__main__":
    main()
