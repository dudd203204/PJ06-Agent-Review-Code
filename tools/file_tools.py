from __future__ import annotations

import json
import shutil
from pathlib import Path


def _resolve_inside(base_dir: Path, target: str) -> Path:
    """Resolve a path while preventing traversal outside base_dir."""
    base_dir = base_dir.resolve()
    candidate = Path(target)
    if not candidate.is_absolute():
        candidate = (base_dir / candidate).resolve()
    else:
        candidate = candidate.resolve()

    try:
        candidate.relative_to(base_dir)
    except ValueError as exc:
        raise ValueError(f"Path escapes project root: {target}")
    return candidate


def read_file_text(base_dir: Path, file_path: str) -> str:
    """Read a text file from the project safely."""
    path = _resolve_inside(base_dir, file_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    return path.read_text(encoding="utf-8")


def list_files(base_dir: Path, target_dir: str = ".", pattern: str = "**/*", max_results: int = 200) -> list[str]:
    """List files under target_dir using glob pattern."""
    root = _resolve_inside(base_dir, target_dir)
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Directory not found: {target_dir}")

    files = [
        str(path.relative_to(base_dir)).replace("\\", "/")
        for path in root.glob(pattern)
        if path.is_file()
    ]
    files.sort()
    return files[:max_results]


def ensure_directory(path: Path) -> Path:
    """Create a directory if it does not exist."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def collect_input_files(project_root: Path, input_root: Path, proceed_root: Path, appkey_filter: str | None = None) -> list[Path]:
    """
    Return input files from appkey subfolders.
    
    Structure: input/<appkey>/*.json
    Returns only files inside appkey subfolders, not at input root level.
    
    Args:
        project_root: Project root directory
        input_root: Input root directory
        proceed_root: Proceed directory for tracking
        appkey_filter: Optional specific appkey to process. If None, processes all appkeys.
    
    Returns:
        List of input file paths
    """
    input_root = ensure_directory(_resolve_inside(project_root, str(input_root)))
    proceed_root = ensure_directory(_resolve_inside(project_root, str(proceed_root)))

    files: list[Path] = []
    
    # Scan direct subfolders in input_root (these are appkey folders)
    for appkey_folder in input_root.iterdir():
        if not appkey_folder.is_dir() or appkey_folder.name.startswith("."):
            continue
        
        # Skip if appkey_filter is specified and this folder doesn't match
        if appkey_filter and appkey_folder.name != appkey_filter:
            continue
        
        # Collect .json files from this appkey folder
        for path in appkey_folder.glob("*.json"):
            if not path.is_file():
                continue
            if path.name.startswith("."):
                continue
            
            # Exclude files already in proceed folder
            try:
                path.relative_to(proceed_root)
                continue
            except ValueError:
                pass
            
            files.append(path)

    files.sort()
    return files


def mark_file_as_proceeding(proceed_root: Path, input_file: Path) -> Path:
    """Copy the current input file into the proceed directory as a runtime marker."""
    ensure_directory(proceed_root)
    marker_path = proceed_root / input_file.name
    shutil.copy2(input_file, marker_path)
    return marker_path


def clear_directory(path: Path) -> None:
    """Remove all contents from a directory while preserving the directory itself."""
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        return

    for child in path.iterdir():
        if child.is_file() and child.name == ".gitkeep":
            continue
        if child.is_dir():
            clear_directory(child)
            if not any(child.iterdir()):
                child.rmdir()
        else:
            child.unlink()


def write_output_file(output_root: Path, input_file, payload: dict, project_root: Path = None, input_root: Path = None, skills_root: Path = None, template_path: Path = None) -> Path:
    """
    Persist a JSON result in appkey-based folder structure.
    
    Creates structure: output/<appkey>/output_<type>_<timestamp>.json
    Also generates Excel output: output/<appkey>/output_<type>_<timestamp>.xlsx
    
    Expects input files to be in: input/<appkey>/<filename>.json
    Uses parent folder name as appkey.
    
    Args:
        output_root: Root output directory
        input_file: Path object for input file
        payload: Result payload dict
        project_root: Project root (optional)
        input_root: Input root directory (optional)
        skills_root: Path to skills directory for loading skill definitions
        template_path: Path to Excel template file
    
    Returns:
        Path to generated JSON output file
    """
    from datetime import datetime
    from .excel_generator import create_excel_output, load_skill_definitions
    
    ensure_directory(output_root)
    
    input_path = Path(input_file).resolve()
    
    # Extract app key from parent folder name
    # Expected structure: input/<appkey>/<file>.json
    # So appkey = input_path.parent.name
    app_key = input_path.parent.name
    
    # Determine type (backoffice or formio)
    input_name = input_path.name.lower()
    if "backoffice" in input_name:
        output_type = "backoffice"
    elif "formio" in input_name:
        output_type = "formio"
    else:
        # Try to infer from payload
        if payload.get("route") == "route_b":
            output_type = "backoffice"
        elif payload.get("route") == "route_a":
            output_type = "formio"
        else:
            output_type = "result"
    
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create appkey subdirectory
    appkey_dir = output_root / app_key
    ensure_directory(appkey_dir)
    
    # Generate output filename
    output_name = f"output_{output_type}_{timestamp}.json"
    output_path = appkey_dir / output_name
    
    # Write JSON file
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    
    # Generate Excel output (optional, best-effort)
    try:
        if skills_root is None and project_root:
            skills_root = project_root / "skills"
        
        if skills_root and skills_root.exists():
            skill_map = load_skill_definitions(skills_root)
            
            excel_name = f"output_{output_type}_{timestamp}.xlsx"
            excel_path = appkey_dir / excel_name
            
            create_excel_output(
                excel_path,
                payload,
                template_path=template_path,
                skill_map=skill_map
            )
    except Exception:
        # Silently fail Excel generation - JSON output is primary
        pass
    
    return output_path


def make_file_tools(project_root: Path):
    """Build LangChain-compatible file tools."""
    from langchain_core.tools import tool

    @tool("read_project_file")
    def read_project_file(file_path: str) -> str:
        """Read a UTF-8 text file from the project root."""
        return read_file_text(project_root, file_path)

    @tool("list_project_files")
    def list_project_files(target_dir: str = ".", pattern: str = "**/*", max_results: int = 100) -> str:
        """List project files under a directory and return JSON array."""
        files = list_files(project_root, target_dir=target_dir, pattern=pattern, max_results=max_results)
        return json.dumps(files, indent=2)

    return [read_project_file, list_project_files]
