"""Veyra Instrument — design tokens.

Journal layout: ink, graphite, one teal accent, hairlines.
Not affiliated with OpenAI. Inter stands in for OpenAI Sans.
"""

from __future__ import annotations

FONT_SANS = 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, ui-sans-serif, system-ui, sans-serif'
FONT_SERIF = 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
FONT_MONO = 'ui-monospace, "SF Mono", Menlo, Consolas, monospace'

LIGHT = {
    "bg": "#ffffff",
    "bg_soft": "#ffffff",
    "surface": "#ffffff",
    "text": "#0d0d0d",
    "muted": "#6e6e6e",
    "graphite": "#3c3c3c",
    "subtle": "#9b9b9b",
    "border": "#e5e5e5",
    "border_strong": "#e5e5e5",
    "hover": "#f4f4f4",
    "accent": "#10a37f",
    "accent_hover": "#0e8c6d",
    "accent_soft": "rgba(16,163,127,0.12)",
    "danger": "#3c3c3c",
    "warning": "#3c3c3c",
}

DARK = {
    "bg": "#0d0d0d",
    "bg_soft": "#0d0d0d",
    "surface": "#0d0d0d",
    "text": "#ffffff",
    "muted": "#9b9b9b",
    "graphite": "#9b9b9b",
    "subtle": "#6e6e6e",
    "border": "#262626",
    "border_strong": "#262626",
    "hover": "#1a1a1a",
    "accent": "#10a37f",
    "accent_hover": "#12b38c",
    "accent_soft": "rgba(16,163,127,0.16)",
    "danger": "#9b9b9b",
    "warning": "#9b9b9b",
}

RADIUS = "12px"
RADIUS_SM = "12px"
RADIUS_PILL = "9999px"
DURATION = "180ms"
EASE = "cubic-bezier(0.25, 0.1, 0.25, 1)"
FOCUS_RING = "0 0 0 3px rgba(16,163,127,0.12)"
