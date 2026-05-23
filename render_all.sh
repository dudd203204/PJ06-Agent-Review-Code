#!/bin/bash
# Render all Mermaid diagrams to PNG

cd /Users/dudd/Documents/nhu_agent/agent-check-code/diagrams

echo "========================================"
echo "Rendering Mermaid Diagrams to PNG"
echo "========================================"
echo

mmdc -i 01_batch_processing_flow.mmd -o 01_batch_processing_flow.png
echo "✓ 01_batch_processing_flow.png"

mmdc -i 02_architecture_overview.mmd -o 02_architecture_overview.png
echo "✓ 02_architecture_overview.png"

mmdc -i 03_policy_system_abac.mmd -o 03_policy_system_abac.png
echo "✓ 03_policy_system_abac.png"

mmdc -i 04_component_quality_checks.mmd -o 04_component_quality_checks.png
echo "✓ 04_component_quality_checks.png"

mmdc -i 05_tools_skills_architecture.mmd -o 05_tools_skills_architecture.png
echo "✓ 05_tools_skills_architecture.png"

mmdc -i 06_route_detection_workflow.mmd -o 06_route_detection_workflow.png
echo "✓ 06_route_detection_workflow.png"

echo
echo "========================================"
echo "✅ All diagrams rendered successfully!"
echo "========================================"
echo
echo "PNG Files:"
ls -lh *.png | awk '{print "  " $9 " (" $5 ")"}'
