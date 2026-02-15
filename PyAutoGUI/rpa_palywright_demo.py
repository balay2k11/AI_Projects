from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # STEP 1: Launch Chromium browser
    browser = p.chromium.launch(headless=True)

    # STEP 2: Create page
    page = browser.new_page()

    # STEP 3: Open website
    page.goto("https://www.google.com/", timeout=60000)

    # STEP 4: Wait for page to fully load
    page.wait_for_load_state("networkidle")

    # STEP 5: Generate PDF
    page.pdf(
        path="pdfs/example_page.pdf",
        format="A4",
        print_background=True
    )

    print("✅ PDF generated successfully")

    # STEP 6: Close browser
    browser.close()
