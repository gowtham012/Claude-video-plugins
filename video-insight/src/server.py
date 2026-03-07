"""
FastMCP server — Video Understanding Plugin

Tools:
  1.  analyze_video              — full pipeline: metadata + scenes + OCR + colors + motion + burst + cursor + scroll + loading + confidence
  2.  build_frontend_from_video  — analyze + return everything for Claude to generate frontend code
  3.  extract_colors             — pull design token palette from a video
  4.  design_spec                — full design spec (tokens, components, diffs, spacing hints)
  5.  write_copy                 — extract all text content + narration from a video
  6.  describe_3d                — tuned manifest for 3D walkthroughs
  7.  generate_tests             — screen recording → Playwright/Cypress test file context
  8.  export_tokens              — colors → tailwind.config.js / CSS variables / Figma tokens
  9.  user_flow                  — infer step-by-step user journey from a recording
  10. generate_animations        — burst frames + motion → CSS @keyframes / Framer Motion
  11. watch_directory            — watch a folder and auto-analyze new video files
  12. generate_report            — self-contained HTML visual report
  13. generate_prd               — product requirements document context
  14. compare_videos             — structural A/B diff between two recordings
  15. generate_storybook         — Storybook stories for every detected UI component
  16. generate_changelog         — user-facing changelog from before/after recordings
  17. annotate_video             — debug frames with OCR boxes, cursor, diff regions, confidence
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP, Context

try:
    from .video_analyzer import (
        build_manifest, extract_color_palette, compute_video_hash,
        generate_html_report, _merge_palettes, compute_scene_diff,
    )
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.video_analyzer import (
        build_manifest, extract_color_palette, compute_video_hash,
        generate_html_report, _merge_palettes, compute_scene_diff,
    )

mcp = FastMCP(
    name="video-insight",
    instructions=(
        "Tools for deeply understanding video recordings. "
        "analyze_video extracts the full manifest (scenes, OCR, colors, burst frames, motion). "
        "Claude Code then uses that context to generate code, specs, copy, or descriptions."
    ),
)


# ---------------------------------------------------------------------------
# Helper: strip b64 from manifest for MCP response
# ---------------------------------------------------------------------------

def _slim_manifest(manifest: dict) -> dict:
    """Remove large b64 blobs from manifest for MCP transport. Claude reads images via keyframe_path."""
    import copy
    m = copy.deepcopy(manifest)
    for scene in m.get("scenes", []):
        scene["keyframe_b64"] = "<see keyframe_path>"
        for bf in scene.get("burst_frames", []):
            bf["b64"] = "<see path>"
    return m


# ---------------------------------------------------------------------------
# Tool 1: analyze_video
# ---------------------------------------------------------------------------

@mcp.tool()
async def analyze_video(
    video_path: str,
    output_dir: str = "./video_analysis",
    ctx: Context = None,
) -> dict[str, Any]:
    """
    Analyze a video and produce a rich structured manifest.

    Extracts (in parallel):
    - Metadata + auto video_type classification
    - Smart keyframes at scene-change boundaries
    - Burst frames inside high-motion scenes
    - Audio transcript with timestamps
    - OCR text per scene (threshold 0.25)
    - Dominant color palette per scene + global palette
    - Font/typography hints per scene
    - Motion detection with type: animation / scroll / cut / none
    - Scene diffs (what changed between consecutive scenes)
    - UI component detection

    Also generates report.html — a visual HTML report of the full analysis.

    Args:
        video_path: Path to video file (.mp4, .mov, .webm, etc.)
        output_dir: Directory to save keyframes, burst frames, manifest.json, report.html
    """
    video_path = str(Path(video_path).expanduser().resolve())
    if not os.path.exists(video_path):
        return {"error": f"Video file not found: {video_path}"}

    output_dir = str(Path(output_dir).expanduser().resolve())

    # Progress callback → streams updates to Claude Code
    stage_labels = {
        "metadata": "Extracting metadata",
        "transcript": "Transcribing audio",
        "scenes": "Detecting scenes",
        "enriching": "Analyzing frames (parallel)",
        "finalizing": "Finalizing manifest",
        "done": "Complete",
    }

    async def _progress(stage: str, current: int, total: int) -> None:
        if ctx:
            label = stage_labels.get(stage, stage)
            try:
                await ctx.report_progress(current, total, label)
            except Exception:
                pass

    def _sync_progress(stage: str, current: int, total: int) -> None:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_progress(stage, current, total))
        except Exception:
            pass

    manifest = build_manifest(video_path, output_dir, progress_callback=_sync_progress)

    # Generate HTML report
    report_path = generate_html_report(manifest, output_dir)

    return {
        "status": "success",
        "manifest_path": str(Path(output_dir) / "manifest.json"),
        "report_path": report_path,
        "manifest": _slim_manifest(manifest),
        "keyframes_dir": str(Path(output_dir) / "frames"),
        "burst_frames_dir": str(Path(output_dir) / "burst"),
        "typography": manifest.get("typography", []),
        "instructions": (
            "Read keyframe images from keyframes_dir and burst frames from burst_frames_dir. "
            "Use color_palette hex codes directly. "
            "typography gives font size classes and weight hints. "
            "motion_type: 'animation'→CSS transitions, 'scroll'→smooth scroll, 'cut'→instant. "
            "Open report_path in browser for a full visual overview."
        ),
    }


# ---------------------------------------------------------------------------
# Tool 2: build_frontend_from_video
# ---------------------------------------------------------------------------

@mcp.tool()
def build_frontend_from_video(
    video_path: str,
    framework: str = "react",
    output_dir: str = "./output",
) -> dict[str, Any]:
    """
    Analyze a video and return full context for Claude to generate frontend code.

    Returns manifest with keyframes, burst frames, exact color hex codes, OCR text,
    and motion types. Claude Code generates and saves the actual code files.

    Args:
        video_path: Path to video file
        framework: "react" (App.jsx + App.css) or "html" (index.html)
        output_dir: Where Claude should save the generated files
    """
    video_path = str(Path(video_path).expanduser().resolve())
    if not os.path.exists(video_path):
        return {"error": f"Video file not found: {video_path}"}

    framework = framework.lower().strip()
    if framework not in ("react", "html"):
        return {"error": f"framework must be 'react' or 'html', got: {framework!r}"}

    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    analysis_dir = str(output_path / "_analysis")

    manifest = build_manifest(video_path, analysis_dir)
    palette = manifest.get("color_palette", [])
    color_vars = "\n".join(f"  {c['hex']}  ({round(c['proportion']*100)}% of screen)" for c in palette[:6])

    if framework == "react":
        task = (
            f"Generate React (App.jsx + App.css) replicating the UI in this video.\n"
            f"EXACT colors to use (from color extraction — do not guess):\n{color_vars}\n"
            f"- Use OCR text verbatim for all labels, headings, CTAs\n"
            f"- motion_type='animation' → add CSS transitions\n"
            f"- motion_type='scroll' → smooth-scroll behaviour\n"
            f"- Burst frames show animation states — use them for hover/active states\n"
            f"- Save App.jsx and App.css to: {output_path}"
        )
    else:
        task = (
            f"Generate a self-contained index.html replicating the UI in this video.\n"
            f"EXACT colors to use (from color extraction — do not guess):\n{color_vars}\n"
            f"- Use OCR text verbatim for all labels, headings, CTAs\n"
            f"- motion_type='animation' → add CSS transitions\n"
            f"- motion_type='scroll' → smooth-scroll behaviour\n"
            f"- Burst frames show animation states — use them for hover/active states\n"
            f"- Inline all CSS/JS — save to: {output_path / 'index.html'}"
        )

    return {
        "status": "success",
        "framework": framework,
        "output_dir": str(output_path),
        "manifest": _slim_manifest(manifest),
        "keyframes_dir": str(Path(analysis_dir) / "frames"),
        "burst_frames_dir": str(Path(analysis_dir) / "burst"),
        "task": task,
    }


# ---------------------------------------------------------------------------
# Tool 3: extract_colors
# ---------------------------------------------------------------------------

@mcp.tool()
def extract_colors(
    video_path: str,
    output_dir: str = "./video_analysis",
) -> dict[str, Any]:
    """
    Extract a complete design token color palette from a video.

    Returns hex codes, RGB values, and proportion for every dominant color across
    all scenes. Useful for replicating design systems, dark/light mode palettes,
    or brand color extraction.

    Args:
        video_path: Path to video file
        output_dir: Directory to save keyframes and manifest
    """
    video_path = str(Path(video_path).expanduser().resolve())
    if not os.path.exists(video_path):
        return {"error": f"Video file not found: {video_path}"}

    output_dir = str(Path(output_dir).expanduser().resolve())
    manifest = build_manifest(video_path, output_dir)

    global_palette = manifest.get("color_palette", [])

    # Per-scene palettes for light/dark variant detection
    scene_palettes = {
        s["id"]: s["color_palette"]
        for s in manifest["scenes"]
    }

    # Detect if video has light + dark variants
    has_dark = any(
        any(sum(c["rgb"]) < 150 and c["proportion"] > 0.2 for c in p)
        for p in scene_palettes.values()
    )
    has_light = any(
        any(sum(c["rgb"]) > 600 and c["proportion"] > 0.2 for c in p)
        for p in scene_palettes.values()
    )

    return {
        "status": "success",
        "global_palette": global_palette,
        "scene_palettes": scene_palettes,
        "has_dark_mode": has_dark,
        "has_light_mode": has_light,
        "video_type": manifest["metadata"]["video_type"],
        "instructions": (
            "global_palette contains hex codes sorted by screen dominance. "
            "Use these directly in CSS — no need to eyeball colors from images. "
            "scene_palettes lets you compare palettes across scenes to identify "
            "dark/light mode color sets or state changes."
        ),
    }


# ---------------------------------------------------------------------------
# Tool 4: design_spec
# ---------------------------------------------------------------------------

@mcp.tool()
def design_spec(
    video_path: str,
    output_dir: str = "./video_analysis",
) -> dict[str, Any]:
    """
    Generate a full design specification from a video.

    Returns a structured spec with:
    - Color tokens (background, surface, accent, text per scene)
    - All OCR text organized by scene (headings, labels, CTAs)
    - Motion inventory (which scenes have animations and what type)
    - Component inventory hint (Claude infers from keyframes)
    - Burst frames for each animated scene

    Args:
        video_path: Path to video file
        output_dir: Directory to save analysis files
    """
    video_path = str(Path(video_path).expanduser().resolve())
    if not os.path.exists(video_path):
        return {"error": f"Video file not found: {video_path}"}

    output_dir = str(Path(output_dir).expanduser().resolve())
    manifest = build_manifest(video_path, output_dir)

    # Build organized spec
    color_tokens = _infer_color_tokens(manifest)
    text_inventory = {
        s["id"]: {
            "timestamp": f"{s['start']}s–{s['end']}s",
            "text": s["detected_text"],
            "narration": s["transcript_overlap"],
        }
        for s in manifest["scenes"]
    }
    motion_inventory = [
        {
            "scene": s["id"],
            "timestamp": f"{s['start']}s–{s['end']}s",
            "motion_type": s["motion_type"],
            "motion_level": s["motion_level"],
            "burst_frame_count": len(s.get("burst_frames", [])),
            "burst_frame_paths": [bf["path"] for bf in s.get("burst_frames", [])],
        }
        for s in manifest["scenes"] if s["motion_detected"]
    ]

    return {
        "status": "success",
        "video_type": manifest["metadata"]["video_type"],
        "duration": manifest["metadata"]["duration_seconds"],
        "resolution": manifest["metadata"]["resolution"],
        "color_tokens": color_tokens,
        "text_inventory": text_inventory,
        "motion_inventory": motion_inventory,
        "global_palette": manifest.get("color_palette", []),
        "keyframes_dir": str(Path(output_dir) / "frames"),
        "burst_frames_dir": str(Path(output_dir) / "burst"),
        "total_scenes": len(manifest["scenes"]),
        "instructions": (
            "Read keyframe images and burst frame images to identify components. "
            "color_tokens gives you semantic color assignments (background/surface/accent/text). "
            "motion_inventory tells you exactly where to add transitions and what kind. "
            "text_inventory gives you exact copy per scene — use it verbatim."
        ),
    }


# ---------------------------------------------------------------------------
# Tool 5: write_copy
# ---------------------------------------------------------------------------

@mcp.tool()
def write_copy(
    video_path: str,
    output_dir: str = "./video_analysis",
) -> dict[str, Any]:
    """
    Extract all text content from a video — OCR text + narration transcript.

    Useful for replicating marketing copy, UI labels, product descriptions,
    or any text visible or spoken in the video.

    Args:
        video_path: Path to video file
        output_dir: Directory to save analysis files
    """
    video_path = str(Path(video_path).expanduser().resolve())
    if not os.path.exists(video_path):
        return {"error": f"Video file not found: {video_path}"}

    output_dir = str(Path(output_dir).expanduser().resolve())
    manifest = build_manifest(video_path, output_dir)

    # All visible text, deduplicated, in order of appearance
    seen = set()
    ordered_text = []
    for scene in manifest["scenes"]:
        for t in scene["detected_text"]:
            if t not in seen:
                seen.add(t)
                ordered_text.append({"text": t, "first_seen": scene["id"], "timestamp": scene["start"]})

    full_transcript = " ".join(s["text"] for s in manifest["transcript"]).strip()

    return {
        "status": "success",
        "video_type": manifest["metadata"]["video_type"],
        "has_audio": manifest["metadata"]["has_audio"],
        "visible_text": ordered_text,
        "full_transcript": full_transcript,
        "transcript_segments": manifest["transcript"],
        "text_per_scene": {
            s["id"]: {
                "timestamp": f"{s['start']}s–{s['end']}s",
                "visible": s["detected_text"],
                "narration": s["transcript_overlap"],
            }
            for s in manifest["scenes"]
        },
        "instructions": (
            "visible_text contains all OCR-extracted text in order of appearance. "
            "full_transcript contains the complete narration. "
            "Use these verbatim — do not invent or paraphrase copy."
        ),
    }


# ---------------------------------------------------------------------------
# Tool 6: describe_3d
# ---------------------------------------------------------------------------

@mcp.tool()
def describe_3d(
    video_path: str,
    output_dir: str = "./video_analysis",
) -> dict[str, Any]:
    """
    Analyze a 3D design / walkthrough video.

    Returns keyframes, burst frames for camera movement scenes, color palette,
    and motion analysis tuned for 3D content (camera_pan, orbit, zoom, cut).
    Claude Code then describes geometry, materials, lighting, and camera path.

    Args:
        video_path: Path to video file (3D render, CAD walkthrough, game engine recording)
        output_dir: Directory to save analysis files
    """
    video_path = str(Path(video_path).expanduser().resolve())
    if not os.path.exists(video_path):
        return {"error": f"Video file not found: {video_path}"}

    output_dir = str(Path(output_dir).expanduser().resolve())
    manifest = build_manifest(video_path, output_dir)

    # Remap motion types for 3D context
    for scene in manifest["scenes"]:
        mt = scene["motion_type"]
        if mt == "animation":
            scene["camera_movement"] = "orbit_or_pan"
        elif mt == "scroll":
            scene["camera_movement"] = "dolly_or_zoom"
        elif mt == "cut":
            scene["camera_movement"] = "camera_cut"
        else:
            scene["camera_movement"] = "static"

    return {
        "status": "success",
        "video_type": "3d_walkthrough",
        "duration": manifest["metadata"]["duration_seconds"],
        "resolution": manifest["metadata"]["resolution"],
        "total_scenes": len(manifest["scenes"]),
        "keyframes_dir": str(Path(output_dir) / "frames"),
        "burst_frames_dir": str(Path(output_dir) / "burst"),
        "global_palette": manifest.get("color_palette", []),
        "scenes": [
            {
                "id": s["id"],
                "timestamp": f"{s['start']}s–{s['end']}s",
                "keyframe_path": s["keyframe_path"],
                "camera_movement": s.get("camera_movement", "static"),
                "motion_level": s["motion_level"],
                "burst_frame_paths": [bf["path"] for bf in s.get("burst_frames", [])],
                "colors": s["color_palette"],
            }
            for s in manifest["scenes"]
        ],
        "instructions": (
            "Read every keyframe and burst frame. "
            "For each scene describe: geometry visible, materials/textures, lighting, "
            "camera_movement type, and any notable design details. "
            "Use color palette to describe material colors precisely."
        ),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _infer_color_tokens(manifest: dict) -> dict[str, Any]:
    """
    Map extracted colors to semantic design tokens.
    Heuristic: darkest dominant → background, next → surface, most colorful → accent.
    """
    palette = manifest.get("color_palette", [])
    if not palette:
        return {}

    def luminance(c):
        r, g, b = c["rgb"]
        return 0.299 * r + 0.587 * g + 0.114 * b

    def saturation(c):
        r, g, b = [x / 255 for x in c["rgb"]]
        mx, mn = max(r, g, b), min(r, g, b)
        return (mx - mn) / mx if mx > 0 else 0

    sorted_by_lum = sorted(palette, key=luminance)
    sorted_by_sat = sorted(palette, key=saturation, reverse=True)

    tokens: dict[str, Any] = {}
    if sorted_by_lum:
        tokens["background"] = sorted_by_lum[0]["hex"]
    if len(sorted_by_lum) > 1:
        tokens["surface"] = sorted_by_lum[1]["hex"]
    if len(sorted_by_lum) > 2:
        tokens["text"] = sorted_by_lum[-1]["hex"]
    if sorted_by_sat:
        tokens["accent"] = sorted_by_sat[0]["hex"]
    if len(sorted_by_sat) > 1:
        tokens["accent_secondary"] = sorted_by_sat[1]["hex"]

    return tokens


# ---------------------------------------------------------------------------
# Tool 7: generate_tests
# ---------------------------------------------------------------------------

@mcp.tool()
def generate_tests(
    video_path: str,
    framework: str = "playwright",
    output_dir: str = "./video_analysis",
) -> dict[str, Any]:
    """
    Analyze a screen recording and return context for Claude to generate tests.

    Infers user actions from motion types and OCR text across scenes:
    - 'cut' between scenes → page navigation or modal open/close
    - 'animation' → button click, form submit, dropdown open
    - 'scroll' → scroll action
    - OCR text that appears/disappears → assert visibility
    - Scene diffs → what element changed (target for assertion)

    Args:
        video_path: Path to screen recording
        framework: "playwright" or "cypress"
        output_dir: Directory to save analysis files
    """
    video_path = str(Path(video_path).expanduser().resolve())
    if not os.path.exists(video_path):
        return {"error": f"Video file not found: {video_path}"}

    framework = framework.lower().strip()
    if framework not in ("playwright", "cypress"):
        return {"error": "framework must be 'playwright' or 'cypress'"}

    output_dir = str(Path(output_dir).expanduser().resolve())
    manifest = build_manifest(video_path, output_dir)

    # Build action sequence from scene transitions
    steps = []
    scenes = manifest["scenes"]
    for i, scene in enumerate(scenes):
        prev_text = set(scenes[i-1]["detected_text"]) if i > 0 else set()
        curr_text = set(scene["detected_text"])
        appeared = list(curr_text - prev_text)
        disappeared = list(prev_text - curr_text)
        diff = scene.get("diff_from_previous", {})

        action = {
            "step": i + 1,
            "scene_id": scene["id"],
            "timestamp": f"{scene['start']}s",
            "motion_type": scene["motion_type"],
            "narration": scene["transcript_overlap"],
            "text_appeared": appeared,
            "text_disappeared": disappeared,
            "diff_score": diff.get("diff_score", 0),
            "change_type": diff.get("change_type", "none"),
            "changed_regions": diff.get("changed_regions", []),
            "keyframe_path": scene["keyframe_path"],
            "burst_frame_paths": [bf["path"] for bf in scene.get("burst_frames", [])],
        }

        # Infer likely user action
        if scene["motion_type"] == "cut" and diff.get("diff_score", 0) > 60:
            action["inferred_action"] = "navigate" if not appeared else "modal_or_drawer_open"
        elif scene["motion_type"] == "animation":
            action["inferred_action"] = "click_or_submit"
        elif scene["motion_type"] == "scroll":
            action["inferred_action"] = "scroll"
        else:
            action["inferred_action"] = "observe"

        steps.append(action)

    if framework == "playwright":
        task = (
            "Generate a complete Playwright test file in TypeScript.\n"
            "For each step:\n"
            "- 'navigate' → await page.goto() or expect(page).toHaveURL()\n"
            "- 'click_or_submit' → await page.click() or page.locator().click()\n"
            "- 'scroll' → await page.evaluate(() => window.scrollBy())\n"
            "- 'observe' → await expect(page.locator()).toBeVisible()\n"
            "Use text_appeared values for toBeVisible() assertions.\n"
            "Use text_disappeared values for toBeHidden() assertions.\n"
            "Look at keyframe images to identify exact selectors (button text, aria labels).\n"
            "Output a single test file with describe/test blocks."
        )
    else:
        task = (
            "Generate a complete Cypress test file in JavaScript.\n"
            "For each step:\n"
            "- 'navigate' → cy.visit() or cy.url().should('include', ...)\n"
            "- 'click_or_submit' → cy.contains().click() or cy.get().submit()\n"
            "- 'scroll' → cy.scrollTo()\n"
            "- 'observe' → cy.contains().should('be.visible')\n"
            "Use text_appeared for should('be.visible') assertions.\n"
            "Look at keyframe images to identify selectors.\n"
            "Output a single spec file with describe/it blocks."
        )

    return {
        "status": "success",
        "framework": framework,
        "total_steps": len(steps),
        "steps": steps,
        "keyframes_dir": str(Path(output_dir) / "frames"),
        "burst_frames_dir": str(Path(output_dir) / "burst"),
        "task": task,
        "instructions": (
            "Read keyframe and burst frame images for each step. "
            "steps[].inferred_action tells you what the user likely did. "
            "steps[].text_appeared / text_disappeared are your assertion targets. "
            "steps[].changed_regions give normalized (0-1) coordinates of what changed."
        ),
    }


# ---------------------------------------------------------------------------
# Tool 8: export_tokens
# ---------------------------------------------------------------------------

@mcp.tool()
def export_tokens(
    video_path: str,
    format: str = "all",
    output_dir: str = "./video_analysis",
) -> dict[str, Any]:
    """
    Export the video's color palette as design tokens in multiple formats.

    Args:
        video_path: Path to video file
        format: "tailwind" | "css" | "figma" | "all"
        output_dir: Directory to save analysis + token files
    """
    video_path = str(Path(video_path).expanduser().resolve())
    if not os.path.exists(video_path):
        return {"error": f"Video file not found: {video_path}"}

    fmt = format.lower().strip()
    if fmt not in ("tailwind", "css", "figma", "all"):
        return {"error": "format must be tailwind | css | figma | all"}

    output_dir = str(Path(output_dir).expanduser().resolve())
    manifest = build_manifest(video_path, output_dir)

    palette = manifest.get("color_palette", [])
    tokens = _infer_color_tokens(manifest)
    out_path = Path(output_dir)

    results: dict[str, Any] = {"status": "success", "tokens": tokens, "palette": palette}

    # --- Tailwind ---
    if fmt in ("tailwind", "all"):
        tw_colors = {f"brand-{i+1}": c["hex"] for i, c in enumerate(palette[:8])}
        tw_colors.update({
            "background": tokens.get("background", "#000000"),
            "surface": tokens.get("surface", "#111111"),
            "accent": tokens.get("accent", "#ffffff"),
            "text-primary": tokens.get("text", "#ffffff"),
        })
        tailwind_config = (
            "/** @type {import('tailwindcss').Config} */\n"
            "module.exports = {\n"
            "  theme: {\n"
            "    extend: {\n"
            "      colors: {\n"
            + "".join(f"        '{k}': '{v}',\n" for k, v in tw_colors.items()) +
            "      },\n"
            "    },\n"
            "  },\n"
            "};\n"
        )
        tw_path = out_path / "tailwind.config.js"
        tw_path.write_text(tailwind_config)
        results["tailwind_config"] = tailwind_config
        results["tailwind_path"] = str(tw_path)

    # --- CSS Variables ---
    if fmt in ("css", "all"):
        css_vars = ":root {\n"
        css_vars += f"  --color-background: {tokens.get('background', '#000')};\n"
        css_vars += f"  --color-surface: {tokens.get('surface', '#111')};\n"
        css_vars += f"  --color-accent: {tokens.get('accent', '#fff')};\n"
        css_vars += f"  --color-accent-secondary: {tokens.get('accent_secondary', '#aaa')};\n"
        css_vars += f"  --color-text: {tokens.get('text', '#fff')};\n"
        for i, c in enumerate(palette[:8]):
            css_vars += f"  --color-brand-{i+1}: {c['hex']};\n"
        css_vars += "}\n"
        css_path = out_path / "tokens.css"
        css_path.write_text(css_vars)
        results["css_variables"] = css_vars
        results["css_path"] = str(css_path)

    # --- Figma Tokens JSON ---
    if fmt in ("figma", "all"):
        import json as _json
        figma_tokens = {
            "global": {
                "background": {"value": tokens.get("background", "#000"), "type": "color"},
                "surface":    {"value": tokens.get("surface", "#111"),    "type": "color"},
                "accent":     {"value": tokens.get("accent", "#fff"),     "type": "color"},
                "text":       {"value": tokens.get("text", "#fff"),       "type": "color"},
            },
            "palette": {
                f"brand-{i+1}": {"value": c["hex"], "type": "color"}
                for i, c in enumerate(palette[:8])
            },
        }
        figma_path = out_path / "figma-tokens.json"
        figma_path.write_text(_json.dumps(figma_tokens, indent=2))
        results["figma_tokens"] = figma_tokens
        results["figma_path"] = str(figma_path)

    return results


# ---------------------------------------------------------------------------
# Tool 9: user_flow
# ---------------------------------------------------------------------------

@mcp.tool()
def user_flow(
    video_path: str,
    output_dir: str = "./video_analysis",
) -> dict[str, Any]:
    """
    Infer a step-by-step user journey from a screen recording.

    Uses scene transitions, motion types, OCR text changes, and scene diffs
    to reconstruct what the user was doing — like a test plan or user story.

    Args:
        video_path: Path to screen recording
        output_dir: Directory to save analysis files
    """
    video_path = str(Path(video_path).expanduser().resolve())
    if not os.path.exists(video_path):
        return {"error": f"Video file not found: {video_path}"}

    output_dir = str(Path(output_dir).expanduser().resolve())
    manifest = build_manifest(video_path, output_dir)

    scenes = manifest["scenes"]
    steps = []

    for i, scene in enumerate(scenes):
        prev_text = set(scenes[i-1]["detected_text"]) if i > 0 else set()
        curr_text = set(scene["detected_text"])
        appeared = sorted(curr_text - prev_text)
        disappeared = sorted(prev_text - curr_text)
        diff = scene.get("diff_from_previous", {})

        # Infer step label
        if i == 0:
            label = "Start / Landing"
        elif scene["motion_type"] == "cut" and diff.get("diff_score", 0) > 60:
            label = f"Navigate → {appeared[0]}" if appeared else "Page change"
        elif scene["motion_type"] == "animation":
            label = f"Interact: {appeared[0]}" if appeared else "UI interaction"
        elif scene["motion_type"] == "scroll":
            label = "Scroll"
        elif appeared:
            label = f"View: {', '.join(appeared[:3])}"
        else:
            label = "Observe"

        steps.append({
            "step": i + 1,
            "label": label,
            "timestamp": f"{scene['start']}s–{scene['end']}s",
            "scene_id": scene["id"],
            "keyframe_path": scene["keyframe_path"],
            "burst_frame_paths": [bf["path"] for bf in scene.get("burst_frames", [])],
            "text_on_screen": scene["detected_text"],
            "text_appeared": appeared,
            "text_disappeared": disappeared,
            "narration": scene["transcript_overlap"],
            "motion_type": scene["motion_type"],
            "diff_change_type": diff.get("change_type", "none"),
            "diff_score": diff.get("diff_score", 0),
            "ui_components": scene.get("ui_components", []),
        })

    return {
        "status": "success",
        "video_type": manifest["metadata"]["video_type"],
        "duration": manifest["metadata"]["duration_seconds"],
        "total_steps": len(steps),
        "steps": steps,
        "keyframes_dir": str(Path(output_dir) / "frames"),
        "instructions": (
            "Read keyframe images for each step. "
            "Use step.label as the step title. "
            "Use text_appeared to describe what became visible. "
            "Use narration for spoken context. "
            "Output a numbered user flow with screenshots referenced by keyframe_path."
        ),
    }


# ---------------------------------------------------------------------------
# Tool 10: generate_animations
# ---------------------------------------------------------------------------

@mcp.tool()
def generate_animations(
    video_path: str,
    framework: str = "css",
    output_dir: str = "./video_analysis",
) -> dict[str, Any]:
    """
    Extract animation data from a video and return context for Claude to generate
    CSS @keyframes or Framer Motion code.

    For each high-motion scene, burst frames capture the animation states.
    Claude reads those frames and writes the actual keyframe/transition code.

    Args:
        video_path: Path to video file
        framework: "css" or "framer-motion"
        output_dir: Directory to save analysis files
    """
    video_path = str(Path(video_path).expanduser().resolve())
    if not os.path.exists(video_path):
        return {"error": f"Video file not found: {video_path}"}

    framework = framework.lower().strip()
    if framework not in ("css", "framer-motion"):
        return {"error": "framework must be 'css' or 'framer-motion'"}

    output_dir = str(Path(output_dir).expanduser().resolve())
    manifest = build_manifest(video_path, output_dir)

    animated_scenes = [
        s for s in manifest["scenes"]
        if s["motion_detected"] and s.get("burst_frames")
    ]

    animations = []
    for scene in animated_scenes:
        burst_paths = [bf["path"] for bf in scene["burst_frames"]]
        n = len(burst_paths)
        duration_s = round(scene["end"] - scene["start"], 2)

        animations.append({
            "id": f"anim_{scene['id']}",
            "scene_id": scene["id"],
            "timestamp": f"{scene['start']}s–{scene['end']}s",
            "duration_seconds": duration_s,
            "motion_type": scene["motion_type"],
            "motion_level": scene["motion_level"],
            "keyframe_path": scene["keyframe_path"],   # first frame
            "burst_frame_paths": burst_paths,           # animation states
            "frame_count": n,
            "frame_interval_ms": round(duration_s * 1000 / max(n - 1, 1)),
            "color_palette": scene["color_palette"],
        })

    if framework == "css":
        task = (
            "For each animation, look at the burst_frame_paths images in order.\n"
            "They show the element at evenly-spaced points through the animation.\n"
            "Generate CSS @keyframes that replicate what you see:\n"
            "- Name each animation after its id (e.g. @keyframes anim_scene_1)\n"
            "- Use the frame_interval_ms for timing\n"
            "- Distribute keyframe stops (0%, 25%, 50%, 75%, 100%) across the frames\n"
            "- Add the animation class to a sample element\n"
            "Output one CSS block per animation."
        )
    else:
        task = (
            "For each animation, look at the burst_frame_paths images in order.\n"
            "They show the element at evenly-spaced points through the animation.\n"
            "Generate Framer Motion variants that replicate what you see:\n"
            "- Name each variant after its id\n"
            "- Use duration_seconds for the transition\n"
            "- Derive initial/animate/exit states from first/last burst frames\n"
            "- Use intermediate frames for custom keyframes array if needed\n"
            "Output a React component with motion.div for each animation."
        )

    return {
        "status": "success",
        "framework": framework,
        "animated_scene_count": len(animations),
        "animations": animations,
        "burst_frames_dir": str(Path(output_dir) / "burst"),
        "task": task,
        "instructions": (
            "Read burst frame images for each animation — they are the keyframe states. "
            "burst_frame_paths[0] = start state, burst_frame_paths[-1] = end state. "
            "Intermediate frames show the easing curve visually."
        ),
    }


# ---------------------------------------------------------------------------
# Tool 11: watch_directory
# ---------------------------------------------------------------------------

@mcp.tool()
def watch_directory(
    directory: str,
    output_base_dir: str = "./video_analysis",
    extensions: str = ".mp4,.mov,.webm,.avi",
) -> dict[str, Any]:
    """
    Scan a directory for video files and analyze any that haven't been processed yet.

    Uses video hash caching — skips videos whose manifest already exists and matches
    the current file hash. Safe to re-run repeatedly.

    Args:
        directory: Directory to scan for video files
        output_base_dir: Base directory for analysis output (one subfolder per video)
        extensions: Comma-separated list of video extensions to process
    """
    directory = str(Path(directory).expanduser().resolve())
    if not os.path.isdir(directory):
        return {"error": f"Directory not found: {directory}"}

    import json as _json

    exts = {e.strip().lower() for e in extensions.split(",")}
    output_base = Path(output_base_dir).expanduser().resolve()
    output_base.mkdir(parents=True, exist_ok=True)

    # Find all video files
    video_files = []
    for f in Path(directory).iterdir():
        if f.is_file() and f.suffix.lower() in exts:
            video_files.append(f)

    if not video_files:
        return {
            "status": "no_videos",
            "message": f"No video files found in {directory} with extensions {extensions}",
        }

    results = []
    for video_file in sorted(video_files):
        video_path = str(video_file)
        out_dir = str(output_base / video_file.stem)
        manifest_path = Path(out_dir) / "manifest.json"

        # Check cache
        current_hash = compute_video_hash(video_path)
        if manifest_path.exists():
            try:
                existing = _json.loads(manifest_path.read_text())
                if existing.get("video_hash") == current_hash:
                    results.append({
                        "file": video_file.name,
                        "status": "cached",
                        "manifest_path": str(manifest_path),
                        "video_hash": current_hash,
                    })
                    continue
            except Exception:
                pass

        # Analyze
        try:
            manifest = build_manifest(video_path, out_dir)
            results.append({
                "file": video_file.name,
                "status": "analyzed",
                "manifest_path": str(manifest_path),
                "video_hash": current_hash,
                "video_type": manifest["metadata"]["video_type"],
                "scenes": manifest["summary"]["total_scenes"],
                "dominant_colors": manifest["summary"]["dominant_colors"],
                "ui_components": manifest["summary"]["ui_components_detected"],
            })
        except Exception as e:
            results.append({
                "file": video_file.name,
                "status": "error",
                "error": str(e),
            })

    analyzed = [r for r in results if r["status"] == "analyzed"]
    cached = [r for r in results if r["status"] == "cached"]
    errors = [r for r in results if r["status"] == "error"]

    return {
        "status": "success",
        "total_files": len(video_files),
        "analyzed": len(analyzed),
        "cached": len(cached),
        "errors": len(errors),
        "results": results,
        "output_base_dir": str(output_base),
        "instructions": (
            "Each analyzed video has its manifest at results[].manifest_path. "
            "Cached videos were skipped because their manifest is already up to date. "
            "Re-run watch_directory any time — it only processes new or changed files."
        ),
    }


# ---------------------------------------------------------------------------
# Tool 12: generate_report
# ---------------------------------------------------------------------------

@mcp.tool()
def generate_report(
    video_path: str,
    output_dir: str = "./video_analysis",
) -> dict[str, Any]:
    """
    Analyze a video and generate a self-contained HTML visual report.

    The report embeds all keyframe images, color swatches, typography table,
    motion badges, burst frames, OCR chips, and transcript — shareable with
    no external dependencies.

    Args:
        video_path: Path to video file
        output_dir: Where to save the report and analysis files
    """
    video_path = str(Path(video_path).expanduser().resolve())
    if not os.path.exists(video_path):
        return {"error": f"Video file not found: {video_path}"}

    output_dir = str(Path(output_dir).expanduser().resolve())
    manifest = build_manifest(video_path, output_dir)
    report_path = generate_html_report(manifest, output_dir)

    return {
        "status": "success",
        "report_path": report_path,
        "manifest_path": str(Path(output_dir) / "manifest.json"),
        "instructions": f"Open {report_path} in a browser to view the full visual report.",
    }


# ---------------------------------------------------------------------------
# Tool 13: generate_prd
# ---------------------------------------------------------------------------

@mcp.tool()
def generate_prd(
    video_path: str,
    output_dir: str = "./video_analysis",
) -> dict[str, Any]:
    """
    Analyze a demo/walkthrough video and return context for Claude to write
    a Product Requirements Document.

    Extracts everything a PM needs: feature inventory from OCR text, user flow
    from scene sequence, UI components, narration, and visual evidence (keyframes).

    Args:
        video_path: Path to demo or walkthrough video
        output_dir: Directory to save analysis files
    """
    video_path = str(Path(video_path).expanduser().resolve())
    if not os.path.exists(video_path):
        return {"error": f"Video file not found: {video_path}"}

    output_dir = str(Path(output_dir).expanduser().resolve())
    manifest = build_manifest(video_path, output_dir)

    scenes = manifest["scenes"]
    meta   = manifest["metadata"]

    # Build feature inventory from OCR text across all scenes
    all_text = list(dict.fromkeys(
        t for s in scenes for t in s["detected_text"]
    ))

    # Build user flow steps
    flow_steps = []
    for i, scene in enumerate(scenes):
        prev_text = set(scenes[i-1]["detected_text"]) if i > 0 else set()
        appeared = sorted(set(scene["detected_text"]) - prev_text)
        flow_steps.append({
            "step": i + 1,
            "timestamp": f"{scene['start']}s",
            "label": appeared[0] if appeared else f"Scene {i+1}",
            "new_elements": appeared,
            "narration": scene["transcript_overlap"],
            "motion": scene["motion_type"],
            "keyframe_path": scene["keyframe_path"],
        })

    full_transcript = " ".join(s["text"] for s in manifest["transcript"]).strip()
    all_components  = manifest["summary"].get("ui_components_detected", [])

    task = (
        "Write a complete Product Requirements Document from this video.\n\n"
        "Structure:\n"
        "# Product Requirements Document\n\n"
        "## Overview\n"
        "<What product/feature is this? Infer from keyframes + narration>\n\n"
        "## Problem Statement\n"
        "<What user problem does this solve? Infer from the demo>\n\n"
        "## User Flow\n"
        "<Numbered steps from flow_steps — use keyframe images as evidence>\n\n"
        "## Feature Requirements\n"
        "<Functional requirements inferred from all_text + components + keyframes>\n\n"
        "## UI Requirements\n"
        "<Component inventory, layout, color scheme, typography>\n\n"
        "## Non-Functional Requirements\n"
        "<Animations, responsiveness, performance hints from motion data>\n\n"
        "## Open Questions\n"
        "<Things unclear from the video that need clarification>\n\n"
        "Be specific. Reference exact text from all_text. Use keyframe images as visual evidence."
    )

    return {
        "status": "success",
        "video_type":       meta["video_type"],
        "duration":         meta["duration_seconds"],
        "all_text":         all_text,
        "ui_components":    all_components,
        "color_palette":    manifest.get("color_palette", []),
        "typography":       manifest.get("typography", []),
        "flow_steps":       flow_steps,
        "full_transcript":  full_transcript,
        "keyframes_dir":    str(Path(output_dir) / "frames"),
        "task":             task,
        "instructions": (
            "Read every keyframe image. "
            "flow_steps gives you the user journey with timestamps. "
            "all_text is every string visible on screen — use verbatim for requirements. "
            "typography + color_palette give you the design spec. "
            "Write the PRD in markdown and save it to the output directory."
        ),
    }


# ---------------------------------------------------------------------------
# Tool 14: compare_videos
# ---------------------------------------------------------------------------

@mcp.tool()
def compare_videos(
    video_a: str,
    video_b: str,
    output_dir: str = "./video_comparison",
) -> dict[str, Any]:
    """
    Compare two video recordings of the same product/flow and produce a diff.

    Useful for:
    - Before/after a redesign
    - v1 vs v2 of a feature
    - A/B test variants
    - Regression checking

    Returns structured diff: colors added/removed, text added/removed,
    components added/removed, scene count delta, and per-scene similarity scores.

    Args:
        video_a: Path to first video (e.g. old version)
        video_b: Path to second video (e.g. new version)
        output_dir: Directory to save both analyses and comparison report
    """
    for vp in (video_a, video_b):
        vp = str(Path(vp).expanduser().resolve())
        if not os.path.exists(vp):
            return {"error": f"Video file not found: {vp}"}

    video_a = str(Path(video_a).expanduser().resolve())
    video_b = str(Path(video_b).expanduser().resolve())
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    manifest_a = build_manifest(video_a, str(out / "video_a"))
    manifest_b = build_manifest(video_b, str(out / "video_b"))

    # Color diff
    colors_a = {c["hex"] for c in manifest_a.get("color_palette", [])}
    colors_b = {c["hex"] for c in manifest_b.get("color_palette", [])}

    # Text diff (all OCR text across all scenes)
    text_a = set(manifest_a["summary"].get("all_detected_text", []))
    text_b = set(manifest_b["summary"].get("all_detected_text", []))

    # Component diff
    comp_a = set(manifest_a["summary"].get("ui_components_detected", []))
    comp_b = set(manifest_b["summary"].get("ui_components_detected", []))

    # Scene-level similarity (pair up scenes by index)
    scenes_a = manifest_a["scenes"]
    scenes_b = manifest_b["scenes"]
    scene_comparisons = []
    for i, (sa, sb) in enumerate(zip(scenes_a, scenes_b)):
        diff = compute_scene_diff(sa["keyframe_path"], sb["keyframe_path"])
        scene_comparisons.append({
            "index":        i,
            "scene_a":      sa["id"],
            "scene_b":      sb["id"],
            "time_a":       f"{sa['start']}s–{sa['end']}s",
            "time_b":       f"{sb['start']}s–{sb['end']}s",
            "diff_score":   diff.get("diff_score", 0),
            "change_type":  diff.get("change_type", "none"),
            "text_added":   sorted(set(sb["detected_text"]) - set(sa["detected_text"])),
            "text_removed": sorted(set(sa["detected_text"]) - set(sb["detected_text"])),
            "keyframe_a":   sa["keyframe_path"],
            "keyframe_b":   sb["keyframe_path"],
        })

    # Overall similarity score (0 = totally different, 1 = identical)
    if scene_comparisons:
        avg_diff = sum(s["diff_score"] for s in scene_comparisons) / len(scene_comparisons)
        similarity = round(max(0, 1 - avg_diff / 100), 2)
    else:
        similarity = 0.0

    return {
        "status": "success",
        "similarity_score": similarity,
        "video_a": {
            "path":         video_a,
            "duration":     manifest_a["metadata"]["duration_seconds"],
            "scenes":       len(scenes_a),
            "video_type":   manifest_a["metadata"]["video_type"],
            "keyframes_dir": str(out / "video_a" / "frames"),
        },
        "video_b": {
            "path":         video_b,
            "duration":     manifest_b["metadata"]["duration_seconds"],
            "scenes":       len(scenes_b),
            "video_type":   manifest_b["metadata"]["video_type"],
            "keyframes_dir": str(out / "video_b" / "frames"),
        },
        "changes": {
            "colors_added":      sorted(colors_b - colors_a),
            "colors_removed":    sorted(colors_a - colors_b),
            "text_added":        sorted(text_b - text_a),
            "text_removed":      sorted(text_a - text_b),
            "components_added":  sorted(comp_b - comp_a),
            "components_removed": sorted(comp_a - comp_b),
            "scene_count_delta": len(scenes_b) - len(scenes_a),
            "duration_delta_s":  round(
                manifest_b["metadata"]["duration_seconds"] -
                manifest_a["metadata"]["duration_seconds"], 2
            ),
        },
        "scene_comparisons": scene_comparisons,
        "instructions": (
            "similarity_score: 1.0 = identical, 0.0 = completely different. "
            "Read keyframe_a and keyframe_b side by side for each scene_comparison. "
            "changes.text_added = new copy in video_b. "
            "changes.text_removed = copy removed from video_a. "
            "Summarize as a changelog: what was added, removed, or changed between the two versions."
        ),
    }


# ---------------------------------------------------------------------------
# Tool 15: generate_storybook
# ---------------------------------------------------------------------------

@mcp.tool()
def generate_storybook(
    video_path: str,
    output_dir: str = "./video_analysis",
) -> dict[str, Any]:
    """
    Analyze a screen recording and return context for Claude to generate
    Storybook stories for every detected UI component.

    For each scene, provides keyframe, burst frames, OCR text, color palette,
    detected components, and motion data. Claude generates .stories.jsx files
    with Default, Loading, and Interactive variants per component.

    Args:
        video_path: Path to screen recording
        output_dir: Directory to save analysis files
    """
    video_path = str(Path(video_path).expanduser().resolve())
    if not os.path.exists(video_path):
        return {"error": f"Video file not found: {video_path}"}

    output_dir = str(Path(output_dir).expanduser().resolve())
    manifest = build_manifest(video_path, output_dir)

    scenes = manifest["scenes"]
    all_components = manifest["summary"].get("ui_components_detected", [])
    color_tokens = _infer_color_tokens(manifest)

    # Per-component evidence: which scenes show it + keyframe + burst frames
    component_evidence: dict[str, list[dict]] = {c: [] for c in all_components}
    for scene in scenes:
        for comp in scene.get("ui_components", []):
            if comp in component_evidence:
                component_evidence[comp].append({
                    "scene_id": scene["id"],
                    "timestamp": f"{scene['start']}s–{scene['end']}s",
                    "keyframe_path": scene["keyframe_path"],
                    "burst_frame_paths": [bf["path"] for bf in scene.get("burst_frames", [])],
                    "ocr_text": scene["detected_text"],
                    "motion_type": scene["motion_type"],
                    "color_palette": scene["color_palette"],
                    "loading": scene.get("loading", {}),
                    "confidence": scene.get("confidence", {}).get("overall", 0),
                })

    task = (
        "Generate a Storybook story file for each UI component listed in component_evidence.\n\n"
        "For each component:\n"
        "1. Read all keyframe images in component_evidence[component] to see what it looks like\n"
        "2. Use burst_frame_paths to see hover/active states (if motion_type='animation')\n"
        "3. Write a .stories.jsx file with these exports:\n"
        "   - Default: normal resting state, colors from color_palette\n"
        "   - Loading: if loading.has_spinner or loading.has_skeleton, show that state\n"
        "   - Interactive: add onClick/hover handlers based on motion evidence\n"
        "4. Use ocr_text for copy (labels, CTAs, placeholder text)\n"
        "5. Use color_tokens for all color values — do not hardcode\n\n"
        "Name each story file: ComponentName.stories.jsx\n"
        "Output one story file per component."
    )

    return {
        "status": "success",
        "video_type": manifest["metadata"]["video_type"],
        "components": all_components,
        "component_count": len(all_components),
        "component_evidence": component_evidence,
        "color_tokens": color_tokens,
        "global_palette": manifest.get("color_palette", []),
        "typography": manifest.get("typography", []),
        "keyframes_dir": str(Path(output_dir) / "frames"),
        "burst_frames_dir": str(Path(output_dir) / "burst"),
        "task": task,
        "instructions": (
            "Read keyframe and burst frame images for each component's evidence entries. "
            "component_evidence[name] lists every scene where that component appears. "
            "color_tokens gives you semantic color names (background/accent/text). "
            "Generate one .stories.jsx per component — Default, Loading, Interactive variants."
        ),
    }


# ---------------------------------------------------------------------------
# Tool 16: generate_changelog
# ---------------------------------------------------------------------------

@mcp.tool()
def generate_changelog(
    video_before: str,
    video_after: str,
    output_dir: str = "./video_comparison",
    version_before: str = "v1",
    version_after: str = "v2",
) -> dict[str, Any]:
    """
    Compare two screen recordings and return context for Claude to write
    a user-facing changelog entry.

    Extracts exact text added/removed, UI components added/removed,
    motion changes (new animations, removed transitions), and visual diffs
    per scene. Claude writes a polished markdown changelog.

    Args:
        video_before: Path to the older version recording
        video_after: Path to the newer version recording
        output_dir: Directory to save both analyses
        version_before: Label for old version (e.g. "v1.2")
        version_after: Label for new version (e.g. "v2.0")
    """
    for vp in (video_before, video_after):
        if not os.path.exists(str(Path(vp).expanduser().resolve())):
            return {"error": f"Video file not found: {vp}"}

    video_before = str(Path(video_before).expanduser().resolve())
    video_after = str(Path(video_after).expanduser().resolve())
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    manifest_b = build_manifest(video_before, str(out / "before"))
    manifest_a = build_manifest(video_after, str(out / "after"))

    # Text diff
    text_before = set(manifest_b["summary"].get("all_detected_text", []))
    text_after  = set(manifest_a["summary"].get("all_detected_text", []))

    # Component diff
    comp_before = set(manifest_b["summary"].get("ui_components_detected", []))
    comp_after  = set(manifest_a["summary"].get("ui_components_detected", []))

    # Motion diff
    motion_before = set(manifest_b["summary"].get("motion_types", []))
    motion_after  = set(manifest_a["summary"].get("motion_types", []))

    # Color diff
    colors_before = {c["hex"] for c in manifest_b.get("color_palette", [])}
    colors_after  = {c["hex"] for c in manifest_a.get("color_palette", [])}

    # Loading state diff
    loading_before = set(manifest_b["summary"].get("loading_scenes", []))
    loading_after  = set(manifest_a["summary"].get("loading_scenes", []))

    # Scene-level visual diff
    scenes_b = manifest_b["scenes"]
    scenes_a = manifest_a["scenes"]
    scene_diffs = []
    for i, (sb, sa) in enumerate(zip(scenes_b, scenes_a)):
        diff = compute_scene_diff(sb["keyframe_path"], sa["keyframe_path"])
        scene_diffs.append({
            "index": i,
            "timestamp_before": f"{sb['start']}s–{sb['end']}s",
            "timestamp_after":  f"{sa['start']}s–{sa['end']}s",
            "keyframe_before":  sb["keyframe_path"],
            "keyframe_after":   sa["keyframe_path"],
            "diff_score":       diff.get("diff_score", 0),
            "change_type":      diff.get("change_type", "none"),
            "text_added":       sorted(set(sa["detected_text"]) - set(sb["detected_text"])),
            "text_removed":     sorted(set(sb["detected_text"]) - set(sa["detected_text"])),
        })

    if scene_diffs:
        avg_diff = sum(s["diff_score"] for s in scene_diffs) / len(scene_diffs)
        similarity = round(max(0.0, 1.0 - avg_diff / 100), 2)
    else:
        similarity = 1.0

    task = (
        f"Write a user-facing changelog entry comparing {version_before} → {version_after}.\n\n"
        "Format:\n"
        f"## {version_after} — What's New\n\n"
        "### Added\n"
        "- Bullet list of new features/copy from text_added and components_added\n"
        "- Read keyframe_after images to describe new UI visually\n\n"
        "### Changed\n"
        "- Bullet list of modified screens (use scene_diffs where change_type='partial')\n"
        "- Describe what changed visually by comparing keyframe_before vs keyframe_after\n\n"
        "### Removed\n"
        "- Bullet list from text_removed and components_removed\n\n"
        "### Design Updates\n"
        "- Colors added/removed (translate hex codes to descriptive names)\n"
        "- New animations or transitions (motion_types_added)\n\n"
        "Keep tone user-facing and concise. No technical jargon."
    )

    return {
        "status": "success",
        "version_before": version_before,
        "version_after": version_after,
        "similarity_score": similarity,
        "changes": {
            "text_added":          sorted(text_after - text_before),
            "text_removed":        sorted(text_before - text_after),
            "components_added":    sorted(comp_after - comp_before),
            "components_removed":  sorted(comp_before - comp_after),
            "motion_types_added":  sorted(motion_after - motion_before),
            "motion_types_removed": sorted(motion_before - motion_after),
            "colors_added":        sorted(colors_after - colors_before),
            "colors_removed":      sorted(colors_before - colors_after),
            "loading_states_added": len(loading_after) > len(loading_before),
        },
        "scene_diffs": scene_diffs,
        "before": {
            "keyframes_dir": str(out / "before" / "frames"),
            "duration": manifest_b["metadata"]["duration_seconds"],
            "scene_count": len(scenes_b),
        },
        "after": {
            "keyframes_dir": str(out / "after" / "frames"),
            "duration": manifest_a["metadata"]["duration_seconds"],
            "scene_count": len(scenes_a),
        },
        "task": task,
        "instructions": (
            "Read keyframe_before and keyframe_after side by side for each scene_diff. "
            "changes gives you the exact diff data. "
            "Write the changelog in markdown. Be specific — reference exact UI text and components."
        ),
    }


# ---------------------------------------------------------------------------
# Tool 17: annotate_video
# ---------------------------------------------------------------------------

@mcp.tool()
def annotate_video(
    video_path: str,
    output_dir: str = "./video_analysis",
) -> dict[str, Any]:
    """
    Analyze a video and produce annotated debug frames showing:
    - Green boxes: OCR text regions with confidence scores
    - Orange boxes: pixel regions that changed from the previous scene
    - Blue labels: detected UI components
    - Red dots: cursor movement path points
    - Corner badge: overall scene confidence score

    Useful for debugging analysis quality, building visual QA reports,
    or understanding exactly what the plugin detected.

    Args:
        video_path: Path to video file
        output_dir: Directory to save analysis and annotated frames
    """
    video_path = str(Path(video_path).expanduser().resolve())
    if not os.path.exists(video_path):
        return {"error": f"Video file not found: {video_path}"}

    output_dir = str(Path(output_dir).expanduser().resolve())
    manifest = build_manifest(video_path, output_dir)

    annotated_frames = []
    for scene in manifest["scenes"]:
        ann = scene.get("annotated_frame_path", "")
        if ann and os.path.exists(ann):
            conf = scene.get("confidence", {})
            annotated_frames.append({
                "scene_id": scene["id"],
                "timestamp": f"{scene['start']}s–{scene['end']}s",
                "annotated_path": ann,
                "original_path": scene["keyframe_path"],
                "confidence": conf,
                "detections": {
                    "ocr_text_count": len(scene.get("detected_text", [])),
                    "ui_components":  scene.get("ui_components", []),
                    "motion_type":    scene.get("motion_type", "none"),
                    "cursor_detected": scene.get("cursor", {}).get("cursor_detected", False),
                    "has_scrollbar":  scene.get("scroll", {}).get("has_scrollbar", False),
                    "loading_type":   scene.get("loading", {}).get("loading_type", "none"),
                    "change_type":    scene.get("diff_from_previous", {}).get("change_type", "none"),
                },
            })

    avg_conf = manifest["summary"].get("avg_confidence", 0)

    return {
        "status": "success",
        "annotated_frame_count": len(annotated_frames),
        "annotated_frames_dir": str(Path(output_dir) / "annotated"),
        "annotated_frames": annotated_frames,
        "avg_confidence": avg_conf,
        "summary": manifest["summary"],
        "instructions": (
            "Read annotated_frames[].annotated_path to see each debug frame. "
            "Green boxes = OCR text, Orange = changed regions, Blue = components, Red = cursor. "
            "confidence.overall < 0.4 means low-quality frame — results may be unreliable. "
            "Compare annotated_path vs original_path to understand what was detected."
        ),
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
