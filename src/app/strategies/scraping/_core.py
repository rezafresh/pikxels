import json
from datetime import datetime
from typing import cast

import arrow
from fastapi import HTTPException
from playwright.sync_api import sync_playwright

from ... import settings
from ._utils import phaser_land_state_getter

DEFAULT_TIMEOUT = 60000 * 15  # 15 minutes


def get_land_state(land_number: int) -> dict:
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.connect_over_cdp(
                settings.BROWSERLESS_URL, timeout=DEFAULT_TIMEOUT
            )
        except Exception:
            raise HTTPException(
                422, "An error has ocurred while connecting to the chrome instance"
            )

        context = browser.new_context()
        page = context.new_page()
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
            context.close()
            browser.close()

    return state


def parse_tree_data(state: dict) -> list[dict]:
    entities: dict = state["entities"]
    results = []

    for item in entities.values():
        if not cast(str, item["entity"]).startswith("ent_tree"):
            continue

        try:
            next_respawn = datetime.fromtimestamp(item["generic"]["utcRefresh"] / 1000)
            next_respawn_h = arrow.get(next_respawn).humanize(
                datetime.now(), granularity=["hour", "minute", "second"]
            )
        except Exception:
            next_respawn, next_respawn_h = None

        results.append(
            {
                "entity": item["entity"],
                "position": item["position"],
                "next_respawn": next_respawn,
                "next_respawn_h": next_respawn_h,
                "current_state": item["generic"]["state"],
            }
        )

    return sorted(results, key=lambda _: (_["next_respawn"] or 0))
