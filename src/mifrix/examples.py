import argparse
import shutil
from importlib.resources import files
from pathlib import Path


EXAMPLE_FILES = {
    "risk_ap": "wilsonb_2025/WilsonB_2025_AP.csv",
    "risk_metadata": "wilsonb_2025/WilsonB_2025_metadata.csv",
    "projection_shap": "projection/WilsonB_2025_IBD_GutInflammation_AP_SHAP.csv",
    "projection_metadata": "projection/WilsonB_2025_projection_metadata.csv",
}


def example_data_root() -> Path:
    return Path(str(files("mifrix"))) / "example_data"


def iter_example_paths():
    root = example_data_root()
    for name, relative_path in EXAMPLE_FILES.items():
        yield name, root / relative_path


def copy_example_data(output_dir) -> Path:
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, source in iter_example_paths():
        if not source.exists():
            raise FileNotFoundError(f"Packaged example file missing: {source}")
        destination = output_dir / source.relative_to(example_data_root())
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    return output_dir


def build_parser():
    parser = argparse.ArgumentParser(description="List or copy packaged MifRix example data.")
    parser.add_argument(
        "--copy-to",
        default=None,
        help="Optional directory where packaged example data should be copied.",
    )
    return parser


def main():
    args = build_parser().parse_args()

    if args.copy_to:
        output_dir = copy_example_data(args.copy_to)
        print(f"Copied MifRix example data to: {output_dir}")
        return

    print("Packaged MifRix example data:")
    for name, path in iter_example_paths():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
