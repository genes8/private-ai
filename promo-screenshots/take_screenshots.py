"""Take promotional screenshots of Private-AI for the landing page."""

import asyncio
import os
from pathlib import Path

from playwright.async_api import async_playwright

SCREENSHOT_DIR = Path("/Users/enes/Desktop/Dev/agents/private-ai/promo-screenshots")
BASE_URL = "http://localhost:3000"
ADMIN_EMAIL = "admin@safe4ai.local"
ADMIN_PASSWORD = "Admin1234!Strong"

# Desktop viewport
DESKTOP = {"width": 1440, "height": 900}
# Mobile viewport
MOBILE = {"width": 375, "height": 812}

SAVE_DIR = str(SCREENSHOT_DIR)


async def take_screenshots():
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport=DESKTOP,
            device_scale_factor=2,  # Retina-quality screenshots
        )
        page = await context.new_page()

        # === 1. LOGIN PAGE ===
        print("1. Login page")
        await page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=os.path.join(SAVE_DIR, "01-login-page.png"))

        # === 2. LOGIN AS ADMIN ===
        print("2. Logging in as admin...")
        email_input = page.locator('input[type="email"], input[name="email"]')
        password_input = page.locator('input[type="password"], input[name="password"]')
        
        await email_input.first.fill(ADMIN_EMAIL)
        await password_input.first.fill(ADMIN_PASSWORD)
        
        submit = page.locator('button[type="submit"]')
        await submit.first.click()
        
        await page.wait_for_url("**/chat**", timeout=15000)
        await page.wait_for_timeout(2000)

        # === 3. EMPTY CHAT STATE ===
        print("3. Empty chat")
        await page.screenshot(path=os.path.join(SAVE_DIR, "02-chat-empty.png"))

        # === 4. SEND CHAT MESSAGE ===
        print("4. Sending chat message...")
        textarea = page.locator('textarea')
        await textarea.fill("What is the annual leave policy for employees?")
        await page.wait_for_timeout(300)
        
        # Use the send button (aria-label="Send message")
        send_btn = page.locator('button[aria-label="Send message"]')
        if await send_btn.count() > 0:
            await send_btn.click()
        else:
            await textarea.press("Enter")
        
        # Wait for response — poll for assistant answer to appear
        print("   Waiting for AI response...")
        for i in range(45):
            await page.wait_for_timeout(2000)
            body_text = await page.inner_text('body')
            # Look for key phrases that indicate the response is complete
            if 'annual leave' in body_text.lower() or '20 days' in body_text:
                # Give a bit more time for rendering to settle
                await page.wait_for_timeout(2000)
                print(f"   Response found after {(i+1)*2}s")
                break
            if i % 5 == 4:
                print(f"   ... still waiting ({(i+1)*2}s)")
        else:
            print("   Timeout waiting for response, taking screenshot anyway")
        
        await page.screenshot(path=os.path.join(SAVE_DIR, "03-chat-response.png"))
        print("   03-chat-response.png saved")

        # === 5. ADMIN OVERVIEW ===
        print("5. Admin overview")
        await page.goto(f"{BASE_URL}/admin/overview", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        await page.screenshot(path=os.path.join(SAVE_DIR, "04-admin-overview.png"))

        # === 6. ADMIN DOCUMENTS ===
        print("6. Admin documents")
        await page.goto(f"{BASE_URL}/admin/documents", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        await page.screenshot(path=os.path.join(SAVE_DIR, "05-admin-documents.png"))

        # === 7. ADMIN AUDIT ===
        print("7. Admin audit")
        await page.goto(f"{BASE_URL}/admin/audit", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        await page.screenshot(path=os.path.join(SAVE_DIR, "06-admin-audit.png"))

        # === 8. ADMIN FEEDBACK ===
        print("8. Admin feedback")
        await page.goto(f"{BASE_URL}/admin/feedback", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        await page.screenshot(path=os.path.join(SAVE_DIR, "07-admin-feedback.png"))

        # === 9. ADMIN USERS ===
        print("9. Admin users")
        await page.goto(f"{BASE_URL}/admin/users", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        await page.screenshot(path=os.path.join(SAVE_DIR, "08-admin-users.png"))

        # === 10. ADMIN SETTINGS ===
        print("10. Admin settings")
        await page.goto(f"{BASE_URL}/admin/settings", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        await page.screenshot(path=os.path.join(SAVE_DIR, "09-admin-settings.png"))

        # === MOBILE SCREENSHOTS ===
        print("Switching to mobile viewport...")
        await page.set_viewport_size(MOBILE)

        # === 11. MOBILE LOGIN ===
        print("11. Mobile login")
        await page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=os.path.join(SAVE_DIR, "10-mobile-login.png"))

        # === 12. MOBILE CHAT ===
        print("12. Mobile chat")
        # Login on mobile first
        email_input = page.locator('input[type="email"], input[name="email"]')
        password_input = page.locator('input[type="password"], input[name="password"]')
        await email_input.first.fill(ADMIN_EMAIL)
        await password_input.first.fill(ADMIN_PASSWORD)
        await page.locator('button[type="submit"]').first.click()
        await page.wait_for_url("**/chat**", timeout=15000)
        await page.wait_for_timeout(2000)
        await page.screenshot(path=os.path.join(SAVE_DIR, "11-mobile-chat.png"))

        # === 13. MOBILE ADMIN OVERVIEW ===
        print("13. Mobile admin overview")
        await page.goto(f"{BASE_URL}/admin/overview", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        await page.screenshot(path=os.path.join(SAVE_DIR, "12-mobile-admin-overview.png"))

        await browser.close()
        print(f"\nAll screenshots saved to {SCREENSHOT_DIR}")


if __name__ == "__main__":
    asyncio.run(take_screenshots())
