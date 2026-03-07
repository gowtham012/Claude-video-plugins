"""
Claude API calls for generating output from a video manifest.

Two main actions:
- generate_frontend: produce React or HTML code from a video manifest
- describe_video: produce a detailed natural-language description
"""

from __future__ import annotations

import os
from typing import Any

import anthropic

MODEL = "claude-opus-4-6"
MAX_TOKENS = 8096


def _build_messages(
    manifest: dict[str, Any],
    system_prompt: str,
) -> list[dict]:
    """
    Construct multi-modal Anthropic messages from a video manifest.

    Each scene becomes:
      [image block] + text describing scene metadata (time, OCR, transcript, motion)
    Followed by a final text block with the task instruction.
    """
    metadata = manifest.get("metadata", {})
    scenes = manifest.get("scenes", [])
    transcript = manifest.get("transcript", [])

    content: list[dict] = []

    # --- Scene blocks ---
    for scene in scenes:
        scene_id = scene.get("id", "?")
        start = scene.get("start", 0)
        end = scene.get("end", 0)
        ocr = scene.get("detected_text", [])
        motion_level = scene.get("motion_level", 0)
        motion_flag = "HIGH" if scene.get("motion_detected") else "minimal"
        narration = scene.get("transcript_overlap", "")

        # Image block (if base64 available)
        b64 = scene.get("keyframe_b64", "")
        if b64 and b64 != "<base64 omitted — see keyframe_path>":
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": b64,
                },
            })

        # Scene metadata text block
        lines = [
            f"**{scene_id}** ({start}s – {end}s)",
        ]
        if narration:
            lines.append(f"Narrator says: \"{narration}\"")
        if ocr:
            lines.append(f"Text visible on screen: {', '.join(ocr)}")
        lines.append(f"Motion: {motion_flag} (level: {motion_level})")

        content.append({"type": "text", "text": "\n".join(lines)})

    # --- Video-level context ---
    duration = metadata.get("duration_seconds", 0)
    resolution = metadata.get("resolution", "unknown")
    total_scenes = len(scenes)
    has_audio = metadata.get("has_audio", False)

    full_transcript = " ".join(
        seg.get("text", "") for seg in transcript
    ).strip()

    summary_lines = [
        "---",
        f"VIDEO TYPE: {metadata.get('video_type', 'unknown')}",
        f"DURATION: {duration}s | SCENES: {total_scenes} | RESOLUTION: {resolution}",
        f"HAS AUDIO: {'yes' if has_audio else 'no'}",
    ]
    if full_transcript:
        summary_lines.append(f"\nFULL TRANSCRIPT:\n{full_transcript}")

    summary_lines.append("")
    summary_lines.append(
        "You have received:\n"
        "- Visual keyframes from every scene change\n"
        "- OCR-extracted text from each scene (exact strings visible on screen)\n"
        "- Timestamped audio transcript aligned to scenes\n"
        "- Motion detection flags (HIGH = animation / user interaction happening)\n"
    )

    content.append({"type": "text", "text": "\n".join(summary_lines)})

    # --- Task instruction (system_prompt appended at end) ---
    content.append({"type": "text", "text": system_prompt})

    return [{"role": "user", "content": content}]


def generate_frontend(manifest: dict[str, Any], framework: str = "react") -> str:
    """
    Use Claude (claude-opus-4-6) to generate frontend code from the video manifest.

    Args:
        manifest: Full video manifest from build_manifest()
        framework: "react" or "html"

    Returns:
        Generated code as a string.
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    if framework == "react":
        task_prompt = (
            "Generate a complete, self-contained React implementation that replicates this UI exactly.\n"
            "Requirements:\n"
            "- Use the exact colors, fonts, and layout visible in the keyframes\n"
            "- Use the exact text from OCR output (headlines, CTAs, prices, labels — no guessing)\n"
            "- Add CSS transitions / hover effects for scenes where Motion is HIGH\n"
            "- Structure components to match the visual hierarchy shown\n"
            "- Output TWO files separated by `// --- App.jsx ---` and `// --- App.css ---` markers\n"
            "- No imports from external libraries (use inline styles or the CSS file only)\n"
            "- The component must be self-contained and runnable with `create-react-app`\n"
            "Output code only. No explanation."
        )
    else:
        task_prompt = (
            "Generate a complete, self-contained HTML page that replicates this UI exactly.\n"
            "Requirements:\n"
            "- Use the exact colors, fonts, and layout visible in the keyframes\n"
            "- Use the exact text from OCR output (headlines, CTAs, prices, labels — no guessing)\n"
            "- Add CSS transitions / hover effects for scenes where Motion is HIGH\n"
            "- Inline all CSS and JS in a single `index.html` file\n"
            "- No external CDN dependencies\n"
            "- Must open correctly in a browser without a server\n"
            "Output code only. No explanation."
        )

    messages = _build_messages(manifest, task_prompt)

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=messages,
    )

    return response.content[0].text


def describe_video(manifest: dict[str, Any]) -> str:
    """
    Use Claude (claude-opus-4-6) to produce a detailed description of the video.

    Works for website recordings, 3D walkthroughs, marketing videos, etc.
    Returns a structured markdown description.
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    task_prompt = (
        "Provide a detailed, structured analysis of this video. Cover:\n\n"
        "1. **Overall purpose** — What is this video showing or demonstrating?\n"
        "2. **Scene-by-scene breakdown** — For each scene: what is shown, key UI/content, "
        "what the narrator says, whether there is significant motion/interaction.\n"
        "3. **Key content extracted** — All headlines, CTAs, prices, feature names, "
        "product names, and important labels visible on screen.\n"
        "4. **UI/UX observations** — Layout structure, navigation patterns, color scheme, "
        "interaction patterns, component types observed.\n"
        "5. **Narration summary** — A condensed summary of the audio narration.\n"
        "6. **Notable moments** — Scenes with high motion, important transitions, "
        "key interactions demonstrated.\n\n"
        "Be specific. Use timestamps. Reference exact text from the OCR output.\n"
        "Format the response as structured markdown."
    )

    messages = _build_messages(manifest, task_prompt)

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=messages,
    )

    return response.content[0].text
