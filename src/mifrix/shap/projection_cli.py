import argparse
import subprocess
from importlib.resources import files
from pathlib import Path

import pandas as pd

from ._paths import projection_pca_results_path


def _script_path() -> Path:
    return Path(str(files("mifrix.shap"))) / "projection.R"


def _validate_metadata(path: Path):
    metadata = pd.read_csv(path, nrows=5)
    if "type" not in metadata.columns:
        raise SystemExit("Metadata CSV must contain a required 'type' column.")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Project MifRix AP SHAP values into saved PCA space."
    )
    parser.add_argument("--disease", required=True, help="Disease/control name, e.g. IBD_GutInflammation or T2D.")
    parser.add_argument("--shap-csv", required=True, help="AP SHAP CSV from mifrix-shap or mifrix-shap-ap.")
    parser.add_argument("--metadata-csv", required=True, help="Metadata CSV with a required 'type' column.")
    parser.add_argument("--output-dir", required=True, help="Directory for projection CSV, RData, and PDF outputs.")
    parser.add_argument("--pca-results", default=None, help="Optional override for Projection_PCA_results.RData.")
    parser.add_argument("--resource-dir", default=None, help="Directory containing unpacked MifRix resources.")
    return parser


def main():
    args = build_parser().parse_args()

    shap_csv = Path(args.shap_csv).resolve()
    metadata_csv = Path(args.metadata_csv).resolve()
    output_dir = Path(args.output_dir).resolve()
    pca_results = Path(args.pca_results).resolve() if args.pca_results else projection_pca_results_path(args.resource_dir)

    if not shap_csv.exists():
        raise SystemExit(f"SHAP CSV not found: {shap_csv}")
    if not metadata_csv.exists():
        raise SystemExit(f"Metadata CSV not found: {metadata_csv}")
    if not pca_results.exists():
        raise SystemExit(
            f"PCA results RData not found: {pca_results}. Run mifrix-unpack-resources or pass --pca-results."
        )

    _validate_metadata(metadata_csv)
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "Rscript",
        str(_script_path()),
        args.disease,
        str(pca_results),
        str(shap_csv),
        str(metadata_csv),
        str(output_dir),
    ]
    subprocess.run(cmd, check=True)

    print("\nSHAP projection finished.")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
