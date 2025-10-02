##Creating By Pr1me_StRel0k##

import discord
from discord.ext import commands
from discord.ui import Button, View
from discord import app_commands
import json
import asyncio
import datetime

BOT_TOKEN = "Your Bot Token"
GUILD_ID = ID your server
TARGET_CHANNEL_ID = ID your channel

ABOUT_US_TEXT = """Your Text"""

FAQ_TEXT = """Your Text"""

USER_DATA_FILE = "bot_users.json"


music_history = {}
click_counts = {}
user_prizes = {}
prize_list = [
    "Your Text",
    "Your Text",
    "Your Text",
    "Your Text"
              ]

APP_TEXT = """Your Text"""

class MusicView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="🔍 Поиск", style=discord.ButtonStyle.primary)
    async def search(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Введите название песни или исполнителя:", ephemeral=True)

        def check(m):
            return m.author.id == interaction.user.id and isinstance(m.channel, discord.DMChannel)

        try:
            msg = await bot.wait_for("message", check=check, timeout=30)
            query = msg.content
            url = f"https://hitmo.org/search?q={query.replace(' ', '+')}"
            history = music_history.get(interaction.user.id, [])
            history.append(query)
            music_history[interaction.user.id] = history[-10:]
            await interaction.followup.send(f"🔎 Вот что я нашёл по запросу **{query}**:\n{url}", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ Время ожидания истекло.", ephemeral=True)

    @discord.ui.button(label="📜 История", style=discord.ButtonStyle.secondary)
    async def history(self, interaction: discord.Interaction, button: Button):
        history = music_history.get(interaction.user.id, [])
        if not history:
            await interaction.response.send_message("❌ История пуста.", ephemeral=True)
        else:
            await interaction.response.send_message("📜 Ваша история:\n" + "\n".join(history), ephemeral=True)

class GameView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="👆 Кликни меня!", style=discord.ButtonStyle.success)
    async def click(self, interaction: discord.Interaction, button: Button):
        uid = interaction.user.id
        count = click_counts.get(uid, 0) + 1
        click_counts[uid] = count

        import random
        msg = f"Вы кликнули {count} раз(а)!"
        if random.randint(1, 100) == 50:
            prize = random.choice(prize_list)
            user_prizes.setdefault(uid, []).append(prize)
            msg += f"\n🎉 Поздравляем! Вы выиграли: **{prize}**"
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="🏆 Мои выигрыши", style=discord.ButtonStyle.secondary)
    async def my_prizes(self, interaction: discord.Interaction, button: Button):
        prizes = user_prizes.get(interaction.user.id, [])
        if not prizes:
            await interaction.response.send_message("❌ У вас пока нет выигрышей.", ephemeral=True)
        else:
            await interaction.response.send_message("🏆 Ваши выигрыши:\n" + "\n".join(prizes), ephemeral=True)

def load_tracked_users():
    try:
        with open(USER_DATA_FILE, 'r') as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_tracked_users(users_set):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(list(users_set), f)

tracked_users = load_tracked_users()

def record_user(user_id):
    if user_id not in tracked_users:
        tracked_users.add(user_id)
        save_tracked_users(tracked_users)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)


user_support_count = {}
user_giveaway_count = {}
user_support_messages = {}
quick_giveaway_participants = set()
user_daily_participation = set()

class GiveawayModal(discord.ui.Modal, title="Участие в розыгрыше"):
    discord_contact = discord.ui.TextInput(label="Ваш Discord (например, username#1234)")
    screenshot_link = discord.ui.TextInput(label="Ссылка на скриншот покупки (imgur.com)")

    async def on_submit(self, interaction: discord.Interaction):
        record_user(interaction.user.id)
        target_channel = bot.get_channel(TARGET_CHANNEL_ID)
        if target_channel:
            embed = discord.Embed(title="Новая заявка на розыгрыш!", color=discord.Color.green())
            embed.add_field(name="Отправитель:", value=interaction.user.mention, inline=False)
            embed.add_field(name="Контакт Discord:", value=self.discord_contact.value, inline=False)
            embed.set_image(url=self.screenshot_link.value)
            embed.set_footer(text=f"ID пользователя: {interaction.user.id}")
            await target_channel.send(embed=embed)
            await interaction.response.send_message("✅ Ваша заявка успешно отправлена!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Ошибка: канал для заявок не найден.", ephemeral=True)

class SupportModal(discord.ui.Modal, title="Обращение в поддержку"):
    support_message = discord.ui.TextInput(label="Опишите вашу проблему или вопрос", style=discord.TextStyle.long)

    async def on_submit(self, interaction: discord.Interaction):
        record_user(interaction.user.id)
        target_channel = bot.get_channel(TARGET_CHANNEL_ID)
        if target_channel:
            embed = discord.Embed(title="Новое обращение в поддержку!", color=discord.Color.orange())
            embed.add_field(name="Отправитель:", value=f"{interaction.user.mention} ({interaction.user})", inline=False)
            embed.add_field(name="Текст обращения:", value=self.support_message.value, inline=False)
            embed.set_footer(text=f"ID пользователя: {interaction.user.id}")
            await target_channel.send(embed=embed)
            await interaction.response.send_message("✅ Ваше обращение отправлено!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Ошибка: канал для заявок не найден.", ephemeral=True)


class ProfileView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="Закрыть", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await interaction.delete_original_response()

async def send_profile(interaction: discord.Interaction):
    uid = interaction.user.id
    support_count = user_support_count.get(uid, 0)
    giveaway_count = user_giveaway_count.get(uid, 0)
    messages = user_support_messages.get(uid, [])

    embed = discord.Embed(title=f"👤 Профиль {interaction.user}", color=discord.Color.blue())
    embed.add_field(name="Обращений в поддержку", value=str(support_count), inline=True)
    embed.add_field(name="Участий в розыгрышах", value=str(giveaway_count), inline=True)

    if messages:
        embed.add_field(name="Последние обращения:", value="\n".join([f"- {m}" for m in messages[-3:]]), inline=False)

    await interaction.response.send_message(embed=embed, view=ProfileView(uid), ephemeral=True)


class QuickGiveawayView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎲 Испытать удачу", style=discord.ButtonStyle.success, custom_id="try_luck")
    async def try_luck(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id in user_daily_participation:
            await interaction.response.send_message("❌ Вы уже участвовали сегодня!", ephemeral=True)
        else:
            quick_giveaway_participants.add(interaction.user.id)
            user_daily_participation.add(interaction.user.id)
            await interaction.response.send_message("✅ Вы зарегистрированы в розыгрыше!", ephemeral=True)

async def send_quick_giveaway(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚡ Быстрый розыгрыш",
        description=(
            "Your Text Here"
            "Your Text Here"
            "Your Text Here"
        ),
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed, view=QuickGiveawayView(), ephemeral=True)

class MainView(View):
    def __init__(self):
        super().__init__(timeout=None)

    
    @discord.ui.button(label="🎵 Музыка", style=discord.ButtonStyle.primary, custom_id="music_button")
    async def music(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🎵 Меню музыки:", view=MusicView(interaction.user.id), ephemeral=True)

    @discord.ui.button(label="🎮 Игра", style=discord.ButtonStyle.success, custom_id="game_button")
    async def game(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🎮 Добро пожаловать в мини-игру!", view=GameView(interaction.user.id), ephemeral=True)

    @discord.ui.button(label="📱 Приложение", style=discord.ButtonStyle.secondary, custom_id="app_button")
    async def app(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(APP_TEXT, ephemeral=True)

   
    @discord.ui.button(label="🎉 Розыгрыш", style=discord.ButtonStyle.success, custom_id="giveaway_button")
    async def giveaway(self, interaction: discord.Interaction, button: Button):
        record_user(interaction.user.id)
        await interaction.response.send_modal(GiveawayModal())

    @discord.ui.button(label="🛒 Товар", style=discord.ButtonStyle.primary, custom_id="product_button")
    async def product(self, interaction: discord.Interaction, button: Button):
        record_user(interaction.user.id)
        embed = discord.Embed(title="Наш магазин", description="Весь перечень товаров 👇", color=discord.Color.blue())
        view = View()
        view.add_item(Button(label="Перейти в магазин", url="your url"))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="🛠️ Поддержка", style=discord.ButtonStyle.secondary, custom_id="support_button")
    async def support(self, interaction: discord.Interaction, button: Button):
        record_user(interaction.user.id)
        await interaction.response.send_modal(SupportModal())

    @discord.ui.button(label="ℹ️ О нас", style=discord.ButtonStyle.secondary, custom_id="about_button")
    async def about(self, interaction: discord.Interaction, button: Button):
        record_user(interaction.user.id)
        await interaction.response.send_message(ABOUT_US_TEXT, ephemeral=True)

    @discord.ui.button(label="🛡️ Гарантии", style=discord.ButtonStyle.secondary, custom_id="guarantees_button")
    async def guarantees(self, interaction: discord.Interaction, button: Button):
        record_user(interaction.user.id)
        await interaction.response.send_message(GUARANTEES_TEXT, ephemeral=True)

    @discord.ui.button(label="👤 Профиль", style=discord.ButtonStyle.secondary, custom_id="profile_button")
    async def profile(self, interaction: discord.Interaction, button: Button):
        await send_profile(interaction)

    @discord.ui.button(label="⚡ Быстрый розыгрыш", style=discord.ButtonStyle.success, custom_id="quick_giveaway_button")
    async def quick_giveaway(self, interaction: discord.Interaction, button: Button):
        await send_quick_giveaway(interaction)

    @discord.ui.button(label="❓ FAQ", style=discord.ButtonStyle.secondary, custom_id="faq_button")
    async def faq(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(FAQ_TEXT, ephemeral=True)


async def daily_tasks():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.datetime.now()
        draw_time = now.replace(hour=20, minute=0, second=0, microsecond=0)
        reset_time = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if now >= reset_time and now < reset_time + datetime.timedelta(seconds=10):
            quick_giveaway_participants.clear()
            user_daily_participation.clear()
            channel = bot.get_channel(TARGET_CHANNEL_ID)
            if channel:
                await channel.send("🔄 Новый день! Участники розыгрыша сброшены.")

        if now >= draw_time and now < draw_time + datetime.timedelta(seconds=10):
            if quick_giveaway_participants:
                import random
                winners = random.sample(list(quick_giveaway_participants), min(10, len(quick_giveaway_participants)))
                winner_mentions = [f"<@{w}>" for w in winners]
                channel = bot.get_channel(TARGET_CHANNEL_ID)
                if channel:
                    embed = discord.Embed(title="🏆 Победители быстрого розыгрыша", description="\n".join(winner_mentions), color=discord.Color.green())
                    await channel.send(embed=embed)
                for w in winners:
                    try:
                        user = await bot.fetch_user(w)
                        await user.send("🎉 Поздравляем! Вы стали победителем **быстрого розыгрыша**!")
                    except Exception as e:
                                                print(f"Не удалось отправить ЛС {w}: {e}")
            else:
                channel = bot.get_channel(TARGET_CHANNEL_ID)
                if channel:
                    await channel.send("📢 Сегодня участников быстрого розыгрыша не было.")

        await asyncio.sleep(10)


@bot.event
async def on_ready():
    print(f'Бот {bot.user} успешно запущен!')
    bot.add_view(MainView())
    await bot.tree.sync()
    print("Слэш-команды синхронизированы.")
    bot.loop.create_task(daily_tasks())

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if isinstance(message.channel, discord.DMChannel):
        embed = discord.Embed(
            title="Добро пожаловать!",
            description="Вы можете использовать кнопки ниже для навигации.",
            color=0x5865F2
        )
        await message.channel.send(embed=embed, view=MainView())
    await bot.process_commands(message)

@bot.command()
@commands.has_permissions(administrator=True)
async def menu(ctx):
    embed = discord.Embed(
        title="Добро пожаловать в наш магазин!",
        description="Используйте кнопки ниже для навигации.",
        color=0x5865F2
    )
    await ctx.send(embed=embed, view=MainView())
    if isinstance(ctx.channel, discord.TextChannel):
        await ctx.message.delete()

@bot.tree.command(name="stats", description="Показать статистику по пользователям бота")
@app_commands.checks.has_permissions(administrator=True)
async def stats(interaction: discord.Interaction):
    user_count = len(tracked_users)
    await interaction.response.send_message(
        f"📈 Всего ботом воспользовалось: **{user_count}** уникальных пользователей.",
        ephemeral=True
    )

@stats.error
async def on_stats_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ У вас нет прав для использования этой команды.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(f"Произошла ошибка: {error}", ephemeral=True)


bot.run(BOT_TOKEN)



