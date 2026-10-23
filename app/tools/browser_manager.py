import os
import ctypes
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from app.core.config import BASE_DIR

LOCAL_TEST_FORM_URL = (BASE_DIR / "data" / "test_form.html").resolve().as_uri()


def ensure_default_desktop():
    """
    On Windows, ensures the calling thread is attached to the interactive user
    desktop ('WinSta0\\Default') so headed Playwright Chromium windows physically
    appear and pop up on the user's active monitor screen.
    """
    if os.name != "nt":
        return
    try:
        u32 = ctypes.windll.user32
        # DESKTOP_ALL_ACCESS = 0x01FF
        h_default = u32.OpenDesktopW("default", 0, False, 0x01FF)
        if h_default:
            u32.SetThreadDesktop(h_default)
    except Exception:
        pass


def bring_process_windows_to_front():
    """
    Finds top-level Chromium windows on the default desktop and raises them
    to the foreground with SW_RESTORE and SW_MAXIMIZE.
    """
    if os.name != "nt":
        return
    try:
        u32 = ctypes.windll.user32
        h_default = u32.OpenDesktopW("default", 0, False, 0x01FF)
        if not h_default:
            return

        ctypes.windll.user32.AllowSetForegroundWindow(-1)

        def enum_cb(hwnd, lparam):
            if u32.IsWindowVisible(hwnd):
                length = u32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    u32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value.lower()
                    if any(token in title for token in ["chromium", "chrome", "greenhouse", "gitlab", "ashby", "lever", "job", "application"]):
                        u32.ShowWindow(hwnd, 9)  # SW_RESTORE
                        u32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
                        u32.SetForegroundWindow(hwnd)
            return True

        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        u32.EnumDesktopWindows(h_default, EnumWindowsProc(enum_cb), 0)
    except Exception:
        pass


class BrowserManager:
    """
    Manages Playwright browser lifecycle (Chromium) in headed or headless mode.
    Allows automated form filling while supporting human intervention pauses.
    """

    def __init__(self, headless: bool = False):
        self.headless = headless
        self._playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def start(self) -> Page:
        """Launches the Chromium browser and opens a fresh viewport."""
        ensure_default_desktop()
        self._playwright = await async_playwright().start()
        # Launch Chromium with explicit desktop window positioning
        launch_args = [
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",
            "--window-position=50,50",
            "--window-size=1366,850",
        ]
        self.browser = await self._playwright.chromium.launch(
            headless=self.headless,
            slow_mo=50,  # 50ms human-like typing pause
            args=launch_args
        )
        if not self.headless:
            # no_viewport allows Chromium to display at full OS window dimensions on the desktop
            self.context = await self.browser.new_context(no_viewport=True)
        else:
            self.context = await self.browser.new_context(
                viewport={"width": 1280, "height": 800}
            )
        self.page = await self.context.new_page()
        if not self.headless:
            try:
                await self.page.bring_to_front()
            except Exception:
                pass
            bring_process_windows_to_front()
        return self.page

    async def goto(self, url: str):
        """Navigates to URL and waits for DOM network idle."""
        if not self.page:
            raise RuntimeError("Browser not started. Call await manager.start() first.")
        ensure_default_desktop()
        await self.page.goto(url, wait_until="domcontentloaded")
        if not self.headless:
            try:
                await self.page.bring_to_front()
            except Exception:
                pass
            bring_process_windows_to_front()

    def is_open(self) -> bool:
        """Returns True if the browser and page are still active and open."""
        try:
            return bool(
                self.browser
                and self.browser.is_connected()
                and self.page
                and not self.page.is_closed()
            )
        except Exception:
            return False

    async def bring_to_front(self):
        """Brings active page window to desktop foreground."""
        ensure_default_desktop()
        if self.page and not self.page.is_closed():
            try:
                await self.page.bring_to_front()
            except Exception:
                pass
        bring_process_windows_to_front()

    async def close(self):
        """Gracefully closes browser and cleans up Playwright processes."""
        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass
        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
