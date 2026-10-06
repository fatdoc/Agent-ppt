"""Safe path helpers used by upload and MinerU file handling."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, Union


logger = logging.getLogger(__name__)
PathInput = Union[os.PathLike, str]


def is_path_within(path: PathInput, root: PathInput) -> bool:
    """Return whether ``path`` resolves inside ``root`` (symlinks included)."""
    try:
        real_root = os.path.realpath(os.fspath(root))
        real_path = os.path.realpath(os.fspath(path))
        return os.path.commonpath([real_path, real_root]) == real_root
    except (TypeError, ValueError, OSError):
        return False


def resolve_path_within(path: PathInput, root: PathInput) -> Path:
    """Resolve a path and reject traversal outside the supplied root."""
    resolved_root = Path(os.path.realpath(os.fspath(root)))
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = resolved_root / candidate
    resolved_path = Path(os.path.realpath(candidate))
    if not is_path_within(resolved_path, resolved_root):
        raise ValueError(f"Path escapes allowed root: {path}")
    return resolved_path


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_mineru_root(
    project_root: Optional[Path] = None,
    upload_folder: Optional[PathInput] = None,
) -> Path:
    if upload_folder is not None:
        upload_root = Path(upload_folder)
    elif project_root is not None:
        upload_root = project_root / "uploads"
    else:
        upload_root = None
        try:
            from flask import current_app, has_app_context

            if has_app_context():
                configured = current_app.config.get("UPLOAD_FOLDER")
                if configured:
                    upload_root = Path(configured)
        except (RuntimeError, ImportError, TypeError, AttributeError):
            pass

        if upload_root is None:
            configured = os.getenv("UPLOAD_FOLDER")
            upload_root = Path(configured) if configured else _default_project_root() / "uploads"

    if not upload_root.is_absolute():
        root = (project_root or _default_project_root()).resolve()
        upload_root = resolve_path_within(upload_root, root)

    return Path(os.path.realpath(upload_root)) / "mineru_files"


def convert_mineru_path_to_local(
    mineru_path: str,
    project_root: Optional[Path] = None,
    upload_folder: Optional[PathInput] = None,
) -> Optional[Path]:
    """Convert a ``/files/mineru/...`` URL to a contained local path."""
    try:
        if not mineru_path.startswith("/files/mineru/"):
            return None
        relative_path = mineru_path[len("/files/mineru/"):].lstrip("/\\")
        mineru_root = _resolve_mineru_root(project_root, upload_folder)
        return resolve_path_within(relative_path, mineru_root)
    except (OSError, TypeError, ValueError) as exc:
        logger.warning("Rejected MinerU path %s: %s", mineru_path, exc)
        return None


def find_mineru_file_with_prefix(
    mineru_path: str,
    project_root: Optional[Path] = None,
    upload_folder: Optional[PathInput] = None,
) -> Optional[Path]:
    """Find a MinerU file, retaining the legacy filename-prefix fallback."""
    local_path = convert_mineru_path_to_local(mineru_path, project_root, upload_folder)
    if local_path is None:
        return None

    mineru_root = _resolve_mineru_root(project_root, upload_folder)
    if local_path.is_file():
        return local_path if is_path_within(local_path, mineru_root) else None

    matched_path = find_file_with_prefix(local_path)
    if matched_path and is_path_within(matched_path, mineru_root):
        return Path(os.path.realpath(matched_path))
    return None


def find_file_with_prefix(file_path: Path) -> Optional[Path]:
    """Find an exact file or a same-extension filename with the requested prefix."""
    if file_path.is_file():
        return file_path

    filename = file_path.name
    directory = file_path.parent
    if "." not in filename or not directory.is_dir():
        return None

    prefix, extension = os.path.splitext(filename)
    if len(prefix) < 5:
        return None

    try:
        for name in os.listdir(directory):
            candidate_prefix, candidate_extension = os.path.splitext(name)
            if (
                candidate_prefix.lower().startswith(prefix.lower())
                and candidate_extension.lower() == extension.lower()
            ):
                candidate = directory / name
                if candidate.is_file():
                    logger.debug("Prefix match found: %s -> %s", file_path, candidate)
                    return candidate
    except OSError as exc:
        logger.warning("Failed to list directory %s: %s", directory, exc)
    return None
