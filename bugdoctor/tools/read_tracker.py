from __future__ import annotations

from pathlib import Path


class ReadTracker:
    """Tracks files read via read_file in the current session."""

    def __init__(self) -> None:
        self._read_paths: set[str] = set()

    def mark_read(self, path: Path) -> None:
        self._read_paths.add(str(path.resolve()))

    def has_read(self, path: Path) -> bool:
        return str(path.resolve()) in self._read_paths
