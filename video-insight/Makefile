.PHONY: install test test-cov lint server tools plugin-dev analyze annotate clean

# Install the package with dev dependencies
install:
	pip install -e ".[dev]"

# Run the full test suite (no video files or GPU required)
test:
	pytest tests/ -v

# Run tests with coverage report
test-cov:
	pytest tests/ -v --cov=src --cov-report=term-missing

# Syntax check all source files
lint:
	python3 -m py_compile src/video_analyzer.py src/server.py src/action_builder.py
	@echo "Syntax OK"

# Start the MCP server in stdio mode (for manual testing)
server:
	python3 src/server.py

# List all registered MCP tools
tools:
	python3 -c "\
import asyncio, sys; sys.path.insert(0, 'src'); \
from server import mcp; \
tools = asyncio.run(mcp.list_tools()); \
print(f'{len(tools)} tools registered:'); \
[print(f'  {t.name}') for t in tools]"

# Load the plugin locally for development (run from repo root)
plugin-dev:
	claude --plugin-dir .

# Analyze a video and print the manifest summary
# Usage: make analyze VIDEO=/path/to/video.mp4
analyze:
	@test -n "$(VIDEO)" || (echo "Usage: make analyze VIDEO=/path/to/video.mp4" && exit 1)
	python3 -c "\
import sys, json; sys.path.insert(0, 'src'); \
from video_analyzer import build_manifest; \
m = build_manifest('$(VIDEO)', './video_analysis'); \
s = m['summary']; meta = m['metadata']; \
print(f\"Type:       {meta['video_type']}\"); \
print(f\"Duration:   {meta['duration_seconds']}s\"); \
print(f\"Resolution: {meta['resolution']}\"); \
print(f\"Scenes:     {s['total_scenes']}\"); \
print(f\"Confidence: {s['avg_confidence']}\"); \
print(f\"Colors:     {s['dominant_colors']}\"); \
print(f\"Components: {s['ui_components_detected']}\"); \
print(f\"Manifest:   video_analysis/manifest.json\"); \
print(f\"Report:     video_analysis/report.html\")"

# Generate annotated debug frames for a video
# Usage: make annotate VIDEO=/path/to/video.mp4
annotate:
	@test -n "$(VIDEO)" || (echo "Usage: make annotate VIDEO=/path/to/video.mp4" && exit 1)
	python3 -c "\
import sys; sys.path.insert(0, 'src'); \
from video_analyzer import build_manifest; \
m = build_manifest('$(VIDEO)', './video_analysis'); \
for s in m['scenes']: \
    ann = s.get('annotated_frame_path', ''); \
    conf = s.get('confidence', {}).get('overall', 0); \
    print(f\"{s['id']}: conf={conf:.2f}  {ann}\")"

# Clean all generated output
clean:
	rm -rf video_analysis/ video_comparison/ output/ annotated/
	rm -rf __pycache__/ src/__pycache__/ tests/__pycache__/
	rm -rf .pytest_cache/ htmlcov/ .coverage
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
