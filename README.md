# MifRix

This repository contains the combined `MifRix` package with code plus a compressed archive of the models, explainers, taxonomy, and FP resources.

## Package Layout

The Python package is organized as:

- `mifrix.risk_scores`: AP/FP preprocessing and risk-scoring
- `mifrix.shap`: SHAP explanation generation using AP

Installed command-line entry points:

- `mifrix-risk-score`
- `mifrix-score-ap`
- `mifrix-score-fp`
- `mifrix-preprocess`
- `mifrix-shap`
- `mifrix-shap-ap`
- `mifrix-shap-projection`
- `shap-projection`
- `mifrix-unpack-resources`
- `mifrix-example-data`

## Resource Setup

MifRix ships the models, explainers, taxonomic abundance, Sub-signature profiles, and FP resources as split compressed archive parts. Each part is kept below GitHub's 100 MB file limit:

```text
src/mifrix/resource_archives/mifrix_resources.tar.gz.part000
src/mifrix/resource_archives/mifrix_resources.tar.gz.part001
...
```

After installing the package, unpack the resources once:

```bash
mifrix-unpack-resources
```

The unpack command reads all archive parts together and extracts them as one resource bundle.

By default this writes to:

```text
~/.mifrix/resources
```

You can choose a different location:

```bash
mifrix-unpack-resources --output-dir /path/to/MifRix_resources
```

Then either set:

```bash
export MIFRIX_RESOURCE_DIR=/path/to/MifRix_resources
```

or pass the location to commands:

```bash
mifrix-risk-score input.csv --metadata metadata.csv --resource-dir /path/to/MifRix_resources
mifrix-shap --ap-input input_AP.csv --output-dir shap_out --resource-dir /path/to/MifRix_resources
```

The unpacked directory contains:

```text
<resource-dir>/
  risk_scores/resources/
  shap/resources/
```

## Example Data

MifRix includes a taxa abundance dataset and corresponding metadata from a study-cohort WilsonB_2025 as example files that show the expected input formats for risk scoring, computing SHAP profiles using AP, and SHAP-based projection to find the disease-specific sub-signatures.

List the packaged example files:

```bash
mifrix-example-data
```

Copy them into a working directory:

```bash
mifrix-example-data --copy-to ./mifrix_examples
```

The copied files are:

```text
./mifrix_examples/
  WilsonB_2025/
    WilsonB_2025_AP.csv
    WilsonB_2025_metadata.csv
  projection/
    WilsonB_2025_IBD_GutInflammation_AP_SHAP.csv
    WilsonB_2025_projection_metadata.csv
```

Example risk scoring:

```bash
mifrix-risk-score \
  ./mifrix_examples/WilsonB_2025/WilsonB_2025_AP.csv \
  --metadata ./mifrix_examples/WilsonB_2025/WilsonB_2025_metadata.csv \
  --scores-output-dir ./mifrix_example_outputs/risk
```

Example AP SHAP:

```bash
mifrix-shap \
  --ap-input ./mifrix_examples/WilsonB_2025/WilsonB_2025_AP.csv \
  --metadata ./mifrix_examples/WilsonB_2025/WilsonB_2025_metadata.csv \
  --output-dir ./mifrix_example_outputs/shap \
  --diseases IBD_GutInflammation
```

Example of Disease sub-signature identification through SHAP values projection:

```bash
shap-projection \
  --disease IBD_GutInflammation \
  --shap-csv ./mifrix_examples/projection/WilsonB_2025_IBD_GutInflammation_AP_SHAP.csv \
  --metadata-csv ./mifrix_examples/projection/WilsonB_2025_projection_metadata.csv \
  --output-dir ./mifrix_example_outputs/projection
```

## What MifRix Does

MifRix package is designed to predict risk-scores using taxonomic Abundance Profiles (AP) as well as Microbiome Functions (FP) and ultimately it computes the MifRix-final-score by integrating both AP- and FP-based score together. Then it computes SHAP-based explanations.

Given:

- one species abundance profile (AP) in CSV format
- one metadata in CSV format

MifRix risk scoring runs:

1. taxonomic nomenclature homogenization
2. AP normalization/collapse
3. FP generation
4. AP risk-scoring
5. FP risk-scoring

and produces:

- a `MAP_*.csv` taxonomy mapping file
- a normalized AP file
- an FP file
- AP risk-score output
- FP risk-score output

The SHAP module can then run saved AP explainers and produce disease-wise per-instance SHAP values plus global SHAP importance tables.
The SHAP projection command can then project AP SHAP values into saved disease-wise PCA spaces.


## Development install

### Recommended

```bash
conda env create -f environment.yml
conda activate MifRix
pip install -e .
```

### Lighter alternative

```bash
conda env create -f environment.from_history.yml
conda activate MifRix
pip install -e .
```

Notes:

- `environment.yml` is the full exported environment from the working local setup
- `environment.from_history.yml` is a lighter alternative

## Main runtime command

When the full packaged distribution is installed, the main command is:

```bash
mifrix-risk-score /path/to/species_profile.csv --metadata /path/to/metadata.csv
```

## Full runtime example

```bash
mifrix-risk-score \
  /path/to/Donors_CDFMT_Species_prof.csv \
  --metadata /path/to/Donors_CDFMT_MD.csv \
  --scores-output-dir /path/to/results
```

## Runtime input requirements

MifRix runtime needs two inputs:

1. species abundance profile in CSV
2. metadata in CSV

### Species profile CSV

Expected structure:

- CSV format
- first column is the sample ID index
- all remaining columns are microbial species/features
- one row per sample

Important:

- sample IDs must match the metadata index exactly

### Metadata CSV

The metadata CSV must:

- be a CSV
- have the first column as the sample ID index
- contain one row per sample
- use the same sample IDs as the species profile file

Required columns:

- `Sequence Type`
- `Cohort Type`

Optional columns copied to score outputs when present:

- `study_name`
- `diseaseCat`

Optional extra columns are allowed.

Example:

```csv
,study_name,Sequence Type,Cohort Type,diseaseCat,Countries
D21-0-week-CDFMT37,CDFMT,WGS,Non-Industrialized,,IND
D21-0-week-CDFMT13,CDFMT,WGS,Non-Industrialized,,IND
```

How MifRix uses the metadata:

- `study_name`
  - optional; copied to the final AP/FP outputs when present
- `Sequence Type`
  - used to create `Is16s`
  - values containing `16s` become `1`
  - `WGS` becomes `0`
- `Cohort Type`
  - used to create `IsIndustrialized`
  - `Industrialized` becomes `1`
  - anything else becomes `0`
- `diseaseCat`
  - optional; copied to final outputs when present

In the metadata example above:

- `Sequence Type = WGS` gives `Is16s = 0`
- `Cohort Type = Non-Industrialized` gives `IsIndustrialized = 0`

## Runtime CLI options

### `mifrix-risk-score`

Command:

```bash
mifrix-risk-score <species_profile> --metadata <metadata_csv> [options]
```

Arguments:

- positional `species_profile`
  - required AP species profile CSV
- `--metadata`
  - required metadata CSV
- `--map-file`
  - optional path for the generated taxonomy mapping CSV
- `--normalized-ap-output`
  - optional output path for normalized AP
- `--fp-matrix-output`
  - optional output path for generated FP matrix
- `--scores-output-dir`
  - optional output folder for final AP/FP score files
- `--no-online-fallback`
  - disables online fallback during taxonomy normalization
- `--resource-dir`
  - optional directory containing resources unpacked by `mifrix-unpack-resources`

Example with all main options:

```bash
mifrix-risk-score \
  /path/to/input_species.csv \
  --metadata /path/to/input_metadata.csv \
  --map-file /path/to/MAP_input_species.csv \
  --normalized-ap-output /path/to/normalized_ap.csv \
  --fp-matrix-output /path/to/generated_fp.csv \
  --scores-output-dir /path/to/final_scores \
  --resource-dir /path/to/MifRix_resources
```

## Direct scoring commands

If you already have the processed AP or FP input, you can score directly.

### `mifrix-score-ap`

```bash
mifrix-score-ap \
  --validation-csv /path/to/normalized_ap.csv \
  --metadata-csv /path/to/metadata.csv \
  --output-csv /path/to/output_ap_scores.csv
```

Options:

- `--validation-csv`
  - required AP input to score
- `--metadata-csv`
  - required metadata CSV
- `--output-csv`
  - required AP score output CSV
- `--models-root`
  - optional override for AP model directory
- `--train-splits-dir`
  - optional override for AP train schema directory
- `--tech`
  - defaults to `AP`
- `--resource-dir`
  - optional directory containing resources unpacked by `mifrix-unpack-resources`

### `mifrix-score-fp`

```bash
mifrix-score-fp \
  --validation-csv /path/to/fp_matrix.csv \
  --metadata-csv /path/to/metadata.csv \
  --output-csv /path/to/output_fp_scores.csv
```

Options:

- `--validation-csv`
  - required FP input to score
- `--metadata-csv`
  - required metadata CSV
- `--output-csv`
  - required FP score output CSV
- `--models-root`
  - optional override for FP model directory
- `--train-splits-dir`
  - optional override for FP train schema directory
- `--tech`
  - defaults to `FP`
- `--resource-dir`
  - optional directory containing resources unpacked by `mifrix-unpack-resources`

## MifRix Final Score

After generating AP and FP risk scores using the MifRix risk-scoring
pipeline, the MifRix-final-score can be calculated using the provided
R utility.

### Usage

The MifRix-final-score utility is provided in:

`MifRix_final_score/Compute_MifRix_final_score.R`

Run the utility from the terminal:

```bash
Rscript MifRix_final_score/Compute_MifRix_final_score.R \
    <AP_score_file.csv> \
    <FP_score_file.csv> \
    <output_file.csv>
```

### Example

For example, if your AP and FP risk-score files are:

- `AP_scores.csv`
- `FP_scores.csv`

run:

```bash
Rscript MifRix_final_score/Compute_MifRix_final_score.R \
    AP_scores.csv \
    FP_scores.csv \
    MifRix_final_scores.csv
```

This will generate:

`MifRix_final_scores.csv`

### Input

The utility requires:

- An AP risk-score CSV file
- An FP risk-score CSV file

The AP and FP files must contain identical column names.

### Output

The utility generates a CSV file containing the final MifRix scores.


## Only Preprocessing

Generate only the preprocessed AP/FP files without risk scoring or SHAP:

```bash
mifrix-preprocess \
  --ap-input /path/to/raw_species_profile.csv \
  --output-dir /path/to/preprocess_outputs
```

Optional explicit output paths:

```bash
mifrix-preprocess \
  --ap-input /path/to/raw_species_profile.csv \
  --output-dir /path/to/preprocess_outputs \
  --map-file /path/to/MAP_input.csv \
  --normalized-ap-output /path/to/normalized_AP.csv \
  --fp-matrix-output /path/to/generated_FP.csv
```

## Computing SHAP profiles

Use this when the AP file has already been prepared:

```bash
mifrix-shap \
  --ap-input /path/to/input_AP.csv \
  --output-dir /path/to/shap_outputs
```

Use preprocessing mode when only a raw AP species profile is available:

```bash
mifrix-shap \
  --preprocess \
  --ap-input /path/to/raw_species_profile.csv \
  --metadata /path/to/metadata.csv \
  --output-dir /path/to/shap_outputs
```

Run only selected diseases/control:

```bash
mifrix-shap \
  --ap-input /path/to/input_AP.csv \
  --output-dir /path/to/shap_outputs \
  --diseases T2D control
```

Run SHAP for AP only:

```bash
mifrix-shap-ap \
  --input /path/to/input_AP.csv \
  --output-dir /path/to/shap_outputs \
  --diseases T2D control
```

List available diseases/control:

```bash
mifrix-shap --list-diseases
mifrix-shap-ap --list-diseases
```
## Disease sub-signatures identification using SHAP-based PCA space

Project AP-based SHAP values into the saved PCA space:

```bash
shap-projection \
  --disease IBD_GutInflammation \
  --shap-csv /path/to/SHAP_Explanations_IBD_GutInflammation_AP_tree_linear_medianAgg.csv \
  --metadata-csv /path/to/projection_metadata.csv \
  --output-dir /path/to/projection_outputs
```

The projection metadata CSV must contain a `type` column. It should also contain one sample identifier column named `Sample`, `sample`, `sample_id`, `SampleID`, or `instance_id`; otherwise the first column is used as the sample identifier.

SHAP outputs are written as:

```text
<output-dir>/
  AP/
  preprocessed/   # only when --preprocess is used
```

Projection outputs are written as:

```text
<output-dir>/
  <disease>_PCA_with_Intervention.pdf
  <disease>_projection_pca.csv
  <disease>_projection_clusters.csv
  <disease>_projection_cluster_df_all.csv
  <disease>_projection_results.RData
```

## Typical outputs after a full run

Main outputs from a full run:

- `MAP_<input_stem>.csv`
- normalized AP CSV
- FP CSV
- `<base>_AP.csv`
- `<base>_FP.csv`

Final AP/FP score CSVs include:

- one probability column per disease model
- `GD_Probability` for the control model
- `study_name` when present in metadata
- `diseaseCat` when present in metadata

## Notes

- `Rscript` must be available in the active environment
- AP and FP scoring use packaged train schema files to align features safely
- runtime will fail if metadata rows are missing for input sample IDs
- run `mifrix-unpack-resources` once after installation before running commands that need models or explainers
