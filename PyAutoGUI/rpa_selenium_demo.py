from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import os
from datetime import datetime

# ---------- Setup ----------
os.makedirs("screenshots/pass", exist_ok=True)
os.makedirs("screenshots/fail", exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

options = Options()
options.add_argument("--start-maximized")

driver = webdriver.Chrome(options=options)

try:
    # ---------- STEP 1: Open login page ----------
    driver.get("https://the-internet.herokuapp.com/login")
    time.sleep(2)

    # ---------- STEP 2: Enter username ----------
    driver.find_element(By.ID, "username").send_keys("tomsmith")

    # ---------- STEP 3: Enter password ----------
    driver.find_element(By.ID, "password").send_keys("SuperSecretPassword!")

    # ---------- STEP 4: Click login ----------
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(2)

    # ---------- STEP 5: Validation ----------
    success_msg = driver.find_element(By.ID, "flash").text

    if "You logged into a secure area!" in success_msg:
        screenshot_path = f"screenshots/pass/login_pass_{timestamp}.png"
        driver.save_screenshot(screenshot_path)
        print("✅ LOGIN TEST PASSED")
        print("📸 Screenshot:", screenshot_path)
    else:
        raise Exception("Login failed message not found")

except Exception as e:
    screenshot_path = f"screenshots/fail/login_fail_{timestamp}.png"
    driver.save_screenshot(screenshot_path)
    print("❌ LOGIN TEST FAILED")
    print("📸 Screenshot:", screenshot_path)
    print("Error:", e)

finally:
    driver.quit()
