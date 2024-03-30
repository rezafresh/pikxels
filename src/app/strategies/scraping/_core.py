import json
from datetime import datetime
from typing import cast

from fastapi import HTTPException
from playwright.sync_api import ViewportSize, sync_playwright

from ... import settings
from ._utils import phaser_land_state_getter

DEFAULT_TIMEOUT = 60000 * 5  # 5 minutes


def get_land_state(land_number: int) -> dict:
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(settings.BROWSERLESS_URL)
        ctx = browser.new_context(viewport=ViewportSize(width=1920, height=1080))
        page = ctx.new_page()
        page.set_default_navigation_timeout(DEFAULT_TIMEOUT)
        page.set_default_timeout(DEFAULT_TIMEOUT)

        try:
            if not page.goto(f"https://play.pixels.xyz/pixels/share/{land_number}").ok:
                raise HTTPException(
                    404, "An error has ocurred while navigating to the land"
                )

            page.wait_for_load_state("load")

            try:
                state_str = phaser_land_state_getter(page)
            except Exception:
                raise HTTPException(422, "Could not fetch the land state")

            try:
                state = json.loads(state_str)
            except Exception:
                raise HTTPException(422, "Could not parse land state data")
        finally:
            page.close()
            ctx.close()
            browser.close()

    return state


def extract_tree_data(state: dict) -> list[dict]:
    entities: dict = state["entities"]
    results = []

    for item in entities.values():
        if not cast(str, item["entity"]).startswith("ent_tree"):
            continue

        try:
            next_respawn = datetime.fromtimestamp(item["generic"]["utcRefresh"] / 1000)
        except Exception:
            next_respawn = None

        results.append(
            {
                "entity": item["entity"],
                "position": item["position"],
                "next_respawn": next_respawn,
                "current_state": item["generic"]["state"],
            }
        )

    return sorted(results, key=lambda _: (_["next_respawn"] or 0))
