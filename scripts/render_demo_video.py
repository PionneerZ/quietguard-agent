"""Render the captioned QuietGuard hackathon demo video.

Usage:
    python scripts/render_demo_video.py \
      --dashboard artifacts/media/dashboard.png \
      --architecture artifacts/media/architecture.png \
      --output artifacts/media/quietguard-demo.mp4
"""

from __future__ import annotations

import argparse
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont
from imageio_ffmpeg import write_frames


WIDTH, HEIGHT = 1280, 720
BG = (243, 248, 253)
INK = (10, 27, 52)
MUTED = (82, 105, 137)
TEAL = (12, 148, 135)
MINT = (59, 215, 170)
AMBER = (245, 166, 35)
NAVY = (20, 39, 70)
WHITE = (255, 255, 255)


def font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    if mono:
        candidates = [Path("C:/Windows/Fonts/CascadiaMono.ttf"), Path("C:/Windows/Fonts/consola.ttf")]
    elif bold:
        candidates = [Path("C:/Windows/Fonts/segoeuib.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")]
    else:
        candidates = [Path("C:/Windows/Fonts/segoeui.ttf"), Path("C:/Windows/Fonts/arial.ttf")]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default(size=size)


F14, F18, F22, F30, F46, F62 = (font(n) for n in (14, 18, 22, 30, 46, 62))
B18, B22, B30, B46, B62 = (font(n, bold=True) for n in (18, 22, 30, 46, 62))
MONO18 = font(18, mono=True)


def canvas() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        t = y / max(1, HEIGHT - 1)
        color = tuple(int(BG[i] * (1 - t) + (233, 252, 246)[i] * t) for i in range(3))
        draw.line((0, y, WIDTH, y), fill=color)
    return image


def text_block(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, face: ImageFont.FreeTypeFont, fill=INK, width=44, spacing=8) -> None:
    wrapped = "\n".join(textwrap.wrap(text, width=width, break_long_words=False))
    draw.multiline_text(xy, wrapped, font=face, fill=fill, spacing=spacing)


def top_label(draw: ImageDraw.ImageDraw, value: str) -> None:
    draw.text((70, 48), value.upper(), font=B18, fill=TEAL)


def footer(draw: ImageDraw.ImageDraw, section: str, index: int, count: int) -> None:
    draw.rounded_rectangle((70, 665, 1210, 670), radius=3, fill=(216, 228, 239))
    draw.rounded_rectangle((70, 665, 70 + int(1140 * index / count), 670), radius=3, fill=MINT)
    draw.text((70, 680), section, font=F14, fill=MUTED)


def title_slide() -> Image.Image:
    image = canvas(); draw = ImageDraw.Draw(image)
    top_label(draw, "Agents for Humans · Professional Agents")
    draw.rounded_rectangle((70, 150, 1210, 535), radius=34, fill=NAVY)
    draw.text((120, 215), "QUIETGUARD", font=B62, fill=(88, 232, 208))
    draw.text((120, 306), "Disk pressure, handled quietly.", font=B46, fill=WHITE)
    text_block(draw, (123, 386), "A safety-first Strands agent that acts on known noise and escalates only real decisions.", F22, (210, 224, 242), width=68)
    return image


def problem_slide() -> Image.Image:
    image = canvas(); draw = ImageDraw.Draw(image); top_label(draw, "The problem")
    draw.text((70, 110), "Log storms fail silently.", font=B46, fill=INK)
    cards = [
        ("01", "Background growth", "Diagnostic logs can consume a workstation before anyone notices."),
        ("02", "Late manual cleanup", "A person has to find the source while urgent work is already blocked."),
        ("03", "Risky broad scripts", "Deleting by extension alone can destroy state, documents, or evidence."),
    ]
    for i, (num, heading, body) in enumerate(cards):
        x = 70 + i * 385
        draw.rounded_rectangle((x, 230, x + 350, 555), radius=24, fill=WHITE, outline=(220, 230, 239), width=2)
        draw.text((x + 28, 260), num, font=B22, fill=TEAL)
        draw.text((x + 28, 326), heading, font=B30, fill=INK)
        text_block(draw, (x + 28, 390), body, F18, MUTED, width=29, spacing=10)
    return image


def audience_slide() -> Image.Image:
    image = canvas(); draw = ImageDraw.Draw(image); top_label(draw, "Who it is for")
    draw.text((70, 110), "Operations safety for teams without operators.", font=B46, fill=INK)
    draw.rounded_rectangle((70, 225, 790, 570), radius=28, fill=WHITE, outline=(220, 230, 239), width=2)
    bullets = [
        "Solo professionals running data-heavy desktop tools",
        "Small businesses with shared workstations",
        "Analysts and creators who cannot pause to babysit storage",
    ]
    for i, item in enumerate(bullets):
        y = 275 + i * 92
        draw.ellipse((110, y, 142, y + 32), fill=(215, 249, 240))
        draw.text((119, y + 2), "✓", font=B22, fill=TEAL)
        draw.text((165, y), item, font=F22, fill=INK)
    draw.rounded_rectangle((830, 225, 1210, 570), radius=28, fill=NAVY)
    draw.text((870, 270), "THE PROMISE", font=B18, fill=MINT)
    text_block(draw, (870, 330), "Run quietly.\nAct narrowly.\nExplain everything.", B30, WHITE, width=18, spacing=18)
    return image


def image_slide(path: Path, label: str, heading: str, note: str) -> Image.Image:
    image = canvas(); draw = ImageDraw.Draw(image); top_label(draw, label)
    draw.text((70, 92), heading, font=B30, fill=INK)
    source = Image.open(path).convert("RGB")
    source.thumbnail((1140, 510), Image.Resampling.LANCZOS)
    x = (WIDTH - source.width) // 2; y = 150 + (510 - source.height) // 2
    draw.rounded_rectangle((x - 10, y - 10, x + source.width + 10, y + source.height + 10), radius=18, fill=WHITE, outline=(218, 228, 238), width=2)
    image.paste(source, (x, y))
    draw.text((70, 630), note, font=F18, fill=MUTED)
    return image


def command_slide() -> Image.Image:
    image = canvas(); draw = ImageDraw.Draw(image); top_label(draw, "Contained working demo")
    draw.text((70, 110), "One command. No cloud account. No user files.", font=B46, fill=INK)
    draw.rounded_rectangle((70, 225, 1210, 540), radius=26, fill=(12, 24, 43))
    lines = [
        ("PS> quietguard demo --output artifacts/acceptance", (105, 226, 205)),
        ("[Strands] tool 1/4  scan_workspace", (145, 177, 220)),
        ("[Strands] tool 2/4  build_guarded_plan", (145, 177, 220)),
        ("[Strands] tool 3/4  apply_safe_actions", (145, 177, 220)),
        ("[Strands] tool 4/4  publish_dashboard", (145, 177, 220)),
        ("DONE  3.0 MB reclaimed · 1 decision escalated", (88, 232, 208)),
    ]
    for i, (line, color) in enumerate(lines):
        draw.text((110, 270 + i * 42), line, font=MONO18, fill=color)
    draw.text((70, 590), "The offline custom model drives the real Strands agent loop and four decorated tools.", font=F18, fill=MUTED)
    return image


def evidence_slide() -> Image.Image:
    image = canvas(); draw = ImageDraw.Draw(image); top_label(draw, "What the evidence proves")
    draw.text((70, 110), "The agent distinguishes action from uncertainty.", font=B46, fill=INK)
    rows = [
        ("Primary001.log", "2.0 MB", "AUTO-SAFE", MINT),
        ("session.tmp", "1.0 MB", "AUTO-SAFE", MINT),
        ("mystery.log", "768 KB", "REVIEW", AMBER),
        ("customer.sqlite", "640 KB", "PROTECTED", (160, 177, 198)),
    ]
    draw.rounded_rectangle((70, 225, 1210, 570), radius=24, fill=WHITE, outline=(220, 230, 239), width=2)
    draw.text((105, 255), "FILE", font=B18, fill=MUTED); draw.text((650, 255), "SIZE", font=B18, fill=MUTED); draw.text((875, 255), "DECISION", font=B18, fill=MUTED)
    for i, (name, size, decision, color) in enumerate(rows):
        y = 306 + i * 60
        draw.line((105, y - 12, 1170, y - 12), fill=(232, 238, 244), width=1)
        draw.text((105, y), name, font=F22, fill=INK); draw.text((650, y), size, font=F22, fill=INK)
        draw.rounded_rectangle((875, y - 4, 1090, y + 35), radius=18, fill=color)
        draw.text((895, y + 4), decision, font=B18, fill=NAVY if color != (160, 177, 198) else WHITE)
    return image


def safety_slide() -> Image.Image:
    image = canvas(); draw = ImageDraw.Draw(image); top_label(draw, "Safety boundary")
    draw.text((70, 110), "Automation earns trust one guard at a time.", font=B46, fill=INK)
    guards = ["Exact resolved root", "Explicit marker", "Safe extension", "Minimum age", "Byte budget", "Reparse refusal", "Read-only default", "Hash-chained audit"]
    for i, value in enumerate(guards):
        col, row = i % 2, i // 2
        x, y = 70 + col * 575, 225 + row * 82
        draw.rounded_rectangle((x, y, x + 540, y + 58), radius=18, fill=WHITE, outline=(218, 229, 238), width=2)
        draw.ellipse((x + 18, y + 13, x + 50, y + 45), fill=(215, 249, 240))
        draw.text((x + 27, y + 14), "✓", font=B18, fill=TEAL)
        draw.text((x + 68, y + 14), value, font=B22, fill=INK)
    return image


def outcome_slide() -> Image.Image:
    image = canvas(); draw = ImageDraw.Draw(image); top_label(draw, "Outcome")
    draw.text((70, 105), "Known noise disappears. Decisions keep their context.", font=B46, fill=INK)
    metrics = [("3.0 MB", "reclaimed safely"), ("0", "protected files changed"), ("1", "clear human decision"), ("7/7", "tests passing")]
    for i, (value, label) in enumerate(metrics):
        x = 70 + (i % 2) * 575; y = 235 + (i // 2) * 165
        draw.rounded_rectangle((x, y, x + 540, y + 130), radius=24, fill=WHITE, outline=(218, 229, 238), width=2)
        draw.text((x + 30, y + 22), value, font=B46, fill=TEAL)
        draw.text((x + 30, y + 84), label, font=F18, fill=MUTED)
    return image


def closing_slide() -> Image.Image:
    image = canvas(); draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((70, 90, 1210, 610), radius=34, fill=NAVY)
    draw.text((120, 155), "QUIETGUARD", font=B62, fill=MINT)
    text_block(draw, (120, 270), "Autonomy for the routine.\nEvidence for the uncertain.", B46, WHITE, width=34, spacing=16)
    draw.text((120, 455), "Built with Strands Agents SDK · MIT licensed · Offline demo included", font=F22, fill=(204, 221, 239))
    draw.text((120, 520), "github.com/PionneerZ/quietguard-agent", font=MONO18, fill=(110, 224, 206))
    return image


@dataclass
class Scene:
    label: str
    duration: float
    build: Callable[[], Image.Image]


def render(dashboard: Path, architecture: Path, output: Path, fps: int = 5) -> None:
    scenes = [
        Scene("Promise", 7, title_slide),
        Scene("Problem", 12, problem_slide),
        Scene("Audience", 11, audience_slide),
        Scene("Architecture", 16, lambda: image_slide(architecture, "How it works", "A real Strands agent coordinates bounded tools.", "The policy can change; the filesystem guardrails cannot.")),
        Scene("Live cycle", 15, command_slide),
        Scene("Evidence", 14, evidence_slide),
        Scene("Dashboard", 16, lambda: image_slide(dashboard, "Working result", "The dashboard shows what changed and what still needs a decision.", "Synthetic acceptance run: 4 files inspected · 3.0 MB safely reclaimed.")),
        Scene("Guardrails", 14, safety_slide),
        Scene("Impact", 11, outcome_slide),
        Scene("Close", 8, closing_slide),
    ]
    frames: list[tuple[Image.Image, int]] = []
    for index, scene in enumerate(scenes, start=1):
        frame = scene.build().convert("RGB")
        if index not in (1, len(scenes)):
            footer(ImageDraw.Draw(frame), scene.label, index, len(scenes))
        frames.append((frame, int(scene.duration * fps)))
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = write_frames(str(output), (WIDTH, HEIGHT), fps=fps, codec="libx264", quality=7, output_params=["-movflags", "+faststart"], ffmpeg_log_level="warning")
    writer.send(None)
    try:
        for frame, count in frames:
            data = frame.tobytes()
            for _ in range(count):
                writer.send(data)
    finally:
        writer.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", type=Path, required=True)
    parser.add_argument("--architecture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fps", type=int, default=5)
    args = parser.parse_args()
    render(args.dashboard, args.architecture, args.output, args.fps)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())