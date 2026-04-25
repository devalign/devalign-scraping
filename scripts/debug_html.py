import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        url = "https://www.computrabajo.com.pe/trabajo-de-desarrollador"
        print(f"Navigating to {url}")
        await page.goto(url, wait_until="networkidle")

        # Get first job link
        links = await page.query_selector_all("a.js-o-link")
        if links:
            job_url = await links[0].get_attribute("href")
            # If relative, make absolute
            if job_url.startswith("/"):
                job_url = "https://www.computrabajo.com.pe" + job_url
            print(f"Navigating to job: {job_url}")
            await page.goto(job_url, wait_until="networkidle")
            await asyncio.sleep(2)  # Extra wait
            content = await page.content()
            with open("brain/debug_job.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("HTML saved to brain/debug_job.html")
        else:
            print("No links found")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
