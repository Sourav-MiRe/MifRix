from importlib.resources import files
from pathlib import Path

from mifrix.resources import resolve_resource_dir


def package_root() -> Path:
    return Path(str(files("mifrix.risk_scores")))


def packaged_resources_root() -> Path:
    return package_root() / "resources"


def resources_root(resource_dir=None) -> Path:
    unpacked = resolve_resource_dir(resource_dir) / "risk_scores" / "resources"
    if unpacked.exists():
        return unpacked
    return packaged_resources_root()


def tech_resources_root(tech: str, resource_dir=None) -> Path:
    tech = tech.upper()
    if tech not in {"AP", "FP"}:
        raise ValueError("tech must be 'AP' or 'FP'")
    return resources_root(resource_dir) / f"resources_{tech}"


def taxonomy_db_path(resource_dir=None) -> Path:
    return resources_root(resource_dir) / "taxonomy.sqlite"


def fp_rdata_path(resource_dir=None) -> Path:
    return resources_root(resource_dir) / "Fp_22022026.RData"


def r_script_path(name: str, resource_dir=None) -> Path:
    return resources_root(resource_dir) / name
