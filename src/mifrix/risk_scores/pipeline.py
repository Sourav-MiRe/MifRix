import subprocess
import sys
from pathlib import Path

from ._paths import fp_rdata_path, r_script_path, taxonomy_db_path


def run_cmd(cmd, step_name):
    print(f"\n{step_name} running...", flush=True)
    print(f"[{step_name}] Command: {' '.join(map(str, cmd))}", flush=True)
    subprocess.run([str(x) for x in cmd], check=True)
    print(f"{step_name} completed.", flush=True)


def default_fp_matrix_path(species_profile: Path) -> Path:
    stem = species_profile.stem
    if stem.endswith("_Species_prof"):
        return species_profile.with_name(stem.replace("_Species_prof", "_FP") + species_profile.suffix)
    return species_profile.with_name(f"{stem}_FP{species_profile.suffix}")


def default_score_prefix(species_profile: Path) -> str:
    stem = species_profile.stem
    for suffix in ("_Species_prof", "_species_prof", "_AP", "_FP"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return stem if stem else "scores"


def run_pipeline(
    *,
    species_profile,
    metadata,
    map_file=None,
    normalized_ap_output=None,
    fp_matrix_output=None,
    scores_output_dir=None,
    online_fallback=True,
    resource_dir=None,
):
    species_profile = Path(species_profile).resolve()
    metadata = Path(metadata).resolve()

    if not species_profile.exists():
        raise FileNotFoundError(f"species_profile not found: {species_profile}")
    if not metadata.exists():
        raise FileNotFoundError(f"metadata not found: {metadata}")

    map_file = Path(map_file).resolve() if map_file else species_profile.with_name(f"MAP_{species_profile.stem}.csv")
    normalized_ap_output = Path(normalized_ap_output).resolve() if normalized_ap_output else species_profile
    fp_matrix_output = Path(fp_matrix_output).resolve() if fp_matrix_output else default_fp_matrix_path(normalized_ap_output)
    scores_output_dir = Path(scores_output_dir).resolve() if scores_output_dir else species_profile.parent / "MifRix_Results"
    scores_output_dir.mkdir(parents=True, exist_ok=True)

    score_prefix = default_score_prefix(species_profile)
    ap_score_output = scores_output_dir / f"{score_prefix}_AP.csv"
    fp_score_output = scores_output_dir / f"{score_prefix}_FP.csv"
    resource_args = ["--resource-dir", str(resource_dir)] if resource_dir else []

    run_cmd(
        [
            sys.executable,
            "-m",
            "mifrix.risk_scores.normalize",
            str(species_profile),
            "--db",
            str(taxonomy_db_path(resource_dir)),
            *(["--online-fallback"] if online_fallback else []),
        ],
        "Stage 1 (normalize)",
    )

    run_cmd(
        [
            "Rscript",
            str(r_script_path("mapping_species_names_normalized.R", resource_dir)),
            str(species_profile),
            str(map_file),
            str(normalized_ap_output),
        ],
        "Stage 2 (mapping_species_names_normalized.R)",
    )

    run_cmd(
        [
            "Rscript",
            str(r_script_path("FP_AD.R", resource_dir)),
            str(normalized_ap_output),
            str(fp_matrix_output),
            str(fp_rdata_path(resource_dir)),
        ],
        "Stage 3 (FP_AD.R)",
    )

    run_cmd(
        [
            sys.executable,
            "-m",
            "mifrix.risk_scores.scoring",
            "--tech",
            "AP",
            "--validation-csv",
            str(normalized_ap_output),
            "--metadata-csv",
            str(metadata),
            "--output-csv",
            str(ap_score_output),
            *resource_args,
        ],
        "Stage 4 (AP scoring)",
    )

    run_cmd(
        [
            sys.executable,
            "-m",
            "mifrix.risk_scores.scoring",
            "--tech",
            "FP",
            "--validation-csv",
            str(fp_matrix_output),
            "--metadata-csv",
            str(metadata),
            "--output-csv",
            str(fp_score_output),
            *resource_args,
        ],
        "Stage 5 (FP scoring)",
    )

    return {
        "map_file": str(map_file),
        "normalized_ap": str(normalized_ap_output),
        "fp_matrix": str(fp_matrix_output),
        "ap_scores": str(ap_score_output),
        "fp_scores": str(fp_score_output),
    }
