##Creating By Pr1me_StRel0k##

import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import aiohttp
import sqlite3
import random
import datetime
import time


GUILD_ID = Your Channel ID
ADMIN_USER_ID = Your Admin User ID

ROLE_UNVERIFIED = ID Unverified Role
ROLE_VERIFIED = ID Verified Role
CHANNEL_WELCOME = ID Welcome Channel
CHANNEL_MOD_LOGS = ID Logs Channel



guard_mode_active = False

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)


conn = sqlite3.connect("defender.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    funpay TEXT,
    roblox TEXT,
    verified INTEGER DEFAULT 0,
    trust_points INTEGER DEFAULT 0,
    swarns INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    moderator_id INTEGER NOT NULL,
    reason_type TEXT NOT NULL,
    issued_at INTEGER NOT NULL,
    expires_at INTEGER
)
""")
conn.commit()


cursor.execute("PRAGMA table_info(users)")
columns = [column[1] for column in cursor.fetchall()]
if 'swarns' not in columns:
    print("Обновление БД: Добавляется колонка 'swarns'...")
    cursor.execute("ALTER TABLE users ADD COLUMN swarns INTEGER DEFAULT 0")
    conn.commit()
    print("Колонка 'swarns' успешно добавлена.")


def save_user(user_id: int, funpay: str = None, roblox: str = None, verified: int = None):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    if funpay is not None: cursor.execute("UPDATE users SET funpay = ? WHERE user_id = ?", (funpay, user_id))
    if roblox is not None: cursor.execute("UPDATE users SET roblox = ? WHERE user_id = ?", (roblox, user_id))
    if verified is not None: cursor.execute("UPDATE users SET verified = ? WHERE user_id = ?", (verified, user_id))
    conn.commit()

def get_user(user_id: int):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

def add_trust(user_id: int, points: int = 1):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    cursor.execute("UPDATE users SET trust_points = trust_points + ? WHERE user_id = ?", (points, user_id))
    conn.commit()

def add_warning(user_id: int, moderator_id: int, reason_type: str, duration_days: int = None):
    issued_at = int(time.time())
    expires_at = issued_at + (duration_days * 86400) if duration_days else None
    cursor.execute("INSERT INTO warnings (user_id, moderator_id, reason_type, issued_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                   (user_id, moderator_id, reason_type, issued_at, expires_at))
    conn.commit()

def get_active_warnings(user_id: int, reason_type: str):
    current_time = int(time.time())
    cursor.execute("SELECT COUNT(*) FROM warnings WHERE user_id = ? AND reason_type = ? AND (expires_at IS NULL OR expires_at > ?)",
                   (user_id, reason_type, current_time))
    return cursor.fetchone()[0]

def add_swarn(user_id: int, amount: int = 1):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    cursor.execute("UPDATE users SET swarns = swarns + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    cursor.execute("SELECT swarns FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()[0]

def remove_warnings(user_id: int, amount: int):
    cursor.execute("SELECT id FROM warnings WHERE user_id = ? ORDER BY issued_at DESC LIMIT ?", (user_id, amount))
    warns_to_delete = cursor.fetchall()
    for warn_id in warns_to_delete:
        cursor.execute("DELETE FROM warnings WHERE id = ?", (warn_id[0],))
    conn.commit()
    return len(warns_to_delete)

def remove_swarns(user_id: int, amount: int):
    cursor.execute("UPDATE users SET swarns = swarns - ? WHERE user_id = ? AND swarns > 0", (amount, user_id))
    conn.commit()


async def log_action(guild: discord.Guild, message: str):
    log_channel = guild.get_channel(CHANNEL_MOD_LOGS)
    if log_channel:
        embed = discord.Embed(description=message, color=discord.Color.orange(), timestamp=datetime.datetime.now())
        await log_channel.send(embed=embed)
    else:
        print(f"Ошибка: не удалось найти канал для логов с ID {CHANNEL_MOD_LOGS}")


@bot.event
async def on_ready():
    print(f"✅ Бот запущен как {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Синхронизировано {len(synced)} слеш-команд")
    except Exception as e:
        print(f"Ошибка синхронизации: {e}")

async def send_menu(user: discord.User):
    if user.id == ADMIN_USER_ID:
        await user.send("🔧 Панель администратора:", view=AdminMenu())
    else:
        await user.send("👋 Привет! Для верификации на сервере нажми кнопку 'Проверка'.", view=UserMenu())

@bot.event
async def on_member_join(member: discord.Member):
    if member.guild.id != GUILD_ID: return

   
    if guard_mode_active:
        account_age = datetime.datetime.now(datetime.timezone.utc) - member.created_at
        if account_age < datetime.timedelta(hours=24):
            await member.kick(reason="Режим защиты: Аккаунт слишком новый.")
            await log_action(member.guild, f"🛡️ **Режим защиты**: Пользователь {member.mention} кикнут (аккаунт создан менее 24 часов назад).")
            return

    unverified_role = member.guild.get_role(ROLE_UNVERIFIED)
    if unverified_role: await member.add_roles(unverified_role)

    welcome_channel = bot.get_channel(CHANNEL_WELCOME)
    if welcome_channel:
        await welcome_channel.send(f"👋 Добро пожаловать, {member.mention}! Я отправил тебе в личные сообщения инструкции для верификации.")

    await send_menu(member)


@bot.tree.command(name="pban", description="Банит пользователя навсегда")
@app_commands.checks.has_permissions(ban_members=True)
async def pban(interaction: discord.Interaction, user: discord.Member, reason: str = "Пермабан от бота"):
    await interaction.guild.ban(user, reason=reason)
    await interaction.response.send_message(f"Пользователь {user.mention} забанен навсегда ✅", ephemeral=True)
    await log_action(interaction.guild, f"🚫 **Перманентный бан**: {interaction.user.mention} забанил {user.mention}. Причина: {reason}")

@bot.tree.command(name="ban", description="Банит пользователя на время")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, user: discord.Member, time: int, reason: str = "Временный бан от бота"):
    await interaction.guild.ban(user, reason=reason)
    await interaction.response.send_message(f"Пользователь {user.mention} забанен на {time} сек. ✅", ephemeral=True)
    await log_action(interaction.guild, f"🔨 **Временный бан**: {interaction.user.mention} забанил {user.mention} на `{time}` секунд. Причина: {reason}")
    await asyncio.sleep(time)
    await interaction.guild.unban(user)
    await log_action(interaction.guild, f"✅ **Авто-разбан**: {user.mention} был автоматически разбанен.")

@bot.tree.command(name="kick", description="Кикает пользователя")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str = "Кикнут ботом"):
    await user.kick(reason=reason)
    await interaction.response.send_message(f"{user.mention} был кикнут ✅", ephemeral=True)
    await log_action(interaction.guild, f"👢 **Кик**: {interaction.user.mention} кикнул {user.mention}. Причина: {reason}")

@bot.tree.command(name="mute", description="Мутит пользователя на время")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, user: discord.Member, time: int, reason: str = "Мут от бота"):
    await user.timeout(datetime.timedelta(seconds=time), reason=reason)
    await interaction.response.send_message(f"{user.mention} замьючен на {time} сек. ✅", ephemeral=True)
    await log_action(interaction.guild, f"🔇 **Мут**: {interaction.user.mention} замьютил {user.mention} на `{time}` секунд. Причина: {reason}")

@bot.tree.command(name="freeze", description="Фризит сервер")
@app_commands.checks.has_permissions(administrator=True)
async def freeze(interaction: discord.Interaction, time: int):
    role = discord.utils.get(interaction.guild.roles, name="Замороженные")
    if not role:
        role = await interaction.guild.create_role(name="Замороженные")
        for channel in interaction.guild.channels:
            await channel.set_permissions(role, send_messages=False)
    for member in interaction.guild.members:
        if not member.bot: await member.add_roles(role)
    await interaction.response.send_message(f"Все игроки заморожены на {time} сек. ❄️", ephemeral=True)
    await log_action(interaction.guild, f"❄️ **Фриз**: {interaction.user.mention} заморозил сервер на `{time}` секунд.")
    await asyncio.sleep(time)
    for member in interaction.guild.members:
        if role in member.roles: await member.remove_roles(role)
    await log_action(interaction.guild, f"✅ **Авто-разморозка**: Сервер разморожен.")


@bot.tree.command(name="warn", description="Выдать предупреждение пользователю")
@app_commands.checks.has_permissions(moderate_members=True)
@app_commands.choices(reason_type=[
    app_commands.Choice(name="Mute", value="mute"),
    app_commands.Choice(name="Kick", value="kick"),
    app_commands.Choice(name="Ban", value="ban"),
    app_commands.Choice(name="Swarn", value="swarn"),
])
async def warn(interaction: discord.Interaction, user: discord.Member, reason_type: app_commands.Choice[str], time: int, reason: str):
    duration_days = time
    add_warning(user.id, interaction.user.id, reason_type.value, duration_days)
    
    await log_action(interaction.guild, f"⚠️ **Предупреждение**: {interaction.user.mention} выдал предупреждение {user.mention} (тип: `{reason_type.name}`) на `{duration_days}` дней. Причина: {reason}")
    await interaction.response.send_message(f"Предупреждение типа `{reason_type.name}` выдано {user.mention} на {duration_days} дней.", ephemeral=True)

    
    active_warns = get_active_warnings(user.id, reason_type.value)
    if active_warns >= 3:
        
        cursor.execute("DELETE FROM warnings WHERE user_id = ? AND reason_type = ?", (user.id, reason_type.value))
        conn.commit()
        
        if reason_type.value == "mute":
            await user.timeout(datetime.timedelta(hours=1), reason="Авто-мут за 3 предупреждения")
            await log_action(interaction.guild, f"🔇 **Авто-мут**: {user.mention} получил мут на 1 час за 3 предупреждения типа `Mute`.")
        elif reason_type.value == "kick":
            await user.kick(reason="Авто-кик за 3 предупреждения")
            await log_action(interaction.guild, f"👢 **Авто-кик**: {user.mention} был кикнут за 3 предупреждения типа `Kick`.")
        elif reason_type.value == "ban":
            await interaction.guild.ban(user, reason="Авто-бан за 3 предупреждения", delete_message_days=0)
            await log_action(interaction.guild, f"🔨 **Авто-бан**: {user.mention} забанен на 2 дня за 3 предупреждения типа `Ban`.")
            await asyncio.sleep(172800) # 2 дня
            await interaction.guild.unban(user)
            await log_action(interaction.guild, f"✅ **Авто-разбан**: {user.mention} был автоматически разбанен.")
        elif reason_type.value == "swarn":
            new_swarn_count = add_swarn(user.id, 1)
            await log_action(interaction.guild, f"‼️ **Выдан Super Warn**: {user.mention} получил 1 `SWarn` (всего: {new_swarn_count}) за 3 предупреждения типа `Swarn`.")
            if new_swarn_count >= 2:
                await interaction.guild.ban(user, reason="Авто-пермабан за 2 Super Warns")
                await log_action(interaction.guild, f"🚫 **Авто-пермабан**: {user.mention} получил перманентный бан за 2 `SWarn`.")

@bot.tree.command(name="swarn", description="Выдать Super Warn пользователю")
@app_commands.checks.has_permissions(administrator=True)
async def swarn(interaction: discord.Interaction, user: discord.Member):
    new_swarn_count = add_swarn(user.id, 1)
    await log_action(interaction.guild, f"‼️ **Выдан Super Warn**: {interaction.user.mention} выдал `SWarn` пользователю {user.mention} (всего: {new_swarn_count}).")
    await interaction.response.send_message(f"Super Warn выдан {user.mention}. Теперь у него {new_swarn_count} SWarn(s).", ephemeral=True)
    if new_swarn_count >= 2:
        await interaction.guild.ban(user, reason="Пермабан за 2 Super Warns")
        await log_action(interaction.guild, f"🚫 **Авто-пермабан**: {user.mention} получил перманентный бан за 2 `SWarn`.")

@bot.tree.command(name="dwarn", description="Снять обычные предупреждения")
@app_commands.checks.has_permissions(administrator=True)
async def dwarn(interaction: discord.Interaction, user: discord.Member, amount: int):
    removed_count = remove_warnings(user.id, amount)
    await interaction.response.send_message(f"Снято {removed_count} предупреждений с {user.mention}.", ephemeral=True)
    await log_action(interaction.guild, f"✅ **Снятие варнов**: {interaction.user.mention} снял `{removed_count}` варнов с {user.mention}.")

@bot.tree.command(name="dswarn", description="Снять Super Warns")
@app_commands.checks.has_permissions(administrator=True)
async def dswarn(interaction: discord.Interaction, user: discord.Member, amount: int):
    remove_swarns(user.id, amount)
    await interaction.response.send_message(f"Снято {amount} SWarn(s) с {user.mention}.", ephemeral=True)
    await log_action(interaction.guild, f"✅ **Снятие SWarn**: {interaction.user.mention} снял `{amount}` SWarn(s) с {user.mention}.")


@bot.tree.command(name="guard", description="Включить/выключить режим защиты от рейдов")
@app_commands.checks.has_permissions(administrator=True)
async def guard(interaction: discord.Interaction):
    global guard_mode_active
    guard_mode_active = not guard_mode_active
    status = "ВКЛЮЧЕН" if guard_mode_active else "ВЫКЛЮЧЕН"
    color = discord.Color.green() if guard_mode_active else discord.Color.red()
    
    embed = discord.Embed(title="🛡️ Режим защиты", description=f"Статус: **{status}**", color=color)
    if guard_mode_active:
        embed.add_field(name="Активные меры:", value="- Кик аккаунтов, созданных менее 24 часов назад.\n- Усиленный контроль спама (3 сообщения за 5 сек).", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
    await log_action(interaction.guild, f"🛡️ **Режим защиты {status}** модератором {interaction.user.mention}.")


class AdminMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Ban", style=discord.ButtonStyle.danger, custom_id="admin_ban"))
        self.add_item(discord.ui.Button(label="Stats", style=discord.ButtonStyle.primary, custom_id="admin_stats"))
        self.add_item(discord.ui.Button(label="Info", style=discord.ButtonStyle.secondary, custom_id="admin_info"))

class UserMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Проверка", style=discord.ButtonStyle.success, custom_id="user_check"))
        self.add_item(discord.ui.Button(label="Данные", style=discord.ButtonStyle.primary, custom_id="user_data"))

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.data or "custom_id" not in interaction.data: return
    cid = interaction.data["custom_id"]
    guild = bot.get_guild(GUILD_ID)
    if not guild and cid in ["admin_ban", "admin_stats", "admin_info", "unban_"]:
        await interaction.response.send_message("❌ Ошибка: не удалось подключиться к серверу. Проверь GUILD_ID.", ephemeral=True)
        return
    if cid == "admin_ban":
        bans = [entry async for entry in guild.bans()]
        view = discord.ui.View()
        if not bans:
            await interaction.response.send_message("Забаненных пользователей нет.", ephemeral=True)
            return
        for entry in bans:
            view.add_item(discord.ui.Button(label=f"Разбанить {entry.user}", style=discord.ButtonStyle.green, custom_id=f"unban_{entry.user.id}"))
        await interaction.response.send_message("Список забаненных:", view=view, ephemeral=True)
    elif cid.startswith("unban_"):
        user_id = int(cid.split("_")[1])
        user = await bot.fetch_user(user_id)
        await guild.unban(user)
        await interaction.response.send_message(f"{user} разбанен ✅", ephemeral=True)
        await log_action(guild, f"✅ **Разбан (кнопка)**: {interaction.user.mention} разбанил {user}.")
    elif cid == "admin_stats":
        online = sum(1 for m in guild.members if m.status != discord.Status.offline)
        bots = sum(1 for m in guild.members if m.bot)
        await interaction.response.send_message(f"👥 Всего пользователей: {guild.member_count}\n🟢 Онлайн: {online}\n🤖 Ботов: {bots}", ephemeral=True)
    elif cid == "admin_info":
        members = "\n".join([m.name for m in guild.members if not m.bot][:20])
        await interaction.response.send_message(f"Участники:\n{members}\n(ограничено 20)", ephemeral=True)
    elif cid == "user_check":
        code = str(random.randint(1000, 9999))
        captcha_codes[interaction.user.id] = code
        await interaction.response.send_message(f"Привет! Давай начнём проверку.\nВведи код: `{code}`", ephemeral=True)
    elif cid == "user_data":
        data = get_user(interaction.user.id)
        if data:
            funpay, roblox, trust = (data[1] or "Не привязан"), (data[2] or "Не привязан"), data[4]
            await interaction.response.send_message(f"📊 Данные:\nFunPay: {funpay}\nRoblox: {roblox}\nОчки доверия: {trust}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Данных не найдено.", ephemeral=True)


async def check_funpay(username: str):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
    url = f"https://funpay.com/users/{username}/"
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as resp:
            return resp.status == 200

async def check_roblox(user_id: int):
    url = f"https://users.roblox.com/v1/users/{user_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("name")
    return None

captcha_codes = {}
bad_words = ["плохое", "ругательство", "http://", "discord.gg/"]
spam_tracker = {}

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot: return

    
    if message.guild is None:
        author_id = message.author.id
        content_lower = message.content.lower()
        if author_id in captcha_codes:
            if message.content.strip() == captcha_codes[author_id]:
                del captcha_codes[author_id]
                await message.channel.send("✅ Капча пройдена! Теперь привяжи FunPay.\nНапиши: `funpay НИК`")
            else:
                await message.channel.send("❌ Неверный код. Попробуй нажать кнопку 'Проверка' ещё раз.")
        elif content_lower.startswith("funpay "):
            username = message.content.split(" ", 1)[1]
            if await check_funpay(username):
                save_user(author_id, funpay=username)
                await message.channel.send(f"✅ Аккаунт FunPay `{username}` подтверждён! Теперь привяжи Roblox.\nНапиши: `roblox ID`")
            else:
                await message.channel.send("❌ Не удалось найти такой аккаунт FunPay.")
        elif content_lower.startswith("roblox "):
            try:
                roblox_id = int(message.content.split(" ", 1)[1])
                name = await check_roblox(roblox_id)
                if name:
                    save_user(author_id, roblox=name, verified=1)
                    guild = bot.get_guild(GUILD_ID)
                    if guild:
                        member = guild.get_member(author_id)
                        if member:
                            role_verified = guild.get_role(ROLE_VERIFIED)
                            role_unverified = guild.get_role(ROLE_UNVERIFIED)
                            if role_unverified: await member.remove_roles(role_unverified)
                            if role_verified: await member.add_roles(role_verified)
                    await message.channel.send(f"✅ Roblox аккаунт найден: {name}\nТы прошёл проверку!")
                else:
                    await message.channel.send("❌ Roblox аккаунт не найден.")
            except (IndexError, ValueError):
                await message.channel.send("❌ Неверный формат. Напиши `roblox ID`, где ID - это число.")
        else:
            await send_menu(message.author)
        return

   
    if message.guild and message.guild.id == GUILD_ID:
        
        for word in bad_words:
            if word in message.content.lower():
                await message.delete()
                await message.channel.send(f"{message.author.mention}, использование запрещённых слов недопустимо!", delete_after=10)
                await log_action(message.guild, f"💬 **Фильтр слов**: {message.author.mention} использовал запрещенное слово. Сообщение удалено.")
                return

       
        user_id = message.author.id
        now = asyncio.get_event_loop().time()
        if user_id not in spam_tracker: spam_tracker[user_id] = []
        spam_tracker[user_id].append(now)
        spam_tracker[user_id] = [t for t in spam_tracker[user_id] if now - t < 5]

        
        spam_limit = 3 if guard_mode_active else 5
        
        if len(spam_tracker[user_id]) > spam_limit:
            await message.author.timeout(datetime.timedelta(minutes=5), reason="Спам")
            await message.channel.send(f"{message.author.mention} замьючен на 5 минут за спам!")
            await log_action(message.guild, f"💨 **Анти-спам**: {message.author.mention} получил мут на 5 минут за спам.")
            spam_tracker[user_id] = []
            return

        add_trust(user_id, 1)
    await bot.process_commands(message)


@bot.tree.command(name="userdata", description="Посмотреть данные пользователя")
@app_commands.checks.has_permissions(administrator=True)
async def userdata(interaction: discord.Interaction, member: discord.Member):
    data = get_user(member.id)
    if data:
        funpay, roblox, verified, trust, swarns = data[1] or "Не привязан", data[2] or "Не привязан", "Да ✅" if data[3] else "Нет ❌", data[4], data[5]
        active_mute_warns = get_active_warnings(member.id, 'mute')
        active_kick_warns = get_active_warnings(member.id, 'kick')
        active_ban_warns = get_active_warnings(member.id, 'ban')
        
        embed = discord.Embed(title=f"📊 Данные пользователя {member.display_name}", color=member.color, timestamp=datetime.datetime.now())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Верификация", value=f"FunPay: {funpay}\nRoblox: {roblox}\nПроверен: {verified}", inline=False)
        embed.add_field(name="Репутация", value=f"Очки доверия: {trust}\nSuper Warns (SWarn): **{swarns}**", inline=False)
        embed.add_field(name="Активные предупреждения", value=f"Mute: {active_mute_warns}/3\nKick: {active_kick_warns}/3\nBan: {active_ban_warns}/3", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message("❌ Данных на этого пользователя не найдено.", ephemeral=True)

bot.run('your bot token here')

