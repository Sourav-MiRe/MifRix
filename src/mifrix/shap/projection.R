suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
})

ProjectIntervention <- function(
    disease_name,
    PCA_results,
    intervention_SHAP,
    intervention_metadata,
    output_dir = "."
){
  required_features <- rownames(PCA_results$pca_model$rotation)
  missing_features <- setdiff(required_features, colnames(intervention_SHAP))

  if(length(missing_features) > 0){
    stop(paste("Missing", length(missing_features), "features in intervention SHAP matrix."))
  }

  if(!("type" %in% colnames(intervention_metadata))){
    stop("intervention metadata must contain a required 'type' column.")
  }

  intervention_SHAP <- intervention_SHAP[, required_features, drop = FALSE]

  intervention_scaled <- scale(
    intervention_SHAP,
    center = PCA_results$pca_model$center,
    scale  = PCA_results$pca_model$scale
  )

  intervention_scores <- as.matrix(intervention_scaled) %*% PCA_results$pca_model$rotation

  intervention_pca <- data.frame(
    Sample = rownames(intervention_SHAP),
    PC1 = intervention_scores[,1],
    PC2 = intervention_scores[,2],
    stringsAsFactors = FALSE
  )

  if(!all(intervention_pca$Sample %in% rownames(intervention_metadata))){
    if(ncol(intervention_metadata) > 0 && all(intervention_pca$Sample %in% intervention_metadata[,1])){
      rownames(intervention_metadata) <- intervention_metadata[,1]
    }
  }

  if(!all(intervention_pca$Sample %in% rownames(intervention_metadata))){
    missing_samples <- setdiff(intervention_pca$Sample, rownames(intervention_metadata))
    stop(paste("Metadata is missing", length(missing_samples), "sample(s). First missing sample:", missing_samples[1]))
  }

  intervention_metadata <- intervention_metadata[intervention_pca$Sample,,drop=FALSE]
  intervention_pca$type <- intervention_metadata$type

  intervention_cluster <- rep(0, nrow(intervention_pca))
  ellipse_list <- PCA_results$ellipse_list
  centroids <- PCA_results$centroids

  use_ellipse_assignment <- !is.null(ellipse_list) && !is.null(centroids)
  if(use_ellipse_assignment && !requireNamespace("sp", quietly = TRUE)){
    stop("R package 'sp' is required for ellipse-based projection assignment.")
  }
  if(!use_ellipse_assignment){
    centroids <- PCA_results$cluster_df %>%
      group_by(Cluster) %>%
      summarize(
        PC1.centroid = mean(PC1, na.rm = TRUE),
        PC2.centroid = mean(PC2, na.rm = TRUE),
        .groups = "drop"
      )
  }

  for(i in seq_len(nrow(intervention_pca))){
    ptx <- intervention_pca$PC1[i]
    pty <- intervention_pca$PC2[i]

    if(use_ellipse_assignment){
      inside_clusters <- c()

      for(cl in names(ellipse_list)){
        poly <- ellipse_list[[cl]]
        inside <- sp::point.in.polygon(
          point.x = ptx,
          point.y = pty,
          pol.x = poly$x,
          pol.y = poly$y
        )

        if(inside > 0){
          inside_clusters <- c(inside_clusters, as.numeric(cl))
        }
      }

      if(length(inside_clusters) == 0){
        intervention_cluster[i] <- 0
      } else if(length(inside_clusters) == 1){
        intervention_cluster[i] <- inside_clusters
      } else {
        candidate_centroids <- centroids %>% dplyr::filter(Cluster %in% inside_clusters)
        dists <- sqrt(
          (candidate_centroids$PC1.centroid - ptx)^2 +
            (candidate_centroids$PC2.centroid - pty)^2
        )
        intervention_cluster[i] <- candidate_centroids$Cluster[which.min(dists)]
      }
    } else {
      dists <- sqrt(
        (centroids$PC1.centroid - ptx)^2 +
          (centroids$PC2.centroid - pty)^2
      )
      intervention_cluster[i] <- centroids$Cluster[which.min(dists)]
    }
  }

  intervention_pca$Cluster <- intervention_cluster
  intervention_pca_plot <- intervention_pca %>% filter(Cluster != 0)

  intervention_cluster_df <- intervention_pca_plot %>%
    transmute(
      Sample,
      Cluster,
      PC1,
      PC2,
      DataType = "intervention",
      Type = type
    )

  cluster_df_all <- bind_rows(PCA_results$cluster_df, intervention_cluster_df)

  n_groups <- length(unique(intervention_pca$type))
  cols <- colorRampPalette(c("#FFD700", "goldenrod1", "yellow", "lightgreen", "green"))(n_groups)

  p <- PCA_results$pca_plot +
    geom_point(
      data = intervention_pca_plot,
      aes(PC1, PC2, colour = type),
      shape = 16,
      size = 4.5,
      alpha = 1
    ) +
    scale_colour_manual(
      values = cols,
      name = "Intervention"
    )

  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  pdf(file.path(output_dir, paste0(disease_name, "_PCA_with_Intervention.pdf")), width = 15, height = 8)
  print(p)
  dev.off()

  cat("\n")
  cat("---------------------------------------\n")
  cat("Intervention projection completed.\n")
  cat("---------------------------------------\n")
  cat("\n")
  cat("Total intervention samples : ", nrow(intervention_pca), "\n")
  cat("Projected inside clusters : ", sum(intervention_cluster != 0), "\n")
  cat("Outside all ellipses       : ", sum(intervention_cluster == 0), "\n")
  cat("\n")
  print(table(intervention_cluster))
  cat("\n")

  list(
    intervention_pca = intervention_pca,
    intervention_cluster_df = intervention_cluster_df,
    cluster_df_all = cluster_df_all,
    pca_plot = p
  )
}

read_shap_csv <- function(path) {
  shap_df <- read.csv(path, check.names = FALSE, stringsAsFactors = FALSE)

  if("instance_id" %in% colnames(shap_df)){
    rownames(shap_df) <- shap_df$instance_id
    shap_df$instance_id <- NULL
    index_cols <- colnames(shap_df) %in% c("", "Unnamed: 0", "...1")
    if(any(index_cols)){
      shap_df <- shap_df[, !index_cols, drop = FALSE]
    }
  } else {
    rownames(shap_df) <- shap_df[[1]]
    shap_df <- shap_df[, -1, drop = FALSE]
    if("instance_id" %in% colnames(shap_df)){
      shap_df$instance_id <- NULL
    }
  }

  as.data.frame(lapply(shap_df, as.numeric), row.names = rownames(shap_df), check.names = FALSE)
}

read_metadata_csv <- function(path) {
  metadata <- read.csv(path, check.names = FALSE, stringsAsFactors = FALSE)
  if(!("type" %in% colnames(metadata))){
    stop("Metadata CSV must contain a required 'type' column.")
  }

  sample_cols <- c("Sample", "sample", "sample_id", "SampleID", "instance_id")
  sample_col <- sample_cols[sample_cols %in% colnames(metadata)][1]

  if(!is.na(sample_col)){
    rownames(metadata) <- metadata[[sample_col]]
  } else {
    rownames(metadata) <- metadata[[1]]
  }

  metadata
}

args <- commandArgs(trailingOnly = TRUE)
if(length(args) != 5){
  stop("Usage: Rscript projection.R <disease> <pca_results_rdata> <shap_csv> <metadata_csv> <output_dir>")
}

disease_name <- args[[1]]
pca_results_rdata <- args[[2]]
shap_csv <- args[[3]]
metadata_csv <- args[[4]]
output_dir <- args[[5]]

loaded_objects <- load(pca_results_rdata)
pca_object_name <- paste0(disease_name, "_PCA_results")
if(!(pca_object_name %in% loaded_objects)){
  stop(paste("PCA results object not found:", pca_object_name))
}

PCA_results <- get(pca_object_name)
intervention_SHAP <- read_shap_csv(shap_csv)
intervention_metadata <- read_metadata_csv(metadata_csv)

projection_results <- ProjectIntervention(
  disease_name = disease_name,
  PCA_results = PCA_results,
  intervention_SHAP = intervention_SHAP,
  intervention_metadata = intervention_metadata,
  output_dir = output_dir
)

write.csv(
  projection_results$intervention_pca,
  file.path(output_dir, paste0(disease_name, "_projection_pca.csv")),
  row.names = FALSE
)
write.csv(
  projection_results$intervention_cluster_df,
  file.path(output_dir, paste0(disease_name, "_projection_clusters.csv")),
  row.names = FALSE
)
write.csv(
  projection_results$cluster_df_all,
  file.path(output_dir, paste0(disease_name, "_projection_cluster_df_all.csv")),
  row.names = FALSE
)
save(
  projection_results,
  file = file.path(output_dir, paste0(disease_name, "_projection_results.RData"))
)
