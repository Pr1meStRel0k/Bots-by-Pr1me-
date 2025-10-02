##Creating By Pr1me_StRel0k##

import json
import asyncio
import random
import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

TELEGRAM_BOT_TOKEN = "Your Token Here"
ADMIN_CHAT_ID = ID Admin Chat
ADMIN_USER_ID = ID Admin User
USER_DATA_FILE = "tg_bot_users.json"

ABOUT_US_TEXT = """Your Text Here"""

GUARANTEES_TEXT = """Your Text Here"""

FAQ_TEXT = """Your Text Here"""

APP_TEXT =  """Your Text Here"""

prize_list = [
    "Your Text Here",
    "Your Text Here",
    "Your Text Here",
    "Your Text Here",
]


data_path = Path(USER_DATA_FILE)
state = {
    "tracked_users": set(),
    "music_history": {},
    "click_counts": {},
    "user_prizes": {},
    "user_support_messages": {},
    "user_support_count": {},
    "user_giveaway_count": {},
    "quick_giveaway_participants": set(),
    "user_daily_participation": set(),
}

def load_state():
    if data_path.exists():
        try:
            j = json.loads(data_path.read_text(encoding="utf-8"))
            state["tracked_users"] = set(j.get("tracked_users", []))
            state["music_history"] = j.get("music_history", {})
            state["click_counts"] = j.get("click_counts", {})
            state["user_prizes"] = j.get("user_prizes", {})
            state["user_support_messages"] = j.get("user_support_messages", {})
            state["user_support_count"] = j.get("user_support_count", {})
            state["user_giveaway_count"] = j.get("user_giveaway_count", {})
            state["quick_giveaway_participants"] = set(j.get("quick_giveaway_participants", []))
            state["user_daily_participation"] = set(j.get("user_daily_participation", []))
            print("State loaded.")
        except Exception as e:
            print(f"Failed to load state: {e}")

def save_state():
    try:
        j = {
            "tracked_users": list(state["tracked_users"]),
            "music_history": state["music_history"],
            "click_counts": state["click_counts"],
            "user_prizes": state["user_prizes"],
            "user_support_messages": state["user_support_messages"],
            "user_support_count": state["user_support_count"],
            "user_giveaway_count": state["user_giveaway_count"],
            "quick_giveaway_participants": list(state["quick_giveaway_participants"]),
            "user_daily_participation": list(state["user_daily_participation"]),
        }
        data_path.write_text(json.dumps(j, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Failed to save state: {e}")

def record_user(user_id: int):
    if user_id not in state["tracked_users"]:
        state["tracked_users"].add(user_id)
        save_state()


def main_menu_keyboard():
    kb = [
        [InlineKeyboardButton("🎵 Музыка", callback_data="music"), InlineKeyboardButton("🎮 Игра", callback_data="game")],
        [InlineKeyboardButton("🎉 Розыгрыш", callback_data="giveaway"), InlineKeyboardButton("⚡ Быстрый розыгрыш", callback_data="quick_giveaway")],
        [InlineKeyboardButton("🛒 Товар", url="your url here"), InlineKeyboardButton("🛠️ Поддержка", callback_data="support")],
        [InlineKeyboardButton("ℹ️ О нас", callback_data="about"), InlineKeyboardButton("🛡️ Гарантии", callback_data="guarantees")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile"), InlineKeyboardButton("❓ FAQ", callback_data="faq")],
        [InlineKeyboardButton("📱 Приложение", callback_data="app")],
    ]
    return InlineKeyboardMarkup(kb)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    record_user(user.id)
    await update.message.reply_text("Добро пожаловать! Выберите пункт меню:", reply_markup=main_menu_keyboard())

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню:", reply_markup=main_menu_keyboard())
    

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data not in ["game_click", "quick_giveaway"]:
        await query.answer()
        
    user_id = query.from_user.id
    record_user(user_id)

    if query.data == "music":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Поиск", callback_data="music_search")],
            [InlineKeyboardButton("📜 История", callback_data="music_history")],
            [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")],
        ])
        await query.edit_message_text("🎵 Меню музыки:", reply_markup=kb)

    elif query.data == "music_search":
        context.user_data["awaiting_music_search"] = True
        await query.message.reply_text("Введите название песни или исполнителя (отправьте сообщение в этот чат).")

    elif query.data == "music_history":
        hist = state["music_history"].get(str(user_id), [])
        if not hist:
            await query.message.reply_text("❌ История пуста.")
        else:
            await query.message.reply_text("📜 Ваша история:\n" + "\n".join(hist[-10:]))

    elif query.data == "game":
        click_count = state["click_counts"].get(str(user_id), 0)
        game_text = (
            f"🎮 **Добро пожаловать в мини-игру!**\n\n"
            f"Вы кликнули: **{click_count}** раз(а).\n\n"
            "Продолжайте кликать, чтобы получить шанс выиграть случайный приз!"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👆 Кликни меня!", callback_data="game_click")],
            [InlineKeyboardButton("🏆 Мои выигрыши", callback_data="game_prizes")],
            [InlineKeyboardButton("◀️ Назад в главное меню", callback_data="main_menu")],
        ])
        await query.edit_message_text(game_text, reply_markup=kb, parse_mode="Markdown")

    elif query.data == "game_click":
        uid = str(user_id)
        cnt = state["click_counts"].get(uid, 0) + 1
        state["click_counts"][uid] = cnt
        
        click_msg = f"Вы кликнули {cnt} раз(а)!"

        
        if random.randint(1, 100) == 50:
            prize = random.choice(prize_list)
            state["user_prizes"].setdefault(uid, []).append(prize)
            save_state() 
            
            prize_msg = f"🎉 Поздравляем! Вы выиграли: {prize}"
            
            await context.bot.send_message(chat_id=user_id, text=prize_msg)
            
            
            await query.answer(text="🎉 ВЫ ВЫИГРАЛИ! 🎉\nПриз отправлен вам в личные сообщения.", show_alert=True)
        else:
            
            await query.answer(text=click_msg)
        
        save_state()


    elif query.data == "game_prizes":
        prizes = state["user_prizes"].get(str(user_id), [])
        back_button = InlineKeyboardButton("◀️ Назад в игру", callback_data="game")
        
        if not prizes:
            text = "❌ У вас пока нет выигрышей. Продолжайте кликать!"
        else:
            prize_list_text = "\n".join([f"• {p}" for p in prizes])
            text = f"🏆 Ваши выигрыши:\n\n{prize_list_text}"
            
        kb = InlineKeyboardMarkup([[back_button]])
        await query.edit_message_text(text=text, reply_markup=kb)


    elif query.data == "app":
        await query.edit_message_text(APP_TEXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]))

    elif query.data == "giveaway":
        await query.message.reply_text("Участие в розыгрыше.\nНапишите ваш Discord (пример: username#1234):")
        context.user_data["giveaway_step"] = "ask_discord"

    elif query.data == "support":
        await query.message.reply_text("Опишите вашу проблему или вопрос (отправьте сообщение):")
        context.user_data["support_step"] = "ask_support"

    elif query.data == "about":
        await query.edit_message_text(ABOUT_US_TEXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]))

    elif query.data == "guarantees":
        await query.edit_message_text(GUARANTEES_TEXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]))

    elif query.data == "profile":
        uid = str(user_id)
        support_count = state["user_support_count"].get(uid, 0)
        giveaway_count = state["user_giveaway_count"].get(uid, 0)
        msgs = state["user_support_messages"].get(uid, [])
        text = f"👤 Профиль {query.from_user.full_name}\n\nОбращений в поддержку: {support_count}\nУчастий в розыгрышах: {giveaway_count}"
        if msgs:
            text += "\n\nПоследние обращения:\n" + "\n".join(msgs[-3:])
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]])
        await query.edit_message_text(text, reply_markup=kb)

    elif query.data == "quick_giveaway":
        if user_id in state["user_daily_participation"]:
            await query.answer(
                "Вы уже приняли участие в сегодняшнем розыгрыше.\n"
                "Победители будут объявлены в 20:00 по времени EEST (Бухарест). Удачи! 🍀", 
                show_alert=True
            )
        else:
            state["quick_giveaway_participants"].add(user_id)
            state["user_daily_participation"].add(user_id)
            save_state()
            await query.answer("✅ Вы успешно зарегистрированы в розыгрыше! Результаты сегодня в 20:00.", show_alert=True)

    elif query.data == "faq":
        await query.edit_message_text(FAQ_TEXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]))

    elif query.data == "main_menu":
        await query.edit_message_text("Меню:", reply_markup=main_menu_keyboard())



async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)
    text = (update.message.text or "").strip()

    
    if context.user_data.get("awaiting_music_search"):
        query = text
        url = f"https://hitmo.org/search?q={query.replace(' ', '+')}"
        hist = state["music_history"].setdefault(uid, [])
        hist.append(query)
        state["music_history"][uid] = hist[-10:]
        save_state()
        await update.message.reply_text(f"🔎 Вот что я нашёл по запросу *{query}*:\n{url}", parse_mode="Markdown")
        context.user_data.pop("awaiting_music_search", None)
        return

   
    if context.user_data.get("giveaway_step") == "ask_discord":
        context.user_data["giveaway_discord"] = text
        context.user_data["giveaway_step"] = "ask_screenshot"
        await update.message.reply_text("Пришлите ссылку на скриншот покупки (например: imgur.com/...).")
        return

    if context.user_data.get("giveaway_step") == "ask_screenshot":
        screenshot = text
        discord_contact = context.user_data.get("giveaway_discord", "Не указан")
        embed_text = (
            f"📥 Новая заявка на розыгрыш!\n\n"
            f"Отправитель: {user.mention_html()}\n"
            f"Контакт Discord: {discord_contact}\n"
            f"Скрин: {screenshot}\n"
            f"ID пользователя: {user.id}"
        )
        try:
            await context.application.bot.send_message(ADMIN_CHAT_ID, embed_text, parse_mode="HTML")
        except Exception as e:
            print(f"Failed to send giveaway to admin: {e}")
        state["user_giveaway_count"][uid] = state["user_giveaway_count"].get(uid, 0) + 1
        record_user(user.id)
        save_state()
        await update.message.reply_text("✅ Ваша заявка успешно отправлена! Спасибо.")
        context.user_data.clear()
        return

    
    if context.user_data.get("support_step") == "ask_support":
        msg = text
        embed_text = (
            f"🛠️ Новое обращение в поддержку!\n\n"
            f"Отправитель: {user.mention_html()} ({user.id})\n"
            f"Текст обращения: {msg}"
        )
        try:
            await context.application.bot.send_message(ADMIN_CHAT_ID, embed_text, parse_mode="HTML")
        except Exception as e:
            print(f"Failed to forward support: {e}")
        state["user_support_messages"].setdefault(uid, []).append(msg)
        state["user_support_count"][uid] = state["user_support_count"].get(uid, 0) + 1
        record_user(user.id)
        save_state()
        await update.message.reply_text("✅ Ваше обращение отправлено! Мы свяжемся с вами.")
        context.user_data.pop("support_step", None)
        return

    await update.message.reply_text("Не понял. Воспользуйтесь /menu или нажмите кнопку в меню.", reply_markup=main_menu_keyboard())



async def daily_tasks_loop(app):
    tz = ZoneInfo("Europe/Bucharest")
    while True:
        now = datetime.datetime.now(tz)

       
        if now.hour == 0 and now.minute == 0 and now.second < 30:
            print("Running daily reset for quick giveaway.")
            state["quick_giveaway_participants"].clear()
            state["user_daily_participation"].clear()
            save_state()
            try:
                await app.bot.send_message(ADMIN_CHAT_ID, "🔄 Новый день! Участники быстрого розыгрыша сброшены.")
            except Exception as e:
                print(f"ERROR: Could not send daily reset message to admin chat: {e}")

        
        if now.hour == 20 and now.minute == 0 and now.second < 30:
            print("Running daily draw for quick giveaway.")
            participants = list(state["quick_giveaway_participants"])
            if participants:
                winners = random.sample(participants, min(10, len(participants)))
                winner_mentions = ", ".join([f"[{w}](tg://user?id={w})" for w in winners])
                text = f"🏆 Победители быстрого розыгрыша:\n{winner_mentions}"
                try:
                    await app.bot.send_message(ADMIN_CHAT_ID, text, parse_mode="Markdown")
                except Exception as e:
                    print(f"ERROR: Could not send winners list to admin chat: {e}")
                
                for w in winners:
                    try:
                        await app.bot.send_message(w, "🎉 Поздравляем! Вы стали победителем быстрого розыгрыша!")
                    except Exception as e:
                        print(f"ERROR: Could not send prize message to winner {w}: {e}")
            else:
                try:
                    await app.bot.send_message(ADMIN_CHAT_ID, "📢 Сегодня участников быстрого розыгрыша не было.")
                except Exception as e:
                    print(f"ERROR: Could not send 'no participants' message to admin chat: {e}")

        await asyncio.sleep(25)



async def on_startup(app):
    load_state()
    app.create_task(daily_tasks_loop(app))
    print("Bot started, background tasks running.")

async def on_shutdown(app):
    save_state()
    print("Shutting down, state saved.")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ У вас нет прав для использования этой команды.")
        return
    
    if ADMIN_USER_ID == 0:
        await update.message.reply_text("⚠️ Внимание: ADMIN_USER_ID не настроен в коде. Команда доступна всем.")

    user_count = len(state['tracked_users'])
    await update.message.reply_text(f"📈 Всего ботом воспользовалось: {user_count} уникальных пользователей.")


def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

   
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("stats", stats_command))

    
    app.add_handler(CallbackQueryHandler(callback_router))

    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))

   
    app.post_init = on_startup
    app.post_shutdown = on_shutdown

    print("Starting polling...")
    app.run_polling()

if __name__ == "__main__":

    main()
