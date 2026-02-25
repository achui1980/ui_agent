from __future__ import annotations

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from loguru import logger

from src.config import Settings


class BrowserManager:
    """Manages Playwright browser lifecycle."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Browser not started. Call start() first.")
        return self._page

    def start(self) -> Page:
        logger.info("Starting Playwright browser...")
        self._playwright = sync_playwright().start()

        launch_args: dict = {
            "headless": self._settings.browser_headless,
        }
        if self._settings.browser_proxy:
            launch_args["proxy"] = {"server": self._settings.browser_proxy}

        self._browser = self._playwright.chromium.launch(**launch_args)
        self._context = self._browser.new_context(
            viewport={
                "width": self._settings.browser_viewport_width,
                "height": self._settings.browser_viewport_height,
            },
        )
        self._context.set_default_timeout(self._settings.browser_timeout)
        self._context.set_default_navigation_timeout(
            self._settings.browser_navigation_timeout
        )
        self._page = self._context.new_page()
        logger.info("Browser started successfully.")
        return self._page

    def navigate(self, url: str) -> None:
        logger.info(f"Navigating to {url}")
        self.page.goto(url, wait_until="networkidle")
        logger.info(f"Navigation complete: {self.page.title()}")

    def close(self) -> None:
        logger.info("Closing browser...")
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        logger.info("Browser closed.")
