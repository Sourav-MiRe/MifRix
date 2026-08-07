import json
import os
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from tqdm import tqdm

from ._paths import tech_shap_root


DROP_COLUMNS = ("study_name", "diseaseCat", "Label")
FLAG_COLUMNS = ("Is16s", "IsIndustrialized")


def sanitize_feature_names(cols):
    mapping = {}
    new_cols = []
    used = set()

    for c in cols:
        old = str(c)
        new = re.sub(r"[^A-Za-z0-9_]+", "_", old)
        if new == "":
            new = "feature"

        base = new
        k = 1
        while new in used:
            k += 1
            new = f"{base}{k}"

        used.add(new)
        mapping[old] = new
        new_cols.append(new)

    return new_cols, mapping


def sanitize_features_df(X: pd.DataFrame, expected_columns=None, fill_value=0.0):
    if not isinstance(X, pd.DataFrame):
        X = pd.DataFrame(X)

    X_out = X.copy()
    new_cols, _ = sanitize_feature_names(X_out.columns)
    X_out.columns = new_cols

    if expected_columns is not None:
        expected_columns = list(expected_columns)

        missing = [c for c in expected_columns if c not in X_out.columns]
        for c in missing:
            X_out[c] = 0.0

        extra = [c for c in X_out.columns if c not in expected_columns]
        if extra:
            X_out = X_out.drop(columns=extra)

        X_out = X_out.reindex(columns=expected_columns)

    X_out = X_out.replace([np.inf, -np.inf], np.nan)
    for c in X_out.columns:
        if not pd.api.types.is_numeric_dtype(X_out[c]):
            X_out[c] = pd.to_numeric(X_out[c], errors="coerce")

    X_out = X_out.fillna(fill_value).astype(np.float32)
    return X_out


def load_explainer(explainer_path: Path, meta_path: Path):
    explainer = joblib.load(explainer_path)
    with open(meta_path, "r") as f:
        meta = json.load(f)
    return explainer, meta


def shap_values_from_explainer(explainer, mode: str, X_eval: pd.DataFrame):
    if mode == "tree":
        out = explainer(X_eval, check_additivity=False)
        vals = out.values

        if isinstance(vals, list):
            vals = vals[1] if len(vals) > 1 else vals[0]
            return np.asarray(vals, dtype=np.float32)

        vals = np.asarray(vals)

        if vals.ndim == 3:
            k = vals.shape[2]
            class_idx = 1 if k > 1 else 0
            return np.asarray(vals[:, :, class_idx], dtype=np.float32)

        if vals.ndim == 2:
            return np.asarray(vals, dtype=np.float32)

        raise RuntimeError(f"Unexpected TreeExplainer SHAP shape: {vals.shape}")

    if mode == "linear":
        sv = explainer.shap_values(X_eval)

        if isinstance(sv, list):
            sv = sv[1] if len(sv) > 1 else sv[0]

        sv = np.asarray(sv)

        if sv.ndim == 3:
            k = sv.shape[2]
            class_idx = 1 if k > 1 else 0
            sv = sv[:, :, class_idx]

        if sv.ndim != 2:
            raise RuntimeError(f"Unexpected LinearExplainer SHAP shape: {sv.shape}")

        return np.asarray(sv, dtype=np.float32)

    raise RuntimeError(f"Unknown explainer mode: {mode}")


def _normalize_metadata_columns(md: pd.DataFrame):
    md = md.copy()
    md.columns = [str(c).strip() for c in md.columns]
    md.index = md.index.astype(str)
    return md


def add_metadata_flags(X: pd.DataFrame, metadata_csv, seq_col="Sequence Type", cohort_col="Cohort Type"):
    X = X.copy()
    X.index = X.index.astype(str)
    md = _normalize_metadata_columns(pd.read_csv(metadata_csv, index_col=0))
    md_aligned = md.reindex(X.index)

    if md_aligned.isna().all(axis=1).any():
        missing_ids = md_aligned.index[md_aligned.isna().all(axis=1)].tolist()[:10]
        raise ValueError(f"Some input sample IDs were not found in metadata index: {missing_ids}")

    if seq_col not in md_aligned.columns:
        raise ValueError(f"Metadata missing required column: '{seq_col}'")
    if cohort_col not in md_aligned.columns:
        raise ValueError(f"Metadata missing required column: '{cohort_col}'")

    seq = md_aligned[seq_col].astype(str).str.strip().str.lower()
    X["Is16s"] = seq.str.contains("16").astype(float)
    cohort = md_aligned[cohort_col].astype(str).str.strip().str.lower()
    X["IsIndustrialized"] = (cohort == "industrialized").astype(float)
    return X


def available_diseases(tech: str, shap_train_root=None, resource_dir=None):
    root = tech_shap_root(tech, shap_train_root, resource_dir)
    expected = {
        p.name.removeprefix("expected_cols_").removesuffix(".pkl")
        for p in root.glob("expected_cols_*.pkl")
    }
    explainer_root = root / "Explainers"
    explained = {p.name for p in explainer_root.iterdir() if p.is_dir()} if explainer_root.exists() else set()
    return sorted(expected & explained)


def list_explainer_pairs(explainer_dir: Path):
    pairs = []
    for meta_path in sorted(explainer_dir.glob("*_explainer_meta.json")):
        model_name = meta_path.name.removesuffix("_explainer_meta.json")
        explainer_path = explainer_dir / f"{model_name}_explainer.pkl"
        if explainer_path.exists():
            pairs.append((model_name, explainer_path, meta_path))
    return pairs


def run_disease_shap(
    *,
    tech: str,
    disease: str,
    input_df: pd.DataFrame,
    output_dir,
    shap_train_root=None,
    metadata_csv=None,
    resource_dir=None,
):
    tech = tech.upper()
    root = tech_shap_root(tech, shap_train_root, resource_dir)
    cols_path = root / f"expected_cols_{disease}.pkl"
    explainer_dir = root / "Explainers" / disease

    if not cols_path.exists():
        raise FileNotFoundError(f"[{tech}/{disease}] Missing expected columns file: {cols_path}")
    if not explainer_dir.is_dir():
        raise FileNotFoundError(f"[{tech}/{disease}] Missing explainer directory: {explainer_dir}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    expected_cols = list(joblib.load(cols_path))
    X_raw = input_df.drop(columns=[c for c in DROP_COLUMNS if c in input_df.columns], errors="ignore").copy()
    if metadata_csv is not None:
        X_raw = add_metadata_flags(X_raw, metadata_csv)

    X_eval = sanitize_features_df(X_raw, expected_columns=expected_cols)
    explainer_pairs = list_explainer_pairs(explainer_dir)

    shap_mats = []
    skipped = []
    used = {"tree": 0, "linear": 0}

    for model_name, explainer_path, meta_path in tqdm(explainer_pairs, desc=f"{tech}/{disease}: explainers"):
        explainer, meta = load_explainer(explainer_path, meta_path)
        mode = meta.get("mode")
        if mode not in ("tree", "linear"):
            skipped.append({"model": model_name, "reason": f"unsupported mode: {mode}"})
            continue

        sv = shap_values_from_explainer(explainer, mode, X_eval)
        expected_shape = (X_eval.shape[0], X_eval.shape[1])
        if sv.shape != expected_shape:
            raise RuntimeError(
                f"[{tech}/{disease}] SHAP shape mismatch for {model_name}: "
                f"got {sv.shape}, expected {expected_shape}"
            )

        used[mode] += 1
        shap_mats.append(sv)

    if not shap_mats:
        raise RuntimeError(f"[{tech}/{disease}] No usable explainers found in {explainer_dir}")

    shap_stack = np.stack(shap_mats, axis=0)
    shap_agg = np.median(shap_stack, axis=0)

    shap_csv_path = output_dir / f"SHAP_Explanations_{disease}_{tech}_tree_linear_medianAgg.csv"
    shap_csv_path_global = output_dir / f"SHAP_Explanations_{disease}_{tech}_tree_linear_medianAgg_global.csv"
    runinfo_path = output_dir / f"SHAP_RunInfo_{disease}_{tech}.json"

    shap_df = pd.DataFrame(shap_agg, columns=X_eval.columns)
    shap_df["instance_id"] = input_df.index
    shap_df.to_csv(shap_csv_path, index=False)

    global_importance = pd.DataFrame({
        "Feature": X_eval.columns,
        "SHAP_Importance": np.abs(shap_agg).mean(axis=0),
    }).sort_values("SHAP_Importance", ascending=False)
    global_importance.to_csv(shap_csv_path_global, index=False)

    runinfo = {
        "tech": tech,
        "disease": disease,
        "expected_cols_path": str(cols_path),
        "explainer_dir": str(explainer_dir),
        "n_instances_eval": int(X_eval.shape[0]),
        "n_features": int(X_eval.shape[1]),
        "n_models_used_tree": int(used["tree"]),
        "n_models_used_linear": int(used["linear"]),
        "n_models_used_total": int(sum(used.values())),
        "skipped": skipped,
        "outputs": {
            "per_instance_csv": str(shap_csv_path),
            "global_importance_csv": str(shap_csv_path_global),
            "runinfo_json": str(runinfo_path),
        },
    }
    with open(runinfo_path, "w") as f:
        json.dump(runinfo, f, indent=2)

    return runinfo


def run_tech_shap(
    *,
    tech: str,
    input_csv,
    output_dir,
    shap_train_root=None,
    diseases=None,
    metadata_csv=None,
    resource_dir=None,
):
    tech = tech.upper()
    input_csv = Path(input_csv).resolve()
    if not input_csv.exists():
        raise FileNotFoundError(f"{tech} input CSV not found: {input_csv}")

    input_df = pd.read_csv(input_csv, index_col=0)
    input_df.index = input_df.index.astype(str)

    diseases = list(diseases) if diseases else available_diseases(tech, shap_train_root, resource_dir)
    if not diseases:
        raise RuntimeError(f"No diseases found for tech={tech}")

    tech_output_dir = Path(output_dir) / tech
    runinfos = []
    for disease in diseases:
        print(f"\n=== {tech}: {disease} ===", flush=True)
        runinfos.append(
            run_disease_shap(
                tech=tech,
                disease=disease,
                input_df=input_df,
                output_dir=tech_output_dir,
                shap_train_root=shap_train_root,
                metadata_csv=metadata_csv,
                resource_dir=resource_dir,
            )
        )
    return runinfos


def run_shap(
    *,
    ap_csv,
    output_dir,
    shap_train_root=None,
    diseases=None,
    metadata_csv=None,
    resource_dir=None,
):
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    ap_infos = run_tech_shap(
        tech="AP",
        input_csv=ap_csv,
        output_dir=output_dir,
        shap_train_root=shap_train_root,
        diseases=diseases,
        metadata_csv=metadata_csv,
        resource_dir=resource_dir,
    )
    manifest = {
        "ap_input": str(Path(ap_csv).resolve()),
        "output_dir": str(output_dir),
        "diseases": list(diseases) if diseases else None,
        "metadata_csv": str(Path(metadata_csv).resolve()) if metadata_csv else None,
        "resource_dir": str(Path(resource_dir).resolve()) if resource_dir else None,
        "ap": ap_infos,
    }
    manifest_path = output_dir / "SHAP_RunManifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest
