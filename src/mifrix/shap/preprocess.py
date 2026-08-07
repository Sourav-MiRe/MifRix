import subprocess
import sys
from shutil import copyfile
from pathlib import Path


def run_cmd(cmd, step_name):
    print(f"\n{step_name} running...", flush=True)
    print(f"[{step_name}] Command: {' '.join(map(str, cmd))}", flush=True)
    subprocess.run([str(x) for x in cmd], check=True)
    print(f"{step_name} completed.", flush=True)


def default_preprocess_paths(raw_ap: Path, output_dir: Path):
    pre_dir = output_dir / "preprocessed"
    pre_dir.mkdir(parents=True, exist_ok=True)
    stem = raw_ap.stem
    return {
        "map_file": pre_dir / f"MAP_{stem}.csv",
        "normalized_ap": pre_dir / f"{stem}_normalized_AP.csv",
        "fp_matrix": pre_dir / f"{stem}_FP.csv",
    }


def run_mifrix_preprocessing(
    *,
    raw_ap=None,
    output_dir,
    map_file=None,
    normalized_ap_output=None,
    fp_matrix_output=None,
    online_fallback=True,
    resource_dir=None,
):
    try:
        from mifrix.risk_scores._paths import fp_rdata_path, r_script_path, taxonomy_db_path
    except ImportError as exc:
        raise RuntimeError(
            "Preprocessing mode requires the MifRix risk module to be installed in this environment."
        ) from exc

    raw_ap = Path(raw_ap).resolve()
    output_dir = Path(output_dir).resolve()
    if not raw_ap.exists():
        raise FileNotFoundError(f"Raw AP input not found: {raw_ap}")

    defaults = default_preprocess_paths(raw_ap, output_dir)
    map_file = Path(map_file).resolve() if map_file else defaults["map_file"]
    normalized_ap_output = Path(normalized_ap_output).resolve() if normalized_ap_output else defaults["normalized_ap"]
    fp_matrix_output = Path(fp_matrix_output).resolve() if fp_matrix_output else defaults["fp_matrix"]

    map_file.parent.mkdir(parents=True, exist_ok=True)
    normalized_ap_output.parent.mkdir(parents=True, exist_ok=True)
    fp_matrix_output.parent.mkdir(parents=True, exist_ok=True)

    run_cmd(
        [
            sys.executable,
            "-m",
            "mifrix.risk_scores.normalize",
            str(raw_ap),
            "--db",
            str(taxonomy_db_path(resource_dir)),
            *(["--online-fallback"] if online_fallback else []),
        ],
        "Stage 1 (MifRix normalize)",
    )

    generated_map = raw_ap.with_name(f"MAP_{raw_ap.stem}.csv")
    if not generated_map.exists():
        raise FileNotFoundError(f"MifRix normalize did not create expected map file: {generated_map}")
    if generated_map.resolve() != map_file.resolve():
        copyfile(generated_map, map_file)
        print(f"Copied taxonomy map to: {map_file}", flush=True)

    run_cmd(
        [
            "Rscript",
            str(r_script_path("mapping_species_names_normalized.R", resource_dir)),
            str(raw_ap),
            str(map_file),
            str(normalized_ap_output),
        ],
        "Stage 2 (MifRix AP normalization/collapse)",
    )

    run_cmd(
        [
            "Rscript",
            str(r_script_path("FP_AD.R", resource_dir)),
            str(normalized_ap_output),
            str(fp_matrix_output),
            str(fp_rdata_path(resource_dir)),
        ],
        "Stage 3 (MifRix FP matrix generation)",
    )

    return {
        "map_file": str(map_file),
        "normalized_ap": str(normalized_ap_output),
        "fp_matrix": str(fp_matrix_output),
    }
