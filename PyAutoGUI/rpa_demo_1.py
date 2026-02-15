import pyautogui
import webbrowser
import time
import datetime

# Safety setting (move mouse to top-left to stop script)
pyautogui.FAILSAFE = True

# ---------- STEP 1: Open WhatsApp Web ----------
webbrowser.open("https://web.whatsapp.com/")
time.sleep(20)  # wait for QR scan / full load

# ---------- STEP 2: Get today and set message ----------
today = datetime.datetime.now().strftime("%A")

if today == "Sunday":
    status_text = "Happy Sunday 🌞"
else:
    status_text = "Happy Morning 🌸"

# ---------- STEP 3: CLICK COORDINATES (UPDATE THESE) ----------
# Use pyautogui.position() to find exact values

STATUS_BTN = (42, 258)      # My Status
ADD_STATUS = (542, 191)      # +
TEXT_BOX = (584, 294)        # Text area
SEND_BTN = (1845, 958)        # Send

# ---------- STEP 4: Automation steps ----------
pyautogui.click(STATUS_BTN)
time.sleep(2)

pyautogui.click(ADD_STATUS)
time.sleep(2)

pyautogui.click(TEXT_BOX)
time.sleep(1)

pyautogui.typewrite(status_text, interval=0.07)
time.sleep(1)

pyautogui.click(SEND_BTN)
time.sleep(2)

print("✅ WhatsApp status posted successfully")