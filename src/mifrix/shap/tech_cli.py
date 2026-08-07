import argparse
import json
from pathlib import Path

from .cli import resolve_requested_diseases
from .core import available_diseases, run_tech_shap


def build_parser(default_tech: str):
    parser = argparse.ArgumentParser(
        description=f"Run MifRix SHAP explanations for {default_tech} input only."
    )
    parser.add_argument("--input", "--validation-csv", dest="input_csv", default=None, help=f"Prepared {default_tech} input CSV.")
    parser.add_argument("--output-dir", default=None, help=f"Directory where the {default_tech} SHAP output folder is written.")
    parser.add_argument("--metadata", default=None, help="Optional metadata CSV indexed by sample ID for Is16s/IsIndustrialized flags.")
    parser.add_argument("--shap-train-root", default=None, help="Override saved SHAP train root containing the AP folder.")
    parser.add_argument("--resource-dir", default=None, help="Directory containing unpacked MifRix resources.")
    parser.add_argument("--diseases", "--disease", nargs="+", default=None, help="Optional disease/control subset. Accepts spaces or commas.")
    parser.add_argument("--disease-file", default=None, help="Optional text file with disease/control names.")
    parser.add_argument("--list-diseases", action="store_true", help=f"List diseases/control available for {default_tech} and exit.")
    parser.add_argument("--tech", default=default_tech, choices=("AP",), help=argparse.SUPPRESS)
    return parser


def run_single_tech(default_tech: str):
    args = build_parser(default_tech).parse_args()
    tech = args.tech.upper()

    if args.list_diseases:
        for disease in available_diseases(tech, args.shap_train_root, args.resource_dir):
            print(disease)
        return

    if not args.input_csv:
        raise SystemExit("--input is required unless --list-diseases is used.")
    if not args.output_dir:
        raise SystemExit("--output-dir is required unless --list-diseases is used.")

    diseases = resolve_requested_diseases(args)
    runinfos = run_tech_shap(
        tech=tech,
        input_csv=args.input_csv,
        output_dir=args.output_dir,
        shap_train_root=args.shap_train_root,
        diseases=diseases,
        metadata_csv=args.metadata,
        resource_dir=args.resource_dir,
    )

    output_dir = Path(args.output_dir).resolve()
    manifest = {
        "tech": tech,
        "input": str(Path(args.input_csv).resolve()),
        "output_dir": str(output_dir),
        "diseases": list(diseases) if diseases else None,
        "metadata_csv": str(Path(args.metadata).resolve()) if args.metadata else None,
        "resource_dir": str(Path(args.resource_dir).resolve()) if args.resource_dir else None,
        "runs": runinfos,
    }
    manifest_path = output_dir / f"SHAP_RunManifest_{tech}.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print("\nSHAP pipeline finished.")
    print(f"Output directory: {output_dir / tech}")


def main_ap():
    run_single_tech("AP")
if __name__ == "__main__":
    main_ap()
