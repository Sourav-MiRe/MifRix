import argparse
import os
import re
import warnings
from glob import glob
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ._paths import tech_resources_root


def align_to_train_schema(X_val, train_columns, flag_cols=("Is16s", "IsIndustrialized")):
    flag_cols = set(flag_cols)
    missing = [c for c in train_columns if c not in X_val.columns]
    missing_set = set(missing)
    missing_only_flags = missing_set and (missing_set <= flag_cols)

    if missing_only_flags:
        warnings.warn(
            f"Missing expected flag column(s) in validation data: {sorted(missing_set)}. They will be filled with 0."
        )

    return X_val.reindex(columns=train_columns, fill_value=0.0)


def sanitize_feature_names(columns):
    sanitized = []
    used = {}
    for idx, col in enumerate(columns):
        base = re.sub(r"[^A-Za-z0-9_]", "_", str(col)).strip("_")
        if not base:
            base = f"feature_{idx}"
        count = used.get(base, 0)
        new_name = base if count == 0 else f"{base}_{count}"
        used[base] = count + 1
        sanitized.append(new_name)
    return sanitized


def read_csv_to_pandas(path, index_col=0):
    return pd.read_csv(path, index_col=index_col)


def load_latest_median_subset(results_dir):
    candidates = glob(os.path.join(results_dir, "*_median.pkl"))
    if not candidates:
        return None, None
    latest = max(candidates, key=os.path.getmtime)
    subset = joblib.load(latest)
    return tuple(subset), latest


def load_individual_models(model_dir, subset):
    models = {}
    missing = []
    failed = []
    for model_name in subset:
        path = os.path.join(model_dir, f"{model_name}.pkl")
        if not os.path.exists(path):
            missing.append(model_name)
            continue
        try:
            models[model_name] = joblib.load(path)
        except Exception as exc:
            failed.append({"model": model_name, "path": path, "error": repr(exc)})
    return models, missing, failed


def median_predict_proba(models, X_aligned):
    prob_predictions = []
    for model in models.values():
        if hasattr(model, "predict_proba"):
            prob_predictions.append(model.predict_proba(X_aligned)[:, 1])
        else:
            prob_predictions.append(model.predict(X_aligned).astype(float))
    return np.median(np.asarray(prob_predictions), axis=0)


def get_train_columns_from_train_csv(train_splits_dir, class_name, train_template):
    train_path = os.path.join(train_splits_dir, train_template.format(disease=class_name))
    if not os.path.exists(train_path):
        raise FileNotFoundError(f"Training schema file not found: {train_path}")

    train_df = read_csv_to_pandas(train_path, index_col=0)
    drop_cols = [c for c in ["study_name", "diseaseCat", "Label"] if c in train_df.columns]
    X_train = train_df.drop(columns=drop_cols, errors="ignore")
    X_train.columns = sanitize_feature_names(X_train.columns)
    return list(X_train.columns), train_path


def _normalize_cols(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _get_optional_meta_cols(md_aligned):
    cols = {str(c).strip().lower(): c for c in md_aligned.columns}
    disease_keys = ["diseasecat", "disease_cat", "disease", "diseasecategory"]
    study_keys = ["study_name", "studyname", "study", "studyid"]
    disease_col = next((cols[k] for k in disease_keys if k in cols), None)
    study_col = next((cols[k] for k in study_keys if k in cols), None)
    study_s = md_aligned[study_col] if study_col is not None else None
    disease_s = md_aligned[disease_col] if disease_col is not None else None
    return study_s, disease_s


def add_flags_from_metadata(X_val, md, seq_col="Sequence Type", cohort_col="Cohort Type"):
    X_val = X_val.copy()
    X_val.index = X_val.index.astype(str)
    md = md.copy()
    md.index = md.index.astype(str)
    md_aligned = md.reindex(X_val.index)

    if md_aligned.isna().all(axis=1).any():
        missing_ids = md_aligned.index[md_aligned.isna().all(axis=1)].tolist()[:10]
        raise ValueError(f"Some validation sample IDs not found in metadata index: {missing_ids}")

    if seq_col not in md_aligned.columns:
        raise ValueError(f"Metadata missing required column: '{seq_col}'")
    if cohort_col not in md_aligned.columns:
        raise ValueError(f"Metadata missing required column: '{cohort_col}'")

    seq = md_aligned[seq_col].astype(str).str.strip().str.lower()
    X_val["Is16s"] = seq.str.contains("16").astype(float)
    cohort = md_aligned[cohort_col].astype(str).str.strip().str.lower()
    X_val["IsIndustrialized"] = (cohort == "industrialized").astype(float)
    return X_val, md_aligned


def score_validation_all_classes_with_metadata(
    *,
    tech: str,
    validation_csv_path,
    metadata_csv_path,
    output_path,
    models_root=None,
    train_splits_dir=None,
    train_template="Test_{disease}_selected.csv",
    drop_from_validation=("study_name", "diseaseCat", "Label"),
    seq_col="Sequence Type",
    cohort_col="Cohort Type",
    resource_dir=None,
):
    tech = tech.upper()
    resource_root = tech_resources_root(tech, resource_dir)
    models_root = str(Path(models_root)) if models_root else str(resource_root / "Models")
    train_splits_dir = str(Path(train_splits_dir)) if train_splits_dir else str(resource_root)

    val_raw = read_csv_to_pandas(validation_csv_path, index_col=0)
    val_raw.index = val_raw.index.astype(str)
    X_val = val_raw.drop(columns=[c for c in drop_from_validation if c in val_raw.columns], errors="ignore").copy()
    X_val.columns = sanitize_feature_names(X_val.columns)

    md = read_csv_to_pandas(metadata_csv_path, index_col=0)
    md = _normalize_cols(md)
    md.index = md.index.astype(str)
    X_val, md_aligned = add_flags_from_metadata(X_val, md, seq_col=seq_col, cohort_col=cohort_col)

    class_dirs = sorted(d for d in os.listdir(models_root) if os.path.isdir(os.path.join(models_root, d)))
    probs = pd.DataFrame(index=X_val.index)
    skipped = []

    for class_name in class_dirs:
        class_dir = os.path.join(models_root, class_name)
        results_dir = os.path.join(class_dir, "results")
        subset, _ = load_latest_median_subset(results_dir)
        if subset is None:
            skipped.append({"class": class_name, "reason": f"No *_median.pkl found in {results_dir}"})
            continue

        models, missing, failed = load_individual_models(class_dir, subset)
        if missing:
            skipped.append({"class": class_name, "reason": f"Missing model files: {missing}"})
            continue
        if failed and not models:
            skipped.append({"class": class_name, "reason": f"All models failed to load. Example: {failed[0]}"})
            continue
        if not models:
            skipped.append({"class": class_name, "reason": "No models loaded"})
            continue

        train_columns, _ = get_train_columns_from_train_csv(train_splits_dir, class_name, train_template)
        X_aligned = align_to_train_schema(X_val, train_columns)
        y_prob = median_predict_proba(models, X_aligned)

        if class_name.strip().lower() == "control":
            probs["GD_Probability"] = y_prob
        else:
            probs[class_name] = y_prob

    out = probs.copy()
    study_s, disease_s = _get_optional_meta_cols(md_aligned)
    if study_s is not None:
        out["study_name"] = study_s.values
    if disease_s is not None:
        out["diseaseCat"] = disease_s.values

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=True)
    return out, pd.DataFrame(skipped)


def _build_parser(default_tech: str):
    parser = argparse.ArgumentParser()
    parser.add_argument("--validation-csv", required=True)
    parser.add_argument("--metadata-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--models-root", default=None)
    parser.add_argument("--train-splits-dir", default=None)
    parser.add_argument("--resource-dir", default=None, help="Directory containing unpacked MifRix resources.")
    parser.add_argument("--tech", default=default_tech)
    return parser


def main_ap():
    args = _build_parser("AP").parse_args()
    score_validation_all_classes_with_metadata(
        tech=args.tech,
        validation_csv_path=args.validation_csv,
        metadata_csv_path=args.metadata_csv,
        output_path=args.output_csv,
        models_root=args.models_root,
        train_splits_dir=args.train_splits_dir,
        resource_dir=args.resource_dir,
    )
    print(f"Saved: {args.output_csv}")


def main_fp():
    args = _build_parser("FP").parse_args()
    score_validation_all_classes_with_metadata(
        tech=args.tech,
        validation_csv_path=args.validation_csv,
        metadata_csv_path=args.metadata_csv,
        output_path=args.output_csv,
        models_root=args.models_root,
        train_splits_dir=args.train_splits_dir,
        resource_dir=args.resource_dir,
    )
    print(f"Saved: {args.output_csv}")


def main():
    parser = _build_parser("AP")
    args = parser.parse_args()
    score_validation_all_classes_with_metadata(
        tech=args.tech,
        validation_csv_path=args.validation_csv,
        metadata_csv_path=args.metadata_csv,
        output_path=args.output_csv,
        models_root=args.models_root,
        train_splits_dir=args.train_splits_dir,
        resource_dir=args.resource_dir,
    )
    print(f"Saved: {args.output_csv}")


if __name__ == "__main__":
    main()
