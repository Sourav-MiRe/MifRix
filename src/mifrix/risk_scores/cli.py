import argparse

from .pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="Run the MifRix unseen-data risk score pipeline.")
    parser.add_argument("species_profile", help="Input AP species profile CSV.")
    parser.add_argument("--metadata", required=True, help="Metadata CSV indexed by sample ID.")
    parser.add_argument("--map-file", default=None)
    parser.add_argument("--normalized-ap-output", default=None)
    parser.add_argument("--fp-matrix-output", default=None)
    parser.add_argument("--scores-output-dir", default=None)
    parser.add_argument("--resource-dir", default=None, help="Directory containing unpacked MifRix resources.")
    parser.add_argument("--no-online-fallback", action="store_true")
    args = parser.parse_args()

    outputs = run_pipeline(
        species_profile=args.species_profile,
        metadata=args.metadata,
        map_file=args.map_file,
        normalized_ap_output=args.normalized_ap_output,
        fp_matrix_output=args.fp_matrix_output,
        scores_output_dir=args.scores_output_dir,
        online_fallback=not args.no_online_fallback,
        resource_dir=args.resource_dir,
    )

    print("Pipeline finished.")
    for key, value in outputs.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
