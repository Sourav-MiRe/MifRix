# ============================================================
# MifRix Final Score
# ============================================================
#
# This script calculates the final MifRix score from AP and FP
# risk-score data frames.
#
# Command-line usage:
#
# Rscript Compute_MifRix_final_score.R \
#     <AP_file.csv> \
#     <FP_file.csv> \
#     <output_file.csv>
#
# Example:
#
# Rscript Compute_MifRix_final_score.R \
#     AP_scores.csv \
#     FP_scores.csv \
#     MifRix_final_scores.csv
#
# ============================================================


# ------------------------------------------------------------
# Function: compute_MifRix_final_score
# ------------------------------------------------------------

compute_MifRix_final_score <- function(AP, FP) {

  # Check that AP and FP are of the same class
  if (class(AP)[1] != class(FP)[1]) {
    stop("AP and FP must both be vectors or both be data frames.")
  }


  # ----------------------------------------------------------
  # Case 1: AP and FP are numeric vectors
  # ----------------------------------------------------------

  if (is.vector(AP) && is.numeric(AP)) {

    if (length(AP) != length(FP)) {
      stop("AP and FP vectors must have the same length.")
    }

    CS <- mapply(
      function(ap, fp) {

        vals <- c(ap, fp)

        mean(vals) * (1 - Gini(vals))

      },
      AP,
      FP
    )

    return(
      data.frame(
        AP = AP,
        FP = FP,
        CS = CS,
        stringsAsFactors = FALSE
      )
    )
  }


  # ----------------------------------------------------------
  # Case 2: AP and FP are data frames
  # ----------------------------------------------------------

  if (is.data.frame(AP)) {

    # Check that AP and FP have identical columns
    if (!identical(colnames(AP), colnames(FP))) {
      stop("AP and FP data frames must have identical columns.")
    }

    # Start with AP data frame
    composite_df <- AP

    # Identify numeric columns
    disease_cols <- names(AP)[sapply(AP, is.numeric)]


    # Calculate final MifRix score for each numeric column
    for (disease in disease_cols) {

      composite_df[[disease]] <-
        mapply(
          function(ap, fp) {

            vals <- c(ap, fp)

            mean(vals) * (1 - Gini(vals))

          },
          AP[[disease]],
          FP[[disease]]
        )
    }

    return(composite_df)
  }


  # ----------------------------------------------------------
  # Unsupported input type
  # ----------------------------------------------------------

  stop("Unsupported input type.")
}


# ============================================================
# Command-line interface
# ============================================================

args <- commandArgs(trailingOnly = TRUE)


# ------------------------------------------------------------
# Check command-line arguments
# ------------------------------------------------------------

if (length(args) < 3) {

  cat("\n")
  cat("MifRix Final Score\n")
  cat("==================\n\n")

  cat("Usage:\n")
  cat(
    "Rscript Compute_MifRix_final_score.R ",
    "<AP_file.csv> <FP_file.csv> <output_file.csv>\n\n",
    sep = ""
  )

  cat("Example:\n")
  cat(
    "Rscript Compute_MifRix_final_score.R ",
    "AP_scores.csv FP_scores.csv MifRix_final_scores.csv\n\n",
    sep = ""
  )

  quit(
    status = 1,
    save = "no"
  )
}


# ------------------------------------------------------------
# Read command-line arguments
# ------------------------------------------------------------

AP_file <- args[1]
FP_file <- args[2]
output_file <- args[3]


# ------------------------------------------------------------
# Check that input files exist
# ------------------------------------------------------------

if (!file.exists(AP_file)) {
  stop(
    paste0(
      "AP input file does not exist: ",
      AP_file
    )
  )
}

if (!file.exists(FP_file)) {
  stop(
    paste0(
      "FP input file does not exist: ",
      FP_file
    )
  )
}


# ------------------------------------------------------------
# Read AP and FP data
# ------------------------------------------------------------

cat("Reading AP risk scores...\n")

AP <- read.csv(
  AP_file,
  row.names = 1,
  check.names = FALSE,
  stringsAsFactors = FALSE
)


cat("Reading FP risk scores...\n")

FP <- read.csv(
  FP_file,
  row.names = 1,
  check.names = FALSE,
  stringsAsFactors = FALSE
)


# ------------------------------------------------------------
# Calculate final MifRix score
# ------------------------------------------------------------

cat("Calculating final MifRix scores...\n")

final_score <- compute_MifRix_final_score(
  AP = AP,
  FP = FP
)


# ------------------------------------------------------------
# Write output
# ------------------------------------------------------------

write.csv(
  final_score,
  output_file,
  row.names = TRUE
)


# ------------------------------------------------------------
# Completion message
# ------------------------------------------------------------

cat("\n")
cat("MifRix final score calculation completed successfully.\n")
cat("Output file:\n")
cat(output_file)
cat("\n\n")
