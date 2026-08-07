import argparse
import json
from pathlib import Path

from .preprocess import run_mifrix_preprocessing


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run MifRix AP preprocessing and FP matrix generation only."
    )
    parser.add_argument("--ap-input", required=True, help="Raw AP species profile CSV.")
    parser.add_argument("--output-dir", required=True, help="Directory where preprocessing outputs are written.")
    parser.add_argument("--map-file", default=None, help="Optional taxonomy map output path.")
    parser.add_argument("--normalized-ap-output", default=None, help="Optional normalized AP output path.")
    parser.add_argument("--fp-matrix-output", default=None, help="Optional generated FP matrix output path.")
    parser.add_argument("--resource-dir", default=None, help="Directory containing unpacked MifRix resources.")
    parser.add_argument("--no-online-fallback", action="store_true", help="Disable online taxonomy fallback during preprocessing.")
    return parser


def main():
    args = build_parser().parse_args()
    outputs = run_mifrix_preprocessing(
        raw_ap=args.ap_input,
        output_dir=args.output_dir,
        map_file=args.map_file,
        normalized_ap_output=args.normalized_ap_output,
        fp_matrix_output=args.fp_matrix_output,
        online_fallback=not args.no_online_fallback,
        resource_dir=args.resource_dir,
    )

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "Preprocess_RunManifest.json"
    with open(manifest_path, "w") as f:
        json.dump(outputs, f, indent=2)

    print("\nPreprocessing finished.")
    for key, value in outputs.items():
        print(f"{key}: {value}")
    print(f"manifest: {manifest_path}")


if __name__ == "__main__":
    main()
