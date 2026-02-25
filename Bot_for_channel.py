import os
import re
import asyncio
from threading import Thread
from flask import Flask
from datetime import datetime
import pytz
from telegram import Update, MessageEntity
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

GG_FILE_ID = "BQACAgUAAxkBAAID7mme066zeoD9zp4WUQ5_OdyY4SrVAAKNHAACIAH5VGPU26rszTehOgQ"

# ===== WEBKEEP ALIVE =====
app_web = Flask(__name__)
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

@app_web.route("/")
def home():
    return "Bot is online!"

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    Thread(target=lambda: app_web.run(host="0.0.0.0", port=port)).start()

# ===== MODERATION HELPERS =====
def msg_is_forwarded(msg) -> bool:
    return bool(
        getattr(msg, "forward_origin", None)
        or getattr(msg, "forward_date", None)
        or getattr(msg, "forward_from", None)
        or getattr(msg, "forward_from_chat", None)
        or getattr(msg, "forward_sender_name", None)
    )

def msg_has_link(msg) -> bool:
    text = (msg.text or msg.caption or "")[:4096]
    t = text.lower()

    # common link patterns
    if re.search(r"(https?://|www\.|t\.me/|telegram\.me/)", t):
        return True

    # plain domains without http(s), ex: google.com
    if re.search(r"\b[a-z0-9-]+\.(com|net|org|io|co|me|gg|app|xyz|site|dev|ph)\b", t):
        return True

    # telegram entities (clickable links)
    entities = (msg.entities or []) + (msg.caption_entities or [])
    for e in entities:
        if e.type in (MessageEntityType.URL, MessageEntityType.TEXT_LINK):
            return True

    return False

async def send_temp_warning(chat, text: str, seconds: int = 5):
    warn = await chat.send_message(text)
    await asyncio.sleep(seconds)
    try:
        await warn.delete()
    except Exception:
        pass


async def moderate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return

    user_id = msg.from_user.id

    # OWNER bypass
    if OWNER_ID and user_id == OWNER_ID:
        return

    # Admin bypass
    member = await context.bot.get_chat_member(msg.chat.id, user_id)
    if member.status in ("administrator", "creator"):
        return

    try:
        if msg_is_forwarded(msg):
            await msg.delete()
            await send_temp_warning(
                msg.chat,
                "⚠️ Forwarded messages are not allowed."
            )
            return

        if msg_has_link(msg):
            await msg.delete()
            await send_temp_warning(
                msg.chat,
                "🚫 Ads / links are not allowed."
            )
            return

    except Exception as e:
        print("moderate error:", e)
        
# ===== START COMMAND =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    full_name = user.full_name.strip() if user and user.full_name else "Player"

    start_message = (
        f"👋 Hi {full_name}! Welcome to Palaro 🎮🔥\n\n"
        "🤖 I'm here to help keep the channel clean and enjoyable.\n\n"
        "⚠️ Channel Rules:\n"
        "• No forwarded messages\n"
        "• No t.me links\n\n"
        "💬 Please stay active and respectful.\n"
        "🛠️ Type /help to see what I can do.\n\n"
        "🔥 Enjoy the game and have fun!"
    )

    await update.message.reply_text(start_message)
    
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.message
    if not msg or not msg.new_chat_members:
        return

    for m in msg.new_chat_members:
        full = (m.full_name or m.first_name or "Player").strip()

        welcome_message = (
            f"👋 Hello {full}, welcome to Palaro! 🎮🔥\n\n"
            "📌 Please check the pinned rules before playing.\n"
            "💬 Stay active and follow announcements for updates.\n\n"
            "👉 If you haven't joined our main channel yet, join here:\n"
            "https://t.me/+wkXVYyqiRYplZjk1"
        )

        await chat.send_message(welcome_message, disable_web_page_preview=True)
# ===== /HELP COMMAND =====
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 <b>KAZEBOT HELP MENU</b>\n\n"

        "👤 <b>MEMBER COMMANDS</b>\n"
        "• /start – Bot information\n"
        "• /help – Show this help menu\n"
        "• /report @username reason – Report a user to admin & owner\n\n"

        "🎮 <b>GAME COMMANDS</b>\n"
        "• Pick numbers: <b>1–6</b>\n"
        "  (Max 3 numbers per player, no duplicate numbers)\n"
        "• /roll – Roll the dice\n"
        "• /reroll – Roll again if no one wins\n\n"

        "🛑 <b>ADMIN COMMANDS</b>\n"
        "• /stoproll – Disable rolling\n"
        "• /runroll – Enable rolling\n"
        "• /cancelroll – Cancel & reset the game\n\n"

        "ℹ️ <b>RULES & NOTES</b>\n"
        "• No picking while a game is pending\n"
        "• The game resets only when there is a winner\n"
        "• Forwarded messages are not allowed\n"
        "• Telegram links are not allowed\n\n"

        "🔥 Please follow the rules and have fun!"
    )

    await update.message.reply_text(help_text, parse_mode="HTML")
    
import re
import random
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import ContextTypes
    
async def report_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not context.args:
        await msg.reply_text(
            "⚠️ Usage:\n/report @username reason\nExample: /report @user spamming links"
        )
        return

    reported_user = context.args[0]
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
    chat = update.effective_chat

    # Get reporter info
    reporter_name = update.effective_user.full_name or update.effective_user.username

    # Confirm to reporter (member)
    await msg.reply_text("✅ Your report has been sent to the admins Owner.")

    # Get admins
    admins = await context.bot.get_chat_administrators(chat.id)

    for admin in admins:
        if admin.user.is_bot:
            continue
        try:
            await context.bot.send_message(
                admin.user.id,
                f"🚨 *Report Notification*\n\n"
                f"👤 Reported user: {reported_user}\n"
                f"📝 Reason: {reason}\n"
                f"🕵️ Reported by: {reporter_name}\n"
                f"📍 Group: {chat.title}",
                parse_mode="Markdown"
            )
        except:
           pass

import random
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ================= CONFIG =================
MAX_PLAYERS = 6
ROLL_WAIT_SECONDS = 0

# ================= GLOBAL GAME STATE =================
picks = {}                  # {user_id: number}
roll_enabled = True
pending_game = False
roll_cooldown_active = False
roll_cooldown_task = None
WINNER_DM = "@KAZEHAYAMODZ"


# ================= HELPER: CHECK ADMIN =================
async def is_admin(update, context):
    member = await context.bot.get_chat_member(
        update.effective_chat.id,
        update.effective_user.id
    )
    return member.status in ["administrator", "creator"]


# ================= AUTO DETECT + PICK =================
import re
from datetime import datetime
import pytz

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global pending_game, roll_cooldown_active

    msg = update.message
    if not msg or not msg.text:
        return

    text = msg.text.strip()
    text_lower = text.lower()
    user = update.effective_user

    # ===== GAMEGUARDIAN AUTO DETECT =====
    # Ise-send ng bot ang APK kapag may nakitang "gameguardian", "game guardian", o "gg"
    if re.search(r"\b(gameguardian|game\sguardian|gg)\b", text_lower):
        try:
            await msg.reply_document(
                document=GG_FILE_ID,
                caption="✅ **Eto na yung game guardian mo supported high Android device**",
                parse_mode="Markdown"
            )
            return # Stop execution para hindi na mag-trigger ang ibang text filters
        except Exception as e:
            print(f"Error sending GG APK: {e}")
            return

    # ===== NAMES / SPECIAL =====
    if re.search(r"\bkaze+\b", text_lower):
        await msg.reply_text(" Pogi si Kaze!")
        return

    if re.search(r"\bkuri\b", text_lower):
        await msg.reply_text(" Pogi")
        return

    if re.search(r"\bphia\b", text_lower):
        await msg.reply_text("🥹 Phia maganda")
        return

    # ===== GREETINGS =====
    if re.search(r"\b(hi|hello|hey|yo|hoy)\b", text_lower):
        await msg.reply_text("👋 Hi! Kumusta ka?")
        return

    # ===== THANK YOU =====
    if re.search(r"\b(thanks|thank you|thx|salamat)\b", text_lower):
        await msg.reply_text("🙏 Walang anuman! 😊")
        return

    # ===== GOOD NIGHT =====
    if re.search(r"\b(good night|gn|gabing gabi)\b", text_lower):
        await msg.reply_text("🌙 Good night too 😴")
        return

    # ===== GOOD MORNING =====
    if re.search(r"\b(good morning|gm|umaga na)\b", text_lower):
        await msg.reply_text("☀️ Good morning too! 😏")
        return

    # ===== WHAT TIME =====
    if re.search(r"\b(anong oras na ba|what time is it|time)\b", text_lower):
        tz = pytz.timezone("Asia/Manila")
        now = datetime.now(tz)
        time_now = now.strftime("%I:%M %p")
        await msg.reply_text(f"⏰ Time check: **{time_now}**", parse_mode="Markdown")
        return

    # ===== BOT INFO =====
    if re.search(r"\b(ano ang pangalan mo|who are you)\b", text_lower):
        await msg.reply_text("🤖 Ako si Rose!")
        return

    # ===== FUN =====
    if re.search(r"\b(gg|good game)\b", text_lower):
        await msg.reply_text("🎮 GG! Nice play!")
        return

    if re.search(r"\bpalaro\b", text_lower):
        await msg.reply_text(" Mga kupal")
        return

    if re.search(r"\bokay+\b", text_lower):
        await msg.reply_text(" Whee di nga🙄!")
        return

    if re.search(r"\bbili+\b", text_lower):
        await msg.reply_text(" bili ka kay 👉 @KAZEHAYAMODZ")
        return

    if re.search(r"\bchecker+\b", text_lower):
        await msg.reply_text(" Bumili ka wag puro hinge🙄")
        return

    if re.search(r"\byow+\b", text_lower):
        await msg.reply_text(" Yow ano topic pwedy makisali?")
        return

    if re.search(r"\bSlyd+\b", text_lower):
        await msg.reply_text(" madamot ako eh🫤")
        return

    if re.search(r"\bsolid+\b", text_lower):
        await msg.reply_text(" Mas solid yan kapag mag avail ka ng lifetime ni kaze")
        return

    # ===== PICK NUMBER (1–6 ONLY) =====
    if text_lower not in ["1", "2", "3", "4", "5", "6"]:
        return

    if pending_game or roll_cooldown_active:
        warn = await msg.reply_text("⏳ Game in progress. Please wait.")
        await asyncio.sleep(3)
        await warn.delete()
        return

    # 🔒 ONE PICK ONLY
    if user_id in picks:
        warn = await msg.reply_text(
            "🚫 You already picked.\nPlease wait for the game to finish."
        )
        await asyncio.sleep(3)
        await warn.delete()
        return

    number = int(text_lower)

    # ❌ DUPLICATE NUMBER
    if number in picks.values():
        warn = await msg.reply_text(
            "❌ That number is already taken.\nChoose another."
        )
        await asyncio.sleep(3)
        await warn.delete()
        return

    # ✅ SUCCESS PICK
    picks[user_id] = number
    confirm = await msg.reply_text(
        f"✅ {user.first_name}, your pick is locked: [{number}] 🔒"
    )
    await asyncio.sleep(3)
    await confirm.delete()
    
# ================= CORE ROLL =================
async def process_roll(update: Update, context: ContextTypes.DEFAULT_TYPE, is_reroll=False):
    global pending_game, picks, WINNER_DM

    dice = random.randint(1, 6)
    winners = []

    for uid, num in picks.items():
        if num == dice:
            member = await context.bot.get_chat_member(
                update.effective_chat.id, uid
            )
            winners.append(member.user.mention_html())

    # ===== IF MAY WINNER =====
    if winners:
        await update.message.reply_html(
            f"🎲 <b>{'Re' if is_reroll else ''}Rolled Number:</b> {dice}\n\n"
            f"🎉 <b>WINNER(S):</b>\n"
            f"{'<br>'.join(winners)}\n\n"
            f"📩 DM {WINNER_DM}"
        )

        picks.clear()
        pending_game = False

    # ===== NO WINNER =====
    else:
        pending_game = True
        await update.message.reply_text(
            f"🎲 Rolled Number: {dice}\n"
            f"🥹 No winners.\n\n"
            f"🔁 Use /reroll"
        )


# ================= /roll =================
async def roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global roll_enabled, roll_cooldown_active, roll_cooldown_task

    if not roll_enabled:
        await update.message.reply_text("⛔ Roll is disabled.")
        return

    if pending_game or roll_cooldown_active:
        await update.message.reply_text("⏳ Please wait.")
        return

    if len(picks) < 2:
        await update.message.reply_text("❌ At least 2 players required.")
        return

    if len(picks) >= MAX_PLAYERS:
        await update.message.reply_text("🔥 Full players! Rolling now...")
        await process_roll(update, context)
        return

    roll_cooldown_active = True
    await update.message.reply_text(
        f"⏳ Please wait {ROLL_WAIT_SECONDS}s.\nWaiting for other players..."
    )

    async def delayed_roll():
        global roll_cooldown_active
        try:
            await asyncio.sleep(ROLL_WAIT_SECONDS)
            if not pending_game and roll_enabled:
                await process_roll(update, context)
        finally:
            roll_cooldown_active = False

    roll_cooldown_task = asyncio.create_task(delayed_roll())


# ================= /reroll =================
async def reroll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not pending_game:
        await update.message.reply_text("❌ No pending game.")
        return
    await process_roll(update, context, is_reroll=True)


# ================= /cancelroll =================
async def cancelroll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global picks, pending_game, roll_cooldown_active, roll_cooldown_task

    if not await is_admin(update, context):
        return

    if roll_cooldown_task:
        roll_cooldown_task.cancel()

    picks.clear()
    pending_game = False
    roll_cooldown_active = False

    await update.message.reply_text(
        "🛑 Game cancelled.\n🔄 Game reset."
    )


# ================= /stoproll =================
async def stoproll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global roll_enabled
    if await is_admin(update, context):
        roll_enabled = False
        await update.message.reply_text("⛔ Roll stopped.")


# ================= /runroll =================
async def runroll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global roll_enabled
    if await is_admin(update, context):
        roll_enabled = True
        await update.message.reply_text("▶️ Roll enabled!")

async def switch_kaze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global WINNER_DM

    # OWNER always allowed
    if OWNER_ID and update.effective_user.id == OWNER_ID:
        WINNER_DM = "@KAZEHAYAMODZ"
        msg = await update.message.reply_text("✅ Switch Successfully")
        await asyncio.sleep(3)
        await msg.delete()
        return

    # Admin only
    if not await is_admin(update, context):
        return

    WINNER_DM = "@KAZEHAYAMODZ"
    msg = await update.message.reply_text("✅ Switch Successfully")
    await asyncio.sleep(3)
    await msg.delete()

async def switch_kuri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global WINNER_DM

    # OWNER always allowed
    if OWNER_ID and update.effective_user.id == OWNER_ID:
        WINNER_DM = "@Kurikongofficial"
        msg = await update.message.reply_text("✅ Switch Successfully")
        await asyncio.sleep(3)
        await msg.delete()
        return

    # Admin only
    if not await is_admin(update, context):
        return

    WINNER_DM = "@Kurikongofficial"
    msg = await update.message.reply_text("✅ Switch Successfully")
    await asyncio.sleep(3)
    await msg.delete()

async def get_file_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.document:
        f_id = update.message.document.file_id
        await update.message.reply_text(f"✅ **FILE ID OBTAINED:**\n\n`{f_id}`", parse_mode="Markdown")
        print(f"File ID: {f_id}") # Lalabas din ito sa console mo
        
# ===== MAIN FUNCTION =====
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_TOKEN env var.")

    app = Application.builder().token(token).build()

    # ===== COMMANDS =====
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("report", report_user))
    # Idagdag ito para gumana yung get_file_id kapag nag-send ka ng APK
    app.add_handler(MessageHandler(filters.Document.ALL, get_file_id))

    # ===== GAME COMMANDS =====
    app.add_handler(CommandHandler("roll", roll))
    app.add_handler(CommandHandler("reroll", reroll))
    app.add_handler(CommandHandler("stoproll", stoproll))
    app.add_handler(CommandHandler("runroll", runroll))
    app.add_handler(CommandHandler("cancelroll", cancelroll))
    app.add_handler(CommandHandler("switchkuri", switch_kuri))
    app.add_handler(CommandHandler("switchkaze", switch_kaze))

    # ===== WELCOME =====
    app.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome)
    )

    # ===== 🚨 MODERATION FIRST =====
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.CAPTION | filters.FORWARDED) & ~filters.COMMAND,
            moderate
        ),
        group=0
    )

    # ===== MAIN TEXT HANDLER =====
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
        group=1
    )

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    keep_alive()
    main()
