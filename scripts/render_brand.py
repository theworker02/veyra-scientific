"""Distribute the canonical Veyra mark from assets/ to every package surface."""

from __future__ import annotations

from pathlib import Path
from shutil import copy2

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
MEDIA = ROOT / "docs" / "media"
INK = (13, 13, 13, 255)
TEAL = (16, 163, 127, 255)
WHITE = (255, 255, 255, 255)
CANVAS = (255, 255, 255, 0)

CANONICAL_SVG = [
    "logo.svg",
    "logo-dark.svg",
    "favicon.svg",
    "wordmark.svg",
    "icon-activity.svg",
]


def _line(draw: ImageDraw.ImageDraw, a: tuple[float, float], b: tuple[float, float], fill: tuple[int, ...], width: int) -> None:
    draw.line([a, b], fill=fill, width=width)
    r = max(1, width / 2)
    for point in (a, b):
        draw.ellipse((point[0] - r, point[1] - r, point[0] + r, point[1] + r), fill=fill)


def render_mark(size: int = 512, ink: tuple[int, ...] = INK, background: tuple[int, ...] = CANVAS) -> Image.Image:
    image = Image.new("RGBA", (size, size), background)
    draw = ImageDraw.Draw(image)
    left = (size * 0.20, size * 0.76)
    peak = (size * 0.50, size * 0.24)
    right = (size * 0.80, size * 0.76)
    stroke = max(3, int(size * 0.067))
    _line(draw, left, peak, ink, stroke)
    _line(draw, peak, right, ink, stroke)
    r = size * 0.064
    draw.ellipse((peak[0] - r, peak[1] - r, peak[0] + r, peak[1] + r), fill=TEAL)
    base_y = size * 0.825
    base_w = max(2, int(size * 0.042))
    _line(draw, (size * 0.32, base_y), (size * 0.68, base_y), (*ink[:3], 90), base_w)
    return image


def render_favicon(size: int = 64) -> Image.Image:
    scale = 8
    hi = size * scale
    image = Image.new("RGBA", (hi, hi), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, hi - 1, hi - 1), radius=int(hi * 0.25), fill=INK)
    left = (hi * 0.25, hi * 0.72)
    peak = (hi * 0.50, hi * 0.28)
    right = (hi * 0.75, hi * 0.72)
    stroke = max(8, int(hi * 0.07))
    _line(draw, left, peak, WHITE, stroke)
    _line(draw, peak, right, WHITE, stroke)
    r = hi * 0.058
    draw.ellipse((peak[0] - r, peak[1] - r, peak[0] + r, peak[1] + r), fill=TEAL)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def _copy_svg(name: str, dest: Path, as_name: str | None = None) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    copy2(ASSETS / name, dest / (as_name or name))


def distribute_svg() -> None:
    for name in CANONICAL_SVG:
        source = ASSETS / name
        if not source.is_file():
            raise FileNotFoundError(source)
    _copy_svg("logo.svg", MEDIA)
    _copy_svg("logo-dark.svg", MEDIA)
    _copy_svg("favicon.svg", MEDIA)
    _copy_svg("wordmark.svg", MEDIA)
    public = ROOT / "workbench" / "public"
    _copy_svg("logo.svg", public)
    _copy_svg("favicon.svg", public)
    static = ROOT / "src" / "veyra" / "static" / "workbench"
    _copy_svg("logo.svg", static)
    _copy_svg("favicon.svg", static)
    extension = ROOT / "extensions" / "veyra-workbench" / "media"
    _copy_svg("logo.svg", extension)
    _copy_svg("favicon.svg", extension)
    _copy_svg("icon-activity.svg", extension, "veyra.svg")


def write_logos() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    MEDIA.mkdir(parents=True, exist_ok=True)
    distribute_svg()
    render_mark(512, background=WHITE).save(ASSETS / "logo.png", "PNG")
    render_mark(192, background=WHITE).save(ASSETS / "logo-192.png", "PNG")
    render_favicon(64).save(ASSETS / "favicon.png", "PNG")
    render_favicon(128).save(ASSETS / "icon.png", "PNG")
    copy2(ASSETS / "logo.png", MEDIA / "logo.png")
    copy2(ASSETS / "logo-192.png", MEDIA / "logo-192.png")
    copy2(ASSETS / "favicon.png", MEDIA / "favicon.png")
    public = ROOT / "workbench" / "public"
    public.mkdir(parents=True, exist_ok=True)
    copy2(ASSETS / "logo.png", public / "logo.png")
    copy2(ASSETS / "favicon.png", public / "favicon.png")
    render_favicon(180).save(public / "apple-touch-icon.png", "PNG")
    extension = ROOT / "extensions" / "veyra-workbench" / "media"
    copy2(ASSETS / "icon.png", extension / "icon.png")
    static = ROOT / "src" / "veyra" / "static" / "workbench"
    if static.is_dir():
        copy2(ASSETS / "favicon.png", static / "favicon.png")
        copy2(public / "apple-touch-icon.png", static / "apple-touch-icon.png")


def make_gif(frames: list[Path], dest: Path) -> None:
    images = []
    width = 1280
    for path in frames:
        if not path.is_file():
            continue
        frame = Image.open(path).convert("RGB")
        ratio = width / frame.width
        height = max(1, int(frame.height * ratio))
        frame = frame.resize((width, height), Image.Resampling.LANCZOS)
        images.append(frame)
    if not images:
        raise SystemExit("no screenshot frames")
    dest.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        dest,
        save_all=True,
        append_images=images[1:],
        duration=1600,
        loop=0,
        optimize=True,
    )


if __name__ == "__main__":
    write_logos()
    shots = MEDIA / "screenshots"
    frames = [
        shots / "results.png",
        shots / "catalog.png",
        shots / "console.png",
        shots / "integrity.png",
        shots / "dark.png",
    ]
    if all(path.is_file() for path in frames):
        make_gif(frames, MEDIA / "workbench.gif")
        print("wrote logos and GIF")
    else:
        print("wrote logos; screenshots not ready")
