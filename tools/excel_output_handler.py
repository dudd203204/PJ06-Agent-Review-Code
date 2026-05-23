"""Excel output handler for extracting application keys and processing output files."""

import json
from pathlib import Path
from typing import Union


def extract_app_key(input_file: Union[str, Path], project_root: Path = None) -> str:
    """
    Extract application key from input JSON file.
    
    For backoffice/application files: looks for 'application.key'
    For other files (formio forms): generates key from filename
    
    Args:
        input_file: Path to input JSON file (absolute or relative)
        project_root: Project root directory (for context)
    
    Returns:
        Application key string
    """
    try:
        input_path = Path(input_file)
        
        # Resolve to absolute path if needed
        if not input_path.is_absolute() and project_root:
            input_path = project_root / input_path
        
        # If file exists and is a JSON file, try to extract app key
        if input_path.exists() and input_path.suffix == '.json':
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # ONLY look for application.key in application/backoffice format
                if isinstance(data, dict) and 'application' in data:
                    app_key = data.get('application', {}).get('key')
                    if app_key:
                        return app_key
        
        # Fallback: generate key from filename (for formio and other files)
        # Remove extension and sanitize
        filename = input_path.stem  # filename without extension
        app_key = filename.replace('-', '_').replace(' ', '_').upper()
        return app_key if app_key else 'DEFAULT_APP'
        
    except Exception:
        # Ultimate fallback
        return 'DEFAULT_APP'


def get_output_type(payload: dict, input_file: str) -> str:
    """
    Determine output type based on payload and input filename.
    
    Args:
        payload: Result payload dictionary
        input_file: Input filename
    
    Returns:
        Output type string ('backoffice', 'formio', or 'result')
    """
    input_name = str(input_file).lower()
    
    if 'backoffice' in input_name:
        return 'backoffice'
    elif 'formio' in input_name:
        return 'formio'
    
    # Infer from payload route
    route = payload.get('route', '')
    if route == 'route_b':
        return 'backoffice'
    elif route == 'route_a':
        return 'formio'
    
    return 'result'
