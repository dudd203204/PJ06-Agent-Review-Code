"""Generate Excel output from review results."""

import json
from pathlib import Path
from typing import Any, Optional

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.cell.cell import MergedCell


def load_skill_definitions(skills_root: Path) -> dict[str, dict[str, dict[str, Any]]]:
    """
    Load all skill definitions organized by skill file name.
    
    Handles both skill array and skill dict structures.
    
    Returns dict: {
        "review_back_office": {
            "B1": {"review_item": "Form.io staging...", "category": "Back office"},
            "B2": {...},
            ...
        },
        "component_quality": {
            "A1": {"review_item": "Camel case...", "category": "Component"},
            ...
        }
    }
    """
    skill_map_by_file = {}
    
    if not skills_root.exists():
        return skill_map_by_file
    
    # Scan all skill JSON files recursively
    for skill_file in sorted(skills_root.rglob("*.json")):
        if skill_file.name == "description.json" or skill_file.name == "skill_registry.json":
            continue
        
        try:
            with open(skill_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, dict):
                continue
            
            category = data.get('category', '')
            skill_section = data.get('skill', {})
            
            # Build filename key (e.g., "review_back_office", "field_logic_quality")
            file_key = skill_file.stem  # removes .json extension
            skill_map = {}
            
            # Handle skill as array (e.g., backoffice)
            if isinstance(skill_section, list):
                for skill_item in skill_section:
                    if isinstance(skill_item, dict):
                        skill_id = skill_item.get('id')
                        review_item = skill_item.get('review_item', '')
                        
                        if skill_id:
                            skill_map[skill_id] = {
                                'review_item': review_item,
                                'description': skill_item.get('description', ''),
                                'category': category
                            }
            
            # Handle skill as dict (e.g., form_quality files)
            elif isinstance(skill_section, dict):
                for skill_id, skill_item in skill_section.items():
                    if isinstance(skill_item, dict):
                        review_item = skill_item.get('review_item', '')
                        
                        if skill_id:
                            skill_map[skill_id] = {
                                'review_item': review_item,
                                'description': skill_item.get('description', ''),
                                'category': category
                            }
            
            if skill_map:
                skill_map_by_file[file_key] = skill_map
        
        except Exception as e:
            # Skip files with parsing errors
            continue
    
    return skill_map_by_file


def get_review_item_name(evidence_key: str, skill_id: str, skill_map_by_file: dict) -> str:
    """Get review item name from skill map based on skill_id, fallback to key.
    
    Args:
        evidence_key: The evidence ID (e.g., "B1", "A1")
        skill_id: The skill name (e.g., "review_back_office", "field_logic_quality")
        skill_map_by_file: Hierarchical skill map organized by skill file name
    
    Returns:
        Review item name or fallback to evidence_key
    """
    if skill_id in skill_map_by_file:
        skill_map = skill_map_by_file[skill_id]
        if evidence_key in skill_map:
            return skill_map[evidence_key].get('review_item', evidence_key)
    
    return evidence_key


def flatten_evidence(payload: dict) -> list[tuple[str, str, str, str]]:
    """
    Flatten evidence from JSON output with skill context.
    
    Returns list of (skill_id, evidence_key, status, note) tuples.
    skill_id: e.g., "review_back_office", "field_logic_quality"
    evidence_key: e.g., "B1", "A1"
    status: "PASSED" or "FAILED"
    note: Feedback text
    """
    results = []
    
    checks = payload.get('checks', [])
    for check in checks:
        skill_id = check.get('skill_id', 'unknown')
        evidence = check.get('evidence', {})
        
        # Handle None or missing evidence
        if evidence is None:
            evidence = {}
        
        for evidence_key, evidence_value in evidence.items():
            if isinstance(evidence_value, dict):
                status = evidence_value.get('Status', '')
                note = evidence_value.get('Note / Feedback', '')
                results.append((skill_id, evidence_key, status, note))
    
    return results


def create_excel_output(
    output_path: Path,
    payload: dict,
    template_path: Optional[Path] = None,
    skill_map: Optional[dict] = None
) -> Path:
    """
    Create Excel output from JSON payload.
    
    Args:
        output_path: Path to write Excel file
        payload: JSON review output payload
        template_path: Path to template Excel file (optional, not used due to merged cells)
        skill_map: Pre-loaded skill mapping organized by file name (optional)
    
    Returns:
        Path to created Excel file
    """
    # Load skill map if not provided
    if skill_map is None:
        skill_map = {}
    
    # Create new workbook from scratch (avoid merged cell issues)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Review Results"
    
    # Add title rows
    ws['A1'] = 'Review Results'
    title_font = Font(size=14, bold=True)
    ws['A1'].font = title_font
    
    # Add headers at row 3
    ws['A3'] = 'Skill ID'
    ws['B3'] = 'Review Items'
    ws['C3'] = 'Status'
    ws['D3'] = 'Note / Feedback'
    
    # Style headers
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    for cell_ref in ['A3', 'B3', 'C3', 'D3']:
        cell = ws[cell_ref]
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    
    # Flatten evidence data
    evidence_data = flatten_evidence(payload)
    
    # Write data starting from row 4
    start_row = 4
    for idx, (skill_id, evidence_key, status, note) in enumerate(evidence_data):
        row = start_row + idx
        
        # Get review item name based on skill context
        review_item = get_review_item_name(evidence_key, skill_id, skill_map)
        
        # Write data
        ws[f'A{row}'] = evidence_key
        ws[f'B{row}'] = review_item
        ws[f'C{row}'] = status
        ws[f'D{row}'] = note
        
        # Style cells
        # Status color coding
        if status.upper() == 'PASSED':
            fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
            font = Font(color="006100")
        elif status.upper() == 'FAILED':
            fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
            font = Font(color="9C0006")
        else:
            fill = None
            font = Font()
        
        # Apply styling to status column
        ws[f'C{row}'].fill = fill
        ws[f'C{row}'].font = font
        ws[f'C{row}'].alignment = Alignment(horizontal='center', vertical='center')
        
        # Apply wrapping to text columns
        ws[f'B{row}'].alignment = Alignment(wrap_text=True, vertical='top')
        ws[f'D{row}'].alignment = Alignment(wrap_text=True, vertical='top')
        
        # Add borders to all data cells
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        for col in ['A', 'B', 'C', 'D']:
            ws[f'{col}{row}'].border = thin_border
    
    # Adjust column widths
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 45
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 50
    
    # Set row height for title
    ws.row_dimensions[1].height = 20
    ws.row_dimensions[3].height = 25
    
    # Freeze header rows
    ws.freeze_panes = 'A4'
    
    # Save workbook
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    
    return output_path
