import pyautogui
import time

# Safety pause (move mouse to corner to stop script)
pyautogui.FAILSAFE = True

# Step 1: Open Browser (Chrome)
pyautogui.press("win")
time.sleep(1)

pyautogui.write("chrome", interval=0.1)
time.sleep(1)

pyautogui.press("enter")
time.sleep(5)  # wait for browser to open

# Step 2: Open WhatsApp Web
pyautogui.write("https://web.whatsapp.com", interval=0.05)
pyautogui.press("enter")
time.sleep(15)  # wait for WhatsApp Web to load

# Step 3: Search Contact (Ctrl + Alt + / opens search box in WhatsApp)
pyautogui.hotkey("ctrl", "alt", "/")
time.sleep(2)

pyautogui.write("vnu", interval=0.1)
time.sleep(2)

pyautogui.press("enter")
time.sleep(2)

# Step 4: Type and Send Message
message = "Hi Vnu I am Bala Welcome to the world"

pyautogui.write(message, interval=0.05)
time.sleep(1)

pyautogui.press("enter")

print("✅ Message sent successfully")
