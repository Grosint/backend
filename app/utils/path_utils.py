from __future__ import annotations

from pathlib import Path


def find_project_root(
    start_path: str | Path | None = None, marker_file_or_dir: str = ".git"
) -> Path | None:
    """
    Finds the project root by searching for a marker file or directory
    upwards from the given start_path.

    Args:
        start_path: Starting path to search from. If None, uses current file's directory.
        marker_file_or_dir: Marker to look for (e.g., ".git", "pyproject.toml", "requirements.txt")

    Returns:
        Path to project root if found, None otherwise
    """
    if start_path is None:
        # Default to current file's directory
        start_path = Path(__file__).parent
    else:
        start_path = Path(start_path).resolve()

    current_path = Path(start_path).resolve()

    # Stop at the file system root
    while current_path != current_path.parent:
        if (current_path / marker_file_or_dir).exists():
            return current_path
        current_path = current_path.parent

    return None  # Marker not found


def get_project_root(start_path: str | Path | None = None) -> Path:
    """
    Get the project root directory by searching for common markers.
    Tries multiple markers in order of preference.

    Args:
        start_path: Starting path to search from. If None, uses the caller's file location.

    Returns:
        Path to project root

    Raises:
        RuntimeError: If project root cannot be found
    """
    # Try multiple markers in order of preference
    markers = [".git", "pyproject.toml", "requirements.txt", "setup.py"]

    # If no start_path provided, try to get it from the caller's frame
    if start_path is None:
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            caller_file = frame.f_back.f_globals.get("__file__")
            if caller_file:
                start_path = Path(caller_file).parent
            else:
                # Fallback to utils directory
                start_path = Path(__file__).parent
        else:
            start_path = Path(__file__).parent

    for marker in markers:
        project_root = find_project_root(start_path, marker)
        if project_root:
            return project_root

    # If no marker found, raise an error
    raise RuntimeError(
        f"Could not find project root. Searched for: {', '.join(markers)}"
    )
