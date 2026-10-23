from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from playwright.async_api import Page


class PageSecurityStatus(BaseModel):
    is_blocked: bool = Field(..., description="True if a CAPTCHA, login wall, or challenge is detected")
    block_type: Optional[str] = Field(default=None, description="'captcha', 'cloudflare', 'login_wall', or None")
    reason: str = Field(..., description="Human-readable explanation of why the agent paused")
    requires_human_intervention: bool = Field(default=False)


# Common signatures for bot challenges and login gates
CAPTCHA_SELECTORS = [
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    "iframe[src*='challenges.cloudflare.com']",
    "#cf-challenge-running",
    ".g-recaptcha",
    ".h-captcha",
    "#turnstile-wrapper"
]

LOGIN_WALL_SELECTORS = [
    "input[type='password']",
    "form[action*='login']",
    "form[action*='signin']",
    "#login-form",
    ".sso-button"
]


async def check_page_security(page: Page) -> PageSecurityStatus:
    """
    Inspects page DOM and title for CAPTCHAs, Cloudflare challenges, and login walls.
    STRICT CONSTRAINT: Never attempt to bypass them. Detect and hand off to human.
    """
    # 1. Check for CAPTCHAs & Cloudflare Challenges
    for selector in CAPTCHA_SELECTORS:
        try:
            el = await page.query_selector(selector)
            if el and await el.is_visible():
                return PageSecurityStatus(
                    is_blocked=True,
                    block_type="captcha",
                    reason=f"CAPTCHA / Bot challenge detected ({selector}). Automation paused for user completion.",
                    requires_human_intervention=True
                )
        except Exception:
            continue

    # Check page title and content for Cloudflare blocks
    page_title = (await page.title()).lower()
    if any(k in page_title for k in ["just a moment...", "attention required", "security check"]):
        return PageSecurityStatus(
            is_blocked=True,
            block_type="cloudflare",
            reason="Cloudflare bot protection screen detected. Automation paused.",
            requires_human_intervention=True
        )

    # 2. Check for Mandatory Login Walls
    for selector in LOGIN_WALL_SELECTORS:
        try:
            el = await page.query_selector(selector)
            if el and await el.is_visible():
                return PageSecurityStatus(
                    is_blocked=True,
                    block_type="login_wall",
                    reason=f"Mandatory login wall detected ({selector}). Please sign in to proceed.",
                    requires_human_intervention=True
                )
        except Exception:
            continue

    # Page is clean and accessible
    return PageSecurityStatus(
        is_blocked=False,
        block_type=None,
        reason="No security barriers detected. Safe to proceed with form filling.",
        requires_human_intervention=False
    )