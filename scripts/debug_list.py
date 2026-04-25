import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        url = "https://www.computrabajo.com.pe/trabajo-de-desarrollador"
        print(f"Navigating to {url}")
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            content = await page.content()
            with open("debug_list.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("List HTML saved to debug_list.html")
        except Exception as e:
            print(f"Error: {e}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
