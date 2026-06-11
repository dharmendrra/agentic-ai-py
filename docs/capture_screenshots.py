#!/usr/bin/env python3
"""Capture HD showcase screenshots for docs/screenshots/ (Python UI).

Services must be running: agent :8082, retrieval :8081.
  pip install playwright && python -m playwright install chromium
  python docs/capture_screenshots.py

High definition: 1600x1000 viewport at device_scale_factor=2 (=> 3200x2000 PNGs).
Answer shot reopens an existing web-cited conversation (no slow live LLM needed).
"""
from __future__ import annotations

import asyncio
import pathlib
from playwright.async_api import async_playwright

CHAT = "http://localhost:8082"
INGEST = "http://localhost:8081"
OUT = pathlib.Path(__file__).parent / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
# A conversation (in shared Mongo) whose assistant answer carries web citations.
WEB_CONVO_TEXT = "throne? searc"


async def shot(page, name):
    await page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
    print(f"  wrote screenshots/{name}.png")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1600, "height": 1000},
                                        device_scale_factor=2)
        page = await ctx.new_page()

        await page.goto(CHAT, wait_until="networkidle")
        await page.wait_for_timeout(700)
        await shot(page, "chat-hero")

        # toggles on
        try:
            await page.click("#webToggle"); await page.click("#libToggle")
            await page.wait_for_timeout(250)
            await shot(page, "source-toggles")
            await page.click("#webToggle"); await page.click("#libToggle")  # reset
        except Exception as e:
            print(f"  [skip] source-toggles: {e}")

        # answer with clickable web citations — reopen an existing conversation
        try:
            await page.click(f'.conv-item:has-text("{WEB_CONVO_TEXT}")', timeout=8000)
            await page.wait_for_selector(".bubble.assistant .tags a", timeout=15000)
            await page.wait_for_timeout(500)
            await shot(page, "answer-web-citations")
            await shot(page, "sidebar-conversations")  # sidebar visible alongside
        except Exception as e:
            print(f"  [skip] answer-web-citations (need a persisted web convo): {e}")
            await shot(page, "sidebar-conversations")

        # ingest page
        await page.goto(INGEST, wait_until="networkidle")
        await page.wait_for_timeout(500)
        await shot(page, "ingest-dropzone")
        try:
            await page.eval_on_selector("#searchBtn", "el => el.scrollIntoView({block:'center'})")
            await page.wait_for_timeout(300)
            await shot(page, "ingest-search-test")
        except Exception as e:
            print(f"  [skip] ingest-search-test: {e}")

        await browser.close()
    print("Done -> docs/screenshots/")


if __name__ == "__main__":
    asyncio.run(main())
