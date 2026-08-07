from importlib.resources import files
from pathlib import Path

from mifrix.resources import resolve_resource_dir


def package_root() -> Path:
    return Path(str(files("mifrix.shap")))


def packaged_resources_root() -> Path:
    return package_root() / "resources"


def resources_root(resource_dir=None) -> Path:
    unpacked = resolve_resource_dir(resource_dir) / "shap" / "resources"
    if unpacked.exists():
        return unpacked
    return packaged_resources_root()


def default_shap_train_root(resource_dir=None) -> Path:
    return resources_root(resource_dir) / "shap_train"


def projection_pca_results_path(resource_dir=None) -> Path:
    return resources_root(resource_dir) / "projection" / "Projection_PCA_results.RData"


def tech_shap_root(tech: str, shap_train_root=None, resource_dir=None) -> Path:
    tech = tech.upper()
    if tech != "AP":
        raise ValueError("tech must be 'AP'")
    root = Path(shap_train_root) if shap_train_root else default_shap_train_root(resource_dir)
    return root / tech / "Importances_tree_linear_aggregated_alltrain_eval_alltrain"
