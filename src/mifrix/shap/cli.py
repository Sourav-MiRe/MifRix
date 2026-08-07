import argparse
import json
from pathlib import Path

from .preprocess import run_mifrix_preprocessing


def parse_disease_values(values):
    if not values:
        return None

    diseases = []
    for value in values:
        for part in str(value).split(","):
            disease = part.strip()
            if disease:
                diseases.append(disease)
    return diseases or None


def read_disease_file(path):
    diseases = []
    with open(path, "r") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            diseases.extend(parse_disease_values([line]) or [])
    return diseases or None


def resolve_requested_diseases(args):
    diseases = parse_disease_values(args.diseases)
    file_diseases = read_disease_file(args.disease_file) if args.disease_file else None

    if diseases and file_diseases:
        merged = []
        seen = set()
        for disease in diseases + file_diseases:
            if disease not in seen:
                merged.append(disease)
                seen.add(disease)
        return merged

    return diseases or file_diseases


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run MifRix SHAP explanations for AP microbiome inputs."
    )
    parser.add_argument("--ap-input", default=None, help="Raw AP when --preprocess is used; otherwise prepared AP.")
    parser.add_argument("--output-dir", default=None, help="Directory where SHAP output folders are written.")
    parser.add_argument("--metadata", default=None, help="Optional metadata CSV indexed by sample ID for Is16s/IsIndustrialized flags.")
    parser.add_argument("--preprocess", action="store_true", help="Run MifRix preprocessing before SHAP.")
    parser.add_argument("--map-file", default=None, help="Optional preprocessing map-file output path.")
    parser.add_argument("--normalized-ap-output", default=None, help="Optional normalized AP output path.")
    parser.add_argument("--fp-matrix-output", default=None, help="Optional generated FP output path.")
    parser.add_argument("--no-online-fallback", action="store_true", help="Disable online taxonomy fallback during preprocessing.")
    parser.add_argument("--shap-train-root", default=None, help="Override saved SHAP train root containing the AP folder.")
    parser.add_argument("--resource-dir", default=None, help="Directory containing unpacked MifRix resources.")
    parser.add_argument(
        "--diseases",
        "--disease",
        nargs="+",
        default=None,
        help="Optional disease/control subset to run. Accepts spaces or commas, e.g. --diseases T2D control or --diseases T2D,control.",
    )
    parser.add_argument(
        "--disease-file",
        default=None,
        help="Optional text file with disease/control names, one per line or comma-separated. Lines may contain # comments.",
    )
    parser.add_argument(
        "--list-diseases",
        action="store_true",
        help="List diseases/control available in the packaged AP SHAP explainers and exit.",
    )
    return parser


def main():
    args = build_parser().parse_args()

    if args.list_diseases:
        from .core import available_diseases

        diseases = available_diseases("AP", args.shap_train_root, args.resource_dir)
        print("Available for AP SHAP:")
        for disease in diseases:
            print(f"  {disease}")
        return

    if not args.ap_input:
        raise SystemExit("--ap-input is required unless --list-diseases is used.")
    if not args.output_dir:
        raise SystemExit("--output-dir is required unless --list-diseases is used.")

    requested_diseases = resolve_requested_diseases(args)

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    preprocessing_outputs = None
    if args.preprocess:
        preprocessing_outputs = run_mifrix_preprocessing(
            raw_ap=args.ap_input,
            output_dir=output_dir,
            map_file=args.map_file,
            normalized_ap_output=args.normalized_ap_output,
            fp_matrix_output=args.fp_matrix_output,
            online_fallback=not args.no_online_fallback,
            resource_dir=args.resource_dir,
        )
        ap_csv = preprocessing_outputs["normalized_ap"]
    else:
        ap_csv = args.ap_input

    from .core import run_shap

    manifest = run_shap(
        ap_csv=ap_csv,
        output_dir=output_dir,
        shap_train_root=args.shap_train_root,
        diseases=requested_diseases,
        metadata_csv=args.metadata,
        resource_dir=args.resource_dir,
    )
    if preprocessing_outputs:
        manifest["preprocessing"] = preprocessing_outputs
        manifest_path = output_dir / "SHAP_RunManifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

    print("\nSHAP pipeline finished.")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
