import argparse
import io
import os
import tarfile
from importlib.resources import files
from pathlib import Path


ENV_RESOURCE_DIR = "MIFRIX_RESOURCE_DIR"
ARCHIVE_NAME = "mifrix_resources.tar.gz"
ARCHIVE_PART_PATTERN = f"{ARCHIVE_NAME}.part*"


def default_user_resource_dir() -> Path:
    return Path.home() / ".mifrix" / "resources"


def packaged_archive_path() -> Path:
    return Path(str(files("mifrix"))) / "resource_archives" / ARCHIVE_NAME


def packaged_archive_part_paths() -> list[Path]:
    archive_dir = Path(str(files("mifrix"))) / "resource_archives"
    return sorted(archive_dir.glob(ARCHIVE_PART_PATTERN))


def resolve_resource_dir(resource_dir=None) -> Path:
    if resource_dir:
        return Path(resource_dir).expanduser().resolve()

    env_value = os.environ.get(ENV_RESOURCE_DIR)
    if env_value:
        return Path(env_value).expanduser().resolve()

    return default_user_resource_dir()


def unpack_resources(output_dir=None, force=False) -> Path:
    destination = resolve_resource_dir(output_dir)
    archive = packaged_archive_path()
    archive_parts = packaged_archive_part_paths()

    if not archive.exists() and not archive_parts:
        raise FileNotFoundError(
            f"Packaged MifRix resource archive was not found: {archive} "
            f"or split parts matching {ARCHIVE_PART_PATTERN}"
        )

    marker = destination / ".mifrix_resources_unpacked"
    if marker.exists() and not force:
        return destination

    destination.mkdir(parents=True, exist_ok=True)
    if archive.exists():
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(destination)
    else:
        tar_source = io.BufferedReader(_JoinedArchiveParts(archive_parts))
        with tarfile.open(fileobj=tar_source, mode="r|gz") as tar:
            tar.extractall(destination)

    marker.write_text(f"{ARCHIVE_NAME}\n")
    return destination


class _JoinedArchiveParts(io.RawIOBase):
    def __init__(self, paths):
        self.paths = list(paths)
        self.index = 0
        self.current = None

    def readable(self):
        return True

    def close(self):
        if self.current is not None:
            self.current.close()
        super().close()

    def _open_next(self):
        if self.current is not None:
            self.current.close()
            self.current = None
        if self.index >= len(self.paths):
            return False
        self.current = self.paths[self.index].open("rb")
        self.index += 1
        return True

    def readinto(self, b):
        view = memoryview(b)
        total = 0
        while total < len(view):
            if self.current is None and not self._open_next():
                break
            n = self.current.readinto(view[total:])
            if n is None:
                break
            if n == 0:
                if not self._open_next():
                    break
                continue
            total += n
        return total


def build_parser():
    parser = argparse.ArgumentParser(description="Unpack MifRix model and data resources.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help=f"Directory to unpack resources into. Defaults to ${ENV_RESOURCE_DIR} or ~/.mifrix/resources.",
    )
    parser.add_argument("--force", action="store_true", help="Unpack even if resources were already marked as unpacked.")
    return parser


def main():
    args = build_parser().parse_args()
    destination = unpack_resources(output_dir=args.output_dir, force=args.force)
    print(f"MifRix resources are ready at: {destination}")
    print(f"Set {ENV_RESOURCE_DIR}={destination} or pass --resource-dir {destination} to MifRix commands.")


if __name__ == "__main__":
    main()
