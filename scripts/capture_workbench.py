"""Capture real Workbench screenshots into docs/media."""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "media" / "screenshots"
URL = "http://127.0.0.1:8765/"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        page.add_init_script("localStorage.setItem('veyra-theme', 'light');")
        page.emulate_media(color_scheme="light")
        page.goto(URL, wait_until="networkidle")
        page.wait_for_selector("text=Dashboard")
        page.get_by_role("button", name="Play").first.click()
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "results.png"), full_page=False)

        page.get_by_role("button", name="Heat Diffusion", exact=True).first.click()
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / "heat.png"), full_page=False)
        page.screenshot(path=str(OUT / "model.png"), full_page=False)
        page.screenshot(path=str(OUT / "integrity.png"), full_page=False)

        page.get_by_role("button", name="Catalog").click()
        page.wait_for_timeout(250)
        page.screenshot(path=str(OUT / "catalog.png"), full_page=False)

        page.get_by_role("button", name="Instruments").click()
        page.wait_for_timeout(250)
        page.screenshot(path=str(OUT / "console.png"), full_page=False)

        page.get_by_role("button", name="Dashboard").click()
        page.get_by_role("button", name="Oscillator", exact=True).first.click()
        page.get_by_role("button", name="Dark").click()
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "dark.png"), full_page=False)
        browser.close()
    print("saved", OUT)


if __name__ == "__main__":
    main()
