from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import threading
import os

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN ortam değişkeni ayarlanmamış!")

bot = TeleBot(TOKEN)
db_lock = threading.Lock()

DB_PATH = os.path.join(os.getcwd(), 'users.db')

CHANNELS = [
    {"id": "https://t.me/+CH21FDcuHR0zZmE0", "name": "1. Kanal", "url": "https://t.me/+CH21FDcuHR0zZmE0", "check": False},
    {"id": "@Regsafetelegramin", "name": "2. Kanal", "url": "https://t.me/Regsafetelegramin", "check": True},
    {"id": "@ykssorulari0", "name": "3. Kanal", "url": "https://t.me/ykssorulari0", "check": True},
]

FINAL_CHANNEL = "https://t.me/ykssorulari0"

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users 
             (user_id INTEGER PRIMARY KEY, referrals INTEGER DEFAULT 0, 
              inviter INTEGER, verified INTEGER DEFAULT 0)''')
conn.commit()

def get_user_data(user_id):
    with db_lock:
        c.execute("SELECT referrals, inviter, verified FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        if not result:
            c.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            conn.commit()
            return 0, None, 0
        return result

def update_referrals(user_id, count):
    with db_lock:
        if count > 5:
            count = 5
        c.execute("UPDATE users SET referrals = ? WHERE user_id = ?", (count, user_id))
        conn.commit()

def set_inviter(new_user_id, inviter_id):
    with db_lock:
        c.execute("UPDATE users SET inviter = ? WHERE user_id = ?", (inviter_id, new_user_id))
        conn.commit()

def set_verified(user_id):
    with db_lock:
        c.execute("UPDATE users SET verified = 1, inviter = NULL WHERE user_id = ?", (user_id,))
        conn.commit()

def is_joined_all(user_id):
    for ch in CHANNELS:
        if not ch.get("check", False):
            continue
        try:
            chat_id = ch["id"]
            status = bot.get_chat_member(chat_id, user_id).status
            if status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
    return True

def get_referral_link(user_id):
    return f"https://t.me/{bot.get_me().username}?start=ref{user_id}"

def get_share_url(user_id):
    ref = get_referral_link(user_id)
    text = "YKS%202026%20Sorular%C4%B1%20Bu%20Botta%20tek%20ger%C3%A7ek"
    return f"https://t.me/share/url?url={ref}&text={text}"

def create_main_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    for ch in CHANNELS:
        markup.add(InlineKeyboardButton(text=ch["name"], url=ch["url"]))
    markup.add(InlineKeyboardButton("✅ Kanallara Katıldım", callback_data="i_joined"))
    return markup

@bot.callback_query_handler(func=lambda call: call.data == "i_joined")
def handle_joined(call):
    user_id = call.from_user.id
    referrals, current_inviter, verified = get_user_data(user_id)

    if verified == 1:
        bot.answer_callback_query(call.id, "✅ Zaten doğrulandı.", show_alert=True)
        return

    if not is_joined_all(user_id):
        bot.answer_callback_query(call.id, "❌ Henüz tüm zorunlu kanallara katılmadın!", show_alert=True)
        return

    set_verified(user_id)

    if current_inviter:
        try:
            inviter_referrals, _, _ = get_user_data(current_inviter)
            if inviter_referrals < 5:
                new_count = inviter_referrals + 1
                update_referrals(current_inviter, new_count)
                bot.send_message(current_inviter, f"✅ Tebrikler! Referansınla birisi doğrulandı.\nReferans sayın: **{new_count}/5**", parse_mode="Markdown")
            else:
                bot.send_message(current_inviter, "✅ Referansın zaten 5/5 tamamlandı.")
        except:
            pass

    bot.answer_callback_query(call.id, "✅ Doğrulandı! Teşekkürler.", show_alert=True)

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🤝 Botu 5 Kişiyle Paylaş", url=get_share_url(user_id)))

    bot.send_message(user_id,
        "🎉 **Doğrulandı!**\n\n"
        "🔥 Botu **5 kişiyle** paylaş ve YKS sorularına eriş.\n"
        f"İlerleme: **{referrals}/5**",
        reply_markup=markup,
        parse_mode="Markdown")

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    args = message.text.split()

    if len(args) > 1 and args[1].startswith("ref"):
        try:
            inviter_id = int(args[1][3:])
            if inviter_id != user_id:
                _, _, verified = get_user_data(user_id)
                if verified == 0:
                    set_inviter(user_id, inviter_id)
                    bot.send_message(inviter_id, "🔥 Birisi senin referansınla katıldı.\n'Katıldım' butonuna bastığında referansın artacak!")
        except:
            pass

    referrals, _, verified = get_user_data(user_id)
    joined = is_joined_all(user_id)

    if joined and verified == 0:
        bot.send_message(user_id,
            "✅ **Tüm kanallara katıldın!**\n\n"
            "Aşağıdaki butona basarak doğrula:",
            reply_markup=create_main_markup(),
            parse_mode="Markdown")
    elif verified == 1 or referrals >= 5:
        bot.send_message(user_id,
            "🎉 **Tebrikler!** 5/5 tamamlandı.\n\n"
            f"**YKS 2026 soruları** burada:\n{FINAL_CHANNEL}",
            disable_web_page_preview=True,
            parse_mode="Markdown")
    else:
        bot.send_message(user_id,
            "👋 **Merhaba!**\n\n"
            "🔥 **2026 YKS soru ve cevaplarına** ulaşmak için aşağıdaki kanallara katıl:",
            reply_markup=create_main_markup(),
            disable_web_page_preview=True,
            parse_mode="Markdown")

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    if message.text and "start" in message.text.lower():
        start(message)

print("✅ YKS Botu çalışıyor...")
bot.infinity_polling(timeout=40, long_polling_timeout=40)
