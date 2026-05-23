from __future__ import annotations

from pathlib import Path


def resolve_policy_storage_root(root_path: Path) -> Path:
    """Resolve the policy storage folder from a file or directory path."""
    path = Path(root_path)
    if path.is_file():
        return path.parent
    if (path / "storage").exists():
        return path / "storage"
    return path


def iter_policy_json_files(storage_root: Path) -> tuple[Path, ...]:
    """Return ordered policy JSON files that define active policy state."""
    root = resolve_policy_storage_root(storage_root)
    file_paths: list[Path] = []

    base_path = root / "base.json"
    if base_path.exists():
        file_paths.append(base_path)

    for folder_name in ("principals", "by_type"):
        folder_path = root / folder_name
        if not folder_path.exists():
            continue
        file_paths.extend(sorted(folder_path.glob("*.json")))

    return tuple(file_paths)


def compute_policy_fingerprint(storage_root: Path) -> tuple[tuple[str, int, int], ...]:
    """Compute deterministic fingerprint from policy file metadata."""
    root = resolve_policy_storage_root(storage_root)
    fingerprint: list[tuple[str, int, int]] = []
    for file_path in iter_policy_json_files(root):
        stats = file_path.stat()
        fingerprint.append(
            (
                file_path.relative_to(root).as_posix(),
                int(stats.st_mtime_ns),
                int(stats.st_size),
            )
        )
    return tuple(fingerprint)
