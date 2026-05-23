#!/usr/bin/env python3
"""
Render Mermaid diagrams to PNG using mermaid.ink service
"""
import os
import base64
import urllib.request
import json

diagrams_dir = "/Users/dudd/Documents/nhu_agent/agent-check-code/diagrams"

# List of mermaid files to render
diagram_files = [
    "01_batch_processing_flow.mmd",
    "02_architecture_overview.mmd",
    "03_policy_system_abac.mmd",
    "04_component_quality_checks.mmd",
    "05_tools_skills_architecture.mmd",
    "06_route_detection_workflow.mmd"
]

def render_mermaid_to_png(mmd_file, output_png):
    """Render mermaid file to PNG using mermaid.ink"""
    
    # Read mermaid file
    mmd_path = os.path.join(diagrams_dir, mmd_file)
    with open(mmd_path, 'r', encoding='utf-8') as f:
        diagram_code = f.read()
    
    print(f"Processing: {mmd_file}...")
    
    try:
        # Encode diagram code to base64 (for URL-safe embedding)
        encoded = base64.b64encode(diagram_code.encode('utf-8')).decode('utf-8')
        
        # Use mermaid.ink service to render
        # Note: mermaid.ink has size limits, so we'll try multiple approaches
        
        # Approach 1: Try using mermaid.ink direct render
        url = f"https://mermaid.ink/img/{encoded}"
        
        output_path = os.path.join(diagrams_dir, output_png)
        
        # Download and save
        print(f"  → Downloading from mermaid.ink...")
        urllib.request.urlretrieve(url, output_path)
        
        # Check file size
        size_kb = os.path.getsize(output_path) / 1024
        print(f"  ✓ Saved: {output_png} ({size_kb:.1f} KB)")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {str(e)}")
        return False

# Render all diagrams
print("=" * 60)
print("RENDERING MERMAID DIAGRAMS TO PNG")
print("=" * 60)
print()

success_count = 0
for mmd_file in diagram_files:
    png_file = mmd_file.replace('.mmd', '.png')
    if render_mermaid_to_png(mmd_file, png_file):
        success_count += 1
    print()

print("=" * 60)
print(f"Result: {success_count}/{len(diagram_files)} diagrams rendered successfully")
print("=" * 60)
print()

# List generated PNG files
print("Generated PNG files:")
png_files = [f for f in os.listdir(diagrams_dir) if f.endswith('.png')]
for png_file in sorted(png_files):
    png_path = os.path.join(diagrams_dir, png_file)
    size_kb = os.path.getsize(png_path) / 1024
    print(f"  ✓ {png_file} ({size_kb:.1f} KB)")
