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
REFERRAL_GOAL = 5
TOP_N = 5

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users 
             (user_id INTEGER PRIMARY KEY, referrals INTEGER DEFAULT 0, 
              inviter INTEGER, verified INTEGER DEFAULT 0,
              first_name TEXT)''')
conn.commit()

# first_name sütunu yoksa ekle (eski db uyumluluğu)
try:
    c.execute("ALTER TABLE users ADD COLUMN first_name TEXT")
    conn.commit()
except:
    pass

def get_user_data(user_id):
    with db_lock:
        c.execute("SELECT referrals, inviter, verified FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        if not result:
            c.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            conn.commit()
            return 0, None, 0
        return result

def update_first_name(user_id, first_name):
    with db_lock:
        c.execute("UPDATE users SET first_name = ? WHERE user_id = ?", (first_name, user_id))
        conn.commit()

def update_referrals(user_id, count):
    with db_lock:
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

def get_top_users(limit=TOP_N):
    with db_lock:
        c.execute(
            "SELECT user_id, referrals, first_name FROM users ORDER BY referrals DESC LIMIT ?",
            (limit,)
        )
        return c.fetchall()

def is_in_top(user_id):
    top = get_top_users()
    ids = [row[0] for row in top]
    return user_id in ids and len([r for r in top if r[0] == user_id and r[1] > 0]) > 0

def is_joined_all(user_id):
    for ch in CHANNELS:
        if not ch.get("check", False):
            continue
        try:
            status = bot.get_chat_member(ch["id"], user_id).status
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

def format_leaderboard():
    top = get_top_users()
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lines = ["🏆 *Liderlik Tablosu* 🏆\n"]
    for i, (uid, refs, fname) in enumerate(top):
        name = fname if fname else f"Kullanıcı {uid}"
        medal = medals[i] if i < len(medals) else f"{i+1}."
        lines.append(f"{medal} {name} — *{refs} referans*")
    if not top or top[0][1] == 0:
        lines.append("_Henüz kimse referans kazanmadı._")
    lines.append(f"\n🎯 İlk {TOP_N}'e gir, YKS sorularına *bedava* eriş!")
    return "\n".join(lines)

# ====================== KATILDIM BUTONU ======================
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
            new_count = inviter_referrals + 1
            update_referrals(current_inviter, new_count)

            # Davet eden ilk 5'e girdiyse bildir
            top_ids = [r[0] for r in get_top_users()]
            if current_inviter in top_ids:
                pos = top_ids.index(current_inviter) + 1
                bot.send_message(
                    current_inviter,
                    f"✅ Referansınla birisi doğrulandı! Referans sayın: *{new_count}*\n"
                    f"🏆 Şu an liderlik tablosunda *{pos}. sıradasın!*",
                    parse_mode="Markdown"
                )
                # İlk 5'e yeni girdiyse erişim ver
                if pos <= TOP_N and new_count == 1 or pos == TOP_N:
                    bot.send_message(
                        current_inviter,
                        f"🎉 Tebrikler! İlk {TOP_N}'e girdin!\n\n"
                        f"**YKS 2026 soruları** burada:\n{FINAL_CHANNEL}",
                        disable_web_page_preview=True,
                        parse_mode="Markdown"
                    )
            else:
                bot.send_message(
                    current_inviter,
                    f"✅ Referansınla birisi doğrulandı! Referans sayın: *{new_count}*",
                    parse_mode="Markdown"
                )
        except:
            pass

    bot.answer_callback_query(call.id, "✅ Doğrulandı! Teşekkürler.", show_alert=True)

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🤝 Botu Arkadaşlarınla Paylaş", url=get_share_url(user_id)))
    markup.add(InlineKeyboardButton("🏆 Liderlik Tablosu", callback_data="leaderboard"))

    bot.send_message(
        user_id,
        f"🎉 *Doğrulandı!*\n\n"
        f"🔥 Botu paylaş, referans kazan!\n"
        f"📌 *{REFERRAL_GOAL} referans* ile erişim kazan\n"
        f"🏆 İlk *{TOP_N}'e* gir → *Bedava erişim!*\n\n"
        f"İlerleme: *{referrals} referans*",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# ====================== LİDERLİK TABLOSU CALLBACK ======================
@bot.callback_query_handler(func=lambda call: call.data == "leaderboard")
def handle_leaderboard(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.from_user.id, format_leaderboard(), parse_mode="Markdown")

# ====================== START ======================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or f"Kullanıcı"
    update_first_name(user_id, first_name)

    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref"):
        try:
            inviter_id = int(args[1][3:])
            if inviter_id != user_id:
                _, _, verified = get_user_data(user_id)
                if verified == 0:
                    set_inviter(user_id, inviter_id)
                    bot.send_message(inviter_id, "🔥 Birisi senin referansınla katıldı!\n'Kanallara Katıldım' butonuna basınca referansın artacak.")
        except:
            pass

    referrals, _, verified = get_user_data(user_id)
    joined = is_joined_all(user_id)
    in_top = is_in_top(user_id) and referrals > 0

    if verified == 1 and (referrals >= REFERRAL_GOAL or in_top):
        bot.send_message(
            user_id,
            f"🎉 *Tebrikler!*\n\n"
            f"**YKS 2026 soruları** burada:\n{FINAL_CHANNEL}",
            disable_web_page_preview=True,
            parse_mode="Markdown"
        )
    elif joined and verified == 0:
        bot.send_message(
            user_id,
            "✅ *Tüm kanallara katıldın!*\n\nAşağıdaki butona basarak doğrula:",
            reply_markup=create_main_markup(),
            parse_mode="Markdown"
        )
    else:
        markup = create_main_markup()
        bot.send_message(
            user_id,
            f"👋 *Merhaba {first_name}!*\n\n"
            f"🔥 *2026 YKS soru ve cevaplarına* ulaşmak için:\n\n"
            f"1️⃣ Aşağıdaki kanallara katıl\n"
            f"2️⃣ Botu arkadaşlarınla paylaş\n"
            f"3️⃣ *{REFERRAL_GOAL} referans* kazan → Erişim aç\n"
            f"🏆 İlk *{TOP_N}'e* gir → *Bedava erişim!*",
            reply_markup=markup,
            disable_web_page_preview=True,
            parse_mode="Markdown"
        )

# ====================== SİRALAMA KOMUTU ======================
@bot.message_handler(commands=['siralama'])
def siralama(message):
    bot.send_message(message.from_user.id, format_leaderboard(), parse_mode="Markdown")

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    if message.text and message.text.lower().startswith("start"):
        start(message)

print("✅ YKS Botu çalışıyor... (Liderlik tablosu aktif)")
bot.infinity_polling(timeout=40, long_polling_timeout=40)
