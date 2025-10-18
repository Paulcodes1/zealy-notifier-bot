import requests
import time
import json
import os
import schedule
import logging
from datetime import datetime
from telegram import Bot
from bs4 import BeautifulSoup
import asyncio

# ===========================
# 🔧 CONFIGURATION
# ===========================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
COMMUNITIES = os.getenv("COMMUNITIES", "").split(",")
CHECK_INTERVAL = 0.5  # in seconds
DATA_FILE = "zealy_tasks.json"
LOG_FILE = "zealy_notifier.log"

# ===========================
# 🧠 SETUP
# ===========================

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Configure logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

def log(message):
    """Log to file and print to console."""
    print(message)
    logging.info(message)

def send_error_to_telegram(error_message):
    """Send error messages to Telegram."""
    try:
        asyncio.run(bot.send_message(
            chat_id=CHAT_ID,
            text=f"⚠️ *Bot Error:* {error_message}",
            parse_mode="Markdown"
        ))
    except Exception as e:
        log(f"Failed to send error alert: {e}")


# ===========================
# 📦 DATA FUNCTIONS
# ===========================

def load_previous_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_current_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ===========================
# 🌐 ZEAly API HANDLER
# ===========================

def fetch_tasks(community_slug):
    """
    Fetch visible quests by scraping the public questboard page.
    """
    url = f"https://zealy.io/cw/{community_slug}/questboard"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        # Zealy renders quests as <div> elements with data-quest-id or similar structure
        quest_divs = soup.find_all("div", attrs={"data-quest-id": True})
        tasks = []
        for div in quest_divs:
            title = div.get_text(strip=True)[:80]  # grab a short snippet
            quest_id = div["data-quest-id"]
            tasks.append({
                "id": quest_id,
                "title": title,
                "url": url
            })

        return tasks

    except requests.exceptions.HTTPError as e:
        print(f"[{community_slug}] Error fetching tasks: {e}")
        return []
    except Exception as e:
        print(f"[{community_slug}] Unexpected error: {e}")
        return []

# ===========================
# 🔍 UPDATE CHECKER
# ===========================

def check_for_updates():
    try:
        log(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking for updates...")
        previous_data = load_previous_data()
        current_data = {}

        for community in COMMUNITIES:
            log(f"🔍 Checking {community}...")
            current_quests = fetch_tasks(community)  # returns a list
            current_data[community] = current_quests

            # Get old quests safely (also a list)
            old_quests = previous_data.get(community, [])
            old_ids = {q.get("id") for q in old_quests if isinstance(q, dict)}
            new_quests = [q for q in current_quests if q.get("id") not in old_ids]

            # Notify for new quests
            if new_quests:
                for quest in new_quests:
                    title = quest.get("title", "Untitled Quest")
                    link = quest.get("url", f"https://zealy.io/cw/{community}/questboard")

                    message = (
                        f"🚀 *New Quest Dropped!*\n\n"
                        f"*Community:* {community}\n"
                        f"*Title:* {title}\n"
                        f"[View Quest 🔗]({link})"
                    )

                    try:
                        log(f"📤 Attempting to send message to Telegram: {message[:60]}...")
                        asyncio.run(bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown"))
                        log(f"✅ New quest found: {title} ({community})")
                    except Exception as send_err:
                        log(f"⚠️ Failed to send message for {title}: {send_err}")
            else:
                log(f"No new quests found for {community}.")

        save_current_data(current_data)
        log("✅ Check complete.")

    except Exception as e:
        error_msg = f"Unexpected error in check_for_updates(): {e}"
        log(error_msg)
        send_error_to_telegram(error_msg)


# ===========================
# DAILY SUMMARY
# ===========================

def send_daily_summary():
    try:
        previous_data = load_previous_data()
        total_quests = 0
        summary_lines = []

        for community, quests in previous_data.items():
            count = len(quests)
            total_quests += count
            summary_lines.append(f"- {community} → {count} quests")

        summary = "\n".join(summary_lines)
        message = (
            f"🗓 *Daily Zealy Summary*\n"
            f"Total Quests: {total_quests}\n"
            f"{summary}\n"
            f"⏰ Checked at {datetime.now().strftime('%H:%M')}"
        )

        log(f"📤 Attempting to send message to Telegram: {message[:60]}...")
        asyncio.run(bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown"))
        log("📊 Daily summary sent successfully.")
    except Exception as e:
        error_msg = f"Error sending daily summary: {e}"
        log(error_msg)
        send_error_to_telegram(error_msg)



# ===========================
# 🕒 SCHEDULER
# ===========================

def main():
    log("🤖 Zealy Notifier Bot Started...")
    log(f"Tracking communities: {', '.join(COMMUNITIES)}")
    check_for_updates()  # initial run

    schedule.every(30).seconds.do(check_for_updates)
    schedule.every().day.at("07:00").do(send_daily_summary)

    while True:
        schedule.run_pending()
        time.sleep(5)


from flask import Flask
import threading

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Zealy Notifier Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=10000)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()  # keep web server alive
    main()



if __name__ == "__main__":
    main()
