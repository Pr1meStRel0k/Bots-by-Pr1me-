##Creating By Pr1me_StRel0k##


import discord
from discord.ext import commands, tasks
from discord import app_commands, ui, ButtonStyle, Interaction, TextStyle
import json
import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional


BOT_TOKEN = "Your bot Token"  
ADMIN_ROLE_NAME = "Mod"  
GUILD_ID = ID Your server


DATA_FILE = "data.json"
LOBBIES: Dict[str, dict] = {} 
LOTTERY_TICKETS: List[int] = []  


def load_data() -> dict:
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_data(data: dict):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_user_data(user_id: int) -> dict:
    data = load_data()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {
            "cash": 1000,
            "bank": 0,
            "credit": None,  
            "stats": {
                "total_won": 0,
                "total_spent": 0,
                "last_10_games": []
            },
            "work": {
                "last_worked": None,
                "total_jobs": 0
            },
            "businesses": [],  
        }
        save_data(data)
    return data[uid]

def update_user_data(user_id: int, new_data: dict):
    data = load_data()
    data[str(user_id)] = new_data
    save_data(data)


BUSINESS_TEMPLATES = {
    "kiosk": {"display": "Ларёк (Kiosk)", "base_cost": 5000, "base_income": 200},  
    "cafe": {"display": "Кафе (Cafe)", "base_cost": 20000, "base_income": 1200},
    "shop": {"display": "Магазин (Shop)", "base_cost": 50000, "base_income": 3500},
    "studio": {"display": "Студия (Studio)", "base_cost": 120000, "base_income": 10000},
}

def create_business_instance(key: str) -> dict:
    tpl = BUSINESS_TEMPLATES[key]
    return {
        "key": key,
        "name": tpl["display"],
        "level": 1,
        "income": tpl["base_income"],
        "cost": tpl["base_cost"],
        "last_collected": datetime.now().isoformat()
    }


intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


def format_money(n: float) -> str:
    return f"{int(n):,}"

def generate_lobby_code() -> str:
    while True:
        code = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=5))
        if code not in LOBBIES:
            return code


class GameBotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_credits_and_lottery.start()
        self.business_income_loop.start()


    @app_commands.command(name="balance", description="Проверить ваш баланс GSCoin.")
    async def balance(self, interaction: Interaction):
        user_data = get_user_data(interaction.user.id)
        embed = discord.Embed(
            title=f"Баланс {interaction.user.display_name} 💳",
            color=discord.Color.gold()
        )
        embed.add_field(name="Наличные", value=f"💰 {format_money(user_data['cash'])} GSCoin", inline=True)
        embed.add_field(name="В банке", value=f"🏦 {format_money(user_data['bank'])} GSCoin", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="pay", description="Перевести GSCoin другому игроку.")
    @app_commands.describe(member="Пользователь, которому вы хотите перевести деньги.", amount="Сумма перевода.")
    async def pay(self, interaction: Interaction, member: discord.Member, amount: int):
        if amount <= 0:
            await interaction.response.send_message("Сумма должна быть положительной!", ephemeral=True)
            return
        if member.id == interaction.user.id:
            await interaction.response.send_message("Вы не можете перевести деньги самому себе!", ephemeral=True)
            return

        sender_data = get_user_data(interaction.user.id)
        if sender_data['cash'] < amount:
            await interaction.response.send_message("У вас недостаточно наличных для этого перевода!", ephemeral=True)
            return

        receiver_data = get_user_data(member.id)
        sender_data['cash'] -= amount
        receiver_data['cash'] += amount
        update_user_data(interaction.user.id, sender_data)
        update_user_data(member.id, receiver_data)

        await interaction.response.send_message(f"✅ Вы успешно перевели {format_money(amount)} GSCoin пользователю {member.mention}!")
        try:
            await member.send(f"💸 Вам пришел перевод в размере {format_money(amount)} GSCoin от {interaction.user.mention}!")
        except discord.Forbidden:
            pass
            
    @app_commands.command(name="bank", description="Управление вашим банковским счетом (депозит, снятие).")
    async def bank(self, interaction: Interaction):
        user_data = get_user_data(interaction.user.id)

        class AmountModal(ui.Modal, title="Банковская операция"):
            amount_input = ui.TextInput(label="Сумма", style=TextStyle.short, placeholder="Введите целое число...")

            def __init__(self, operation: str):
                super().__init__()
                self.operation = operation

            async def on_submit(self, interaction: Interaction):
                try:
                    amount = int(self.amount_input.value)
                    if amount <= 0:
                        raise ValueError
                except ValueError:
                    await interaction.response.send_message("Пожалуйста, введите положительное целое число.", ephemeral=True)
                    return
                
                user_data = get_user_data(interaction.user.id)
                
                if self.operation == 'deposit':
                    if user_data['cash'] < amount:
                        await interaction.response.send_message("У вас недостаточно наличных.", ephemeral=True)
                        return
                    user_data['cash'] -= amount
                    user_data['bank'] += amount
                    update_user_data(interaction.user.id, user_data)
                    await interaction.response.send_message(f"✅ Вы успешно положили {format_money(amount)} GSCoin на банковский счет.", ephemeral=True)
                
                elif self.operation == 'withdraw':
                    if user_data['bank'] < amount:
                        await interaction.response.send_message("У вас недостаточно денег в банке.", ephemeral=True)
                        return
                    user_data['bank'] -= amount
                    user_data['cash'] += amount
                    update_user_data(interaction.user.id, user_data)
                    await interaction.response.send_message(f"✅ Вы успешно сняли {format_money(amount)} GSCoin с банковского счета.", ephemeral=True)

        class BankView(ui.View):
            def __init__(self):
                super().__init__(timeout=180)

            @ui.button(label="Положить", style=ButtonStyle.success, emoji="📥")
            async def deposit_button(self, interaction: Interaction, button: ui.Button):
                await interaction.response.send_modal(AmountModal(operation='deposit'))
                self.stop()
            
            @ui.button(label="Снять", style=ButtonStyle.danger, emoji="📤")
            async def withdraw_button(self, interaction: Interaction, button: ui.Button):
                await interaction.response.send_modal(AmountModal(operation='withdraw'))
                self.stop()

        embed = discord.Embed(title="🏦 Ваш Банк", description="Выберите действие:", color=discord.Color.blue())
        embed.add_field(name="Наличные", value=f"💰 {format_money(user_data['cash'])} GSCoin")
        embed.add_field(name="В банке", value=f"🏦 {format_money(user_data['bank'])} GSCoin")
        
        await interaction.response.send_message(embed=embed, view=BankView(), ephemeral=True)

    @app_commands.command(name="leaderstats", description="Показать таблицу лидеров по балансу.")
    async def leaderstats(self, interaction: Interaction):
        data = load_data()
        if not data:
            await interaction.response.send_message("Пока нет данных для таблицы лидеров.", ephemeral=True)
            return

        sorted_users = sorted(
            data.items(),
            key=lambda item: item[1].get('cash', 0) + item[1].get('bank', 0),
            reverse=True
        )

        embed = discord.Embed(title="🏆 Таблица Лидеров", description="Топ-10 самых богатых пользователей", color=discord.Color.blurple())

        for i, (user_id, udata) in enumerate(sorted_users[:10]):
            try:
                user = await self.bot.fetch_user(int(user_id))
                total_balance = udata.get('cash', 0) + udata.get('bank', 0)
                embed.add_field(name=f"{i+1}. {user.display_name}", value=f"💰 {format_money(total_balance)} GSCoin", inline=False)
            except discord.NotFound:
                continue

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="stats", description="Посмотреть вашу игровую статистику.")
    async def stats(self, interaction: Interaction):
        user_data = get_user_data(interaction.user.id)
        stats = user_data['stats']

        embed = discord.Embed(title=f"Статистика {interaction.user.display_name}", color=discord.Color.green())
        embed.add_field(name="Всего выиграно", value=f"🏆 {format_money(stats['total_won'])} GSCoin")
        embed.add_field(name="Всего потрачено/проиграно", value=f"💸 {format_money(stats['total_spent'])} GSCoin")

        last_games = " | ".join(stats['last_10_games']) if stats['last_10_games'] else "Еще не играли"
        embed.add_field(name="Последние 10 игр", value=last_games, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    
    @app_commands.command(name="work", description="Пойти на работу и заработать GSCoin.")
    async def work(self, interaction: Interaction):
        user_data = get_user_data(interaction.user.id)

        if user_data['work']['last_worked']:
            last_worked_time = datetime.fromisoformat(user_data['work']['last_worked'])
            if datetime.now() < last_worked_time + timedelta(days=1):
                await interaction.response.send_message("Вы уже работали сегодня! Приходите завтра.", ephemeral=True)
                return

        class WorkView(ui.View):
            def __init__(self, user_data):
                super().__init__(timeout=180)
                self.user_data = user_data

            async def handle_work(self, interaction: Interaction, job_name: str, salary: int, duration: int):
                await interaction.response.defer(thinking=True, ephemeral=True)
                await asyncio.sleep(duration)

                self.user_data['cash'] += salary
                self.user_data['work']['last_worked'] = datetime.now().isoformat()
                self.user_data['work']['total_jobs'] += 1
                update_user_data(interaction.user.id, self.user_data)

                await interaction.followup.send(f"✅ Рабочий день на должности '{job_name}' окончен! Вы заработали {format_money(salary)} GSCoin.", ephemeral=True)
                self.stop()

            @ui.button(label="Грузчик (1,000 GSCoin)", style=ButtonStyle.secondary)
            async def loader_button(self, interaction: Interaction, button: ui.Button):
                await self.handle_work(interaction, "Грузчик", 1000, 5)

            @ui.button(label="Admin group (5,000 GSCoin)", style=ButtonStyle.secondary)
            async def admin_button(self, interaction: Interaction, button: ui.Button):
                await self.handle_work(interaction, "Admin group", 5000, 10)

            @ui.button(label="Programmer (10,000 GSCoin)", style=ButtonStyle.primary)
            async def programmer_button(self, interaction: Interaction, button: ui.Button):
                await self.handle_work(interaction, "Programmer", 10000, 15)

            @ui.button(label="Создатель GShop (100,000 GSCoin)", style=ButtonStyle.success, disabled=user_data['work']['total_jobs'] < 30)
            async def creator_button(self, interaction: Interaction, button: ui.Button):
                await self.handle_work(interaction, "Создатель GShop", 100000, 30)

        embed = discord.Embed(title="💼 Биржа труда", description="Выберите, кем вы хотите работать сегодня.", color=discord.Color.dark_blue())
        embed.set_footer(text=f"Всего отработано смен: {user_data['work']['total_jobs']}")
        await interaction.response.send_message(embed=embed, view=WorkView(user_data), ephemeral=True)

    
    @app_commands.command(name="credit", description="Взять кредит.")
    @app_commands.describe(amount="Сумма кредита", days="На сколько дней.")
    async def credit(self, interaction: Interaction, amount: int, days: int):
        if amount <= 0 or days <= 0:
            await interaction.response.send_message("Сумма и количество дней должны быть положительными!", ephemeral=True)
            return

        user_data = get_user_data(interaction.user.id)
        if user_data['credit'] is not None:
            await interaction.response.send_message("У вас уже есть активный кредит!", ephemeral=True)
            return

        amount_to_repay = amount * 1.10
        due_date = datetime.now() + timedelta(days=days)

        user_data['cash'] += amount
        user_data['credit'] = {
            "amount_owed": round(amount_to_repay, 2),
            "due_date": due_date.isoformat()
        }
        update_user_data(interaction.user.id, user_data)

        embed = discord.Embed(title="✅ Кредит одобрен!", color=discord.Color.green())
        embed.add_field(name="Получено", value=f"{format_money(amount)} GSCoin")
        embed.add_field(name="Сумма к возврату", value=f"{amount_to_repay:,.2f} GSCoin")
        embed.add_field(name="Вернуть до", value=due_date.strftime("%d.%m.%Y"))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rcredit", description="Оплатить часть кредита.")
    @app_commands.describe(amount="Сумма для погашения.")
    async def rcredit(self, interaction: Interaction, amount: int):
        if amount <= 0:
            await interaction.response.send_message("Сумма должна быть положительной!", ephemeral=True)
            return

        user_data = get_user_data(interaction.user.id)
        if user_data['credit'] is None:
            await interaction.response.send_message("У вас нет активных кредитов.", ephemeral=True)
            return

        if user_data['cash'] < amount:
            await interaction.response.send_message("У вас недостаточно наличных для оплаты.", ephemeral=True)
            return

        user_data['cash'] -= amount
        user_data['credit']['amount_owed'] = round(user_data['credit']['amount_owed'] - amount, 2)

        if user_data['credit']['amount_owed'] <= 0:
            remaining_cash = abs(user_data['credit']['amount_owed'])
            user_data['cash'] += remaining_cash
            user_data['credit'] = None
            message = f"🎉 Вы полностью погасили кредит! Сдача в размере {remaining_cash:,.2f} GSCoin зачислена на ваш счет."
        else:
            message = f"✅ Вы внесли {format_money(amount)} GSCoin. Осталось погасить: {user_data['credit']['amount_owed']:,.2f} GSCoin."

        update_user_data(interaction.user.id, user_data)
        await interaction.response.send_message(message)

    
    @app_commands.command(name="lottery", description="Купить лотерейный билет.")
    @app_commands.describe(tickets="Количество билетов (1 билет = 1,000 GSCoin).")
    async def lottery(self, interaction: Interaction, tickets: int = 1):
        if tickets <= 0:
            await interaction.response.send_message("Количество билетов должно быть положительным.", ephemeral=True)
            return

        cost = tickets * 1000
        user_data = get_user_data(interaction.user.id)

        if user_data['cash'] < cost:
            await interaction.response.send_message(f"Вам не хватает {format_money(cost - user_data['cash'])} GSCoin для покупки билетов.", ephemeral=True)
            return

        user_data['cash'] -= cost
        update_user_data(interaction.user.id, user_data)

        global LOTTERY_TICKETS
        for _ in range(tickets):
            LOTTERY_TICKETS.append(interaction.user.id)

        await interaction.response.send_message(f"🎟️ Вы успешно купили {tickets} лотерейных билета(ов) за {format_money(cost)} GSCoin! Удачи!")

    
    @app_commands.command(name="slots", description="Сыграть в слот-машину.")
    @app_commands.describe(bet="Ваша ставка.")
    async def slots(self, interaction: Interaction, bet: int):
        if bet <= 0:
            await interaction.response.send_message("Ставка должна быть положительной!", ephemeral=True)
            return
            
        user_data = get_user_data(interaction.user.id)
        if user_data['cash'] < bet:
            await interaction.response.send_message("У вас недостаточно наличных для этой ставки.", ephemeral=True)
            return
            
        emojis = ['🍒', '🍋', '🔔', '💰', '⭐']
        results = random.choices(emojis, k=3)
        
        result_str = f"| {results[0]} | {results[1]} | {results[2]} |"
        
        embed = discord.Embed(title="🎰 Слот-машина 🎰", color=discord.Color.dark_orange())
        embed.add_field(name="Результат", value=result_str, inline=False)

        winnings = 0
        outcome_msg = ""
        
        if results[0] == results[1] == results[2]: 
            winnings = bet * 10
            outcome_msg = f"🎉 ДЖЕКПОТ! Вы выиграли {format_money(winnings)} GSCoin!"
            embed.color = discord.Color.gold()
        elif results[0] == results[1] or results[1] == results[2]: 
            winnings = bet * 2
            outcome_msg = f"👍 Небольшой выигрыш! Вы получили {format_money(winnings)} GSCoin!"
            embed.color = discord.Color.green()
        
        if winnings > 0:
            user_data['cash'] += (winnings - bet)
            user_data['stats']['total_won'] += winnings
            user_data['stats']['last_10_games'].insert(0, f"Win Slots (+{format_money(winnings-bet)})")
        else:
            user_data['cash'] -= bet
            user_data['stats']['total_spent'] += bet
            user_data['stats']['last_10_games'].insert(0, f"Lose Slots (-{format_money(bet)})")
            outcome_msg = f"😕 Увы, не повезло. Вы проиграли {format_money(bet)} GSCoin."
            embed.color = discord.Color.red()
        
        user_data['stats']['last_10_games'] = user_data['stats']['last_10_games'][:10]
        update_user_data(interaction.user.id, user_data)
        
        embed.add_field(name="Итог", value=outcome_msg, inline=False)
        embed.set_footer(text=f"Новый баланс: {format_money(user_data['cash'])} GSCoin")
        
        await interaction.response.send_message(embed=embed)

    
    @app_commands.command(name="business", description="Показать доступные бизнесы и ваши бизнесы.")
    async def business(self, interaction: Interaction):
        user_data = get_user_data(interaction.user.id)

        embed = discord.Embed(title="🏬 Бизнесы", description="Список доступных бизнесов и ваши бизнесы.", color=discord.Color.teal())
        available = ""
        for k, tpl in BUSINESS_TEMPLATES.items():
            available += f"**{tpl['display']}** — цена: {format_money(tpl['base_cost'])}, доход/час: {format_money(tpl['base_income'])}\n"
        embed.add_field(name="Доступные бизнесы", value=available, inline=False)

        if user_data['businesses']:
            mybs = ""
            for b in user_data['businesses']:
                mybs += f"{b['name']} — уровень {b['level']}, доход/час {format_money(b['income'])}, куплена: {b['last_collected'][:10]}\n"
        else:
            mybs = "У вас нет бизнесов."

        embed.add_field(name="Ваши бизнесы", value=mybs, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="buy_business", description="Купить бизнес.")
    @app_commands.describe(business_key="Ключ бизнеса (kiosk, cafe, shop, studio)")
    async def buy_business(self, interaction: Interaction, business_key: str):
        key = business_key.lower()
        if key not in BUSINESS_TEMPLATES:
            await interaction.response.send_message("Неверный ключ бизнеса. Доступно: kiosk, cafe, shop, studio", ephemeral=True)
            return

        user_data = get_user_data(interaction.user.id)
        cost = BUSINESS_TEMPLATES[key]["base_cost"]
        if user_data['cash'] < cost:
            await interaction.response.send_message(f"У вас недостаточно денег. Нужно {format_money(cost)} GSCoin.", ephemeral=True)
            return

        user_data['cash'] -= cost
        newb = create_business_instance(key)
        user_data['businesses'].append(newb)
        update_user_data(interaction.user.id, user_data)

        await interaction.response.send_message(f"✅ Вы купили бизнес: {newb['name']} за {format_money(cost)} GSCoin", ephemeral=True)

    @app_commands.command(name="upgrade_business", description="Улучшить бизнес (увеличивает доход и стоимость).")
    @app_commands.describe(index="Номер бизнеса в списке (начиная с 1).")
    async def upgrade_business(self, interaction: Interaction, index: int):
        user_data = get_user_data(interaction.user.id)
        if index <= 0 or index > len(user_data['businesses']):
            await interaction.response.send_message("Неверный индекс бизнеса.", ephemeral=True)
            return

        b = user_data['businesses'][index - 1]
        upgrade_cost = int(b['cost'] * 0.7 * b['level'])
        if user_data['cash'] < upgrade_cost:
            await interaction.response.send_message(f"У вас недостаточно денег. Нужно {format_money(upgrade_cost)} GSCoin.", ephemeral=True)
            return

        user_data['cash'] -= upgrade_cost
        b['level'] += 1
        b['income'] = int(b['income'] * 1.45)
        b['cost'] = int(b['cost'] * 1.6)
        update_user_data(interaction.user.id, user_data)

        await interaction.response.send_message(f"✅ Бизнес '{b['name']}' улучшен до уровня {b['level']}. Стоимость апгрейда: {format_money(upgrade_cost)} GSCoin", ephemeral=True)

    @app_commands.command(name="sell_business", description="Продать бизнес (получаете 50% от текущей стоимости).")
    @app_commands.describe(index="Номер бизнеса в списке (начиная с 1).")
    async def sell_business(self, interaction: Interaction, index: int):
        user_data = get_user_data(interaction.user.id)
        if index <= 0 or index > len(user_data['businesses']):
            await interaction.response.send_message("Неверный индекс бизнеса.", ephemeral=True)
            return

        b = user_data['businesses'].pop(index - 1)
        sell_price = int(b['cost'] * 0.5)
        user_data['cash'] += sell_price
        update_user_data(interaction.user.id, user_data)

        await interaction.response.send_message(f"🟤 Вы продали '{b['name']}' за {format_money(sell_price)} GSCoin.", ephemeral=True)

    @app_commands.command(name="collect_business", description="Собрать накопленный доход от всех бизнесов (ручной сбор).")
    async def collect_business(self, interaction: Interaction):
        user_data = get_user_data(interaction.user.id)
        if not user_data['businesses']:
            await interaction.response.send_message("У вас нет бизнесов.", ephemeral=True)
            return

        total_collected = 0
        now = datetime.now()
        for b in user_data['businesses']:
            last = datetime.fromisoformat(b.get('last_collected', now.isoformat()))
            hours = int((now - last).total_seconds() // 3600)
            if hours > 0:
                gained = b['income'] * hours
                total_collected += gained
                b['last_collected'] = now.isoformat()

        if total_collected <= 0:
            await interaction.response.send_message("Пока нет дохода для сбора (меньше часа с последнего сбора).", ephemeral=True)
            return

        user_data['cash'] += total_collected
        update_user_data(interaction.user.id, user_data)

        await interaction.response.send_message(f"💰 Вы собрали {format_money(total_collected)} GSCoin с ваших бизнесов.", ephemeral=True)

   
    @app_commands.command(name="lobby_create", description="Создать лобби для игры.")
    @app_commands.describe(max_players="Максимум игроков (2-8).", ante="Вступительный взнос за игру (GSCoin).")
    async def lobby_create(self, interaction: Interaction, max_players: int = 4, ante: int = 100):
        if max_players < 2 or max_players > 8:
            await interaction.response.send_message("Максимальное число игроков должно быть от 2 до 8.", ephemeral=True)
            return
        if ante < 0:
            await interaction.response.send_message("Анте не может быть отрицательным.", ephemeral=True)
            return

        code = generate_lobby_code()
        LOBBIES[code] = {
            "host": interaction.user.id,
            "players": [interaction.user.id],
            "max": max_players,
            "ante": ante,
            "started": False
        }

        class LobbyView(ui.View):
            def __init__(self, code):
                super().__init__(timeout=None)
                self.code = code

            @ui.button(label="Присоединиться", style=ButtonStyle.primary)
            async def join_button(self, interaction: Interaction, button: ui.Button):
                lobby = LOBBIES.get(self.code)
                if not lobby:
                    await interaction.response.send_message("Лобби больше не существует.", ephemeral=True)
                    return
                if interaction.user.id in lobby['players']:
                    await interaction.response.send_message("Вы уже в лобби.", ephemeral=True)
                    return
                if len(lobby['players']) >= lobby['max']:
                    await interaction.response.send_message("Лобби заполнено.", ephemeral=True)
                    return
                
                user_data = get_user_data(interaction.user.id)
                if user_data['cash'] < lobby['ante']:
                    await interaction.response.send_message(f"У вас недостаточно денег для участия (нужно {format_money(lobby['ante'])}).", ephemeral=True)
                    return

                lobby['players'].append(interaction.user.id)
                await interaction.response.send_message(f"✅ Вы присоединились к лобби {self.code}.", ephemeral=True)

        embed = discord.Embed(title=f"Лобби {code}", description=f"Хост: {interaction.user.display_name}\nИгроки: 1/{max_players}\nАнте: {format_money(ante)} GSCoin", color=discord.Color.dark_purple())
        await interaction.response.send_message(embed=embed, view=LobbyView(code))
    
    @app_commands.command(name="lobby_list", description="Показать активные лобби.")
    async def lobby_list(self, interaction: Interaction):
        if not LOBBIES:
            await interaction.response.send_message("Нет активных лобби.", ephemeral=True)
            return
        txt = ""
        for code, l in LOBBIES.items():
            txt += f"{code} — {len(l['players'])}/{l['max']} игроков, анте {format_money(l['ante'])}\n"
        embed = discord.Embed(title="Активные лобби", description=txt, color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="lobby_join", description="Присоединиться к лобби по коду.")
    @app_commands.describe(code="Код лобби.")
    async def lobby_join(self, interaction: Interaction, code: str):
        code = code.upper()
        lobby = LOBBIES.get(code)
        if not lobby:
            await interaction.response.send_message("Лобби с таким кодом не найдено.", ephemeral=True)
            return
        if interaction.user.id in lobby['players']:
            await interaction.response.send_message("Вы уже в лобби.", ephemeral=True)
            return
        if len(lobby['players']) >= lobby['max']:
            await interaction.response.send_message("Лобби заполнено.", ephemeral=True)
            return

        user_data = get_user_data(interaction.user.id)
        if user_data['cash'] < lobby['ante']:
            await interaction.response.send_message(f"У вас недостаточно денег для участия (нужно {format_money(lobby['ante'])}).", ephemeral=True)
            return

        lobby['players'].append(interaction.user.id)
        await interaction.response.send_message(f"✅ Вы присоединились к лобби {code}.", ephemeral=True)

    @app_commands.command(name="lobby_leave", description="Выйти из лобби по коду.")
    @app_commands.describe(code="Код лобби.")
    async def lobby_leave(self, interaction: Interaction, code: str):
        code = code.upper()
        lobby = LOBBIES.get(code)
        if not lobby:
            await interaction.response.send_message("Лобби с таким кодом не найдено.", ephemeral=True)
            return
        if interaction.user.id not in lobby['players']:
            await interaction.response.send_message("Вы не в этом лобби.", ephemeral=True)
            return

        lobby['players'].remove(interaction.user.id)
        await interaction.response.send_message("Вы покинули лобби.", ephemeral=True)

    @app_commands.command(name="lobby_start", description="Запустить игру в лобби (только хост).")
    @app_commands.describe(code="Код лобби.")
    async def lobby_start(self, interaction: Interaction, code: str):
        code = code.upper()
        lobby = LOBBIES.get(code)
        if not lobby:
            await interaction.response.send_message("Лобби с таким кодом не найдено.", ephemeral=True)
            return
        if interaction.user.id != lobby['host']:
            await interaction.response.send_message("Только хост может запускать игру.", ephemeral=True)
            return
        if lobby['started']:
            await interaction.response.send_message("Игра уже запущена в этом лобби.", ephemeral=True)
            return
        if len(lobby['players']) < 2:
            await interaction.response.send_message("Нужно как минимум 2 игрока чтобы начать.", ephemeral=True)
            return

        for uid in list(lobby['players']):
            udata = get_user_data(uid)
            if udata['cash'] < lobby['ante']:
                lobby['players'].remove(uid)
                try:
                    user = await self.bot.fetch_user(uid)
                    await user.send(f"Вы исключены из лобби {code}, т.к. у вас недостаточно денег для анте {format_money(lobby['ante'])}.")
                except Exception:
                    pass

        if len(lobby['players']) < 2:
            await interaction.response.send_message("Недостаточно игроков с деньгами для старта.", ephemeral=True)
            return

        pot = 0
        for uid in lobby['players']:
            udata = get_user_data(uid)
            udata['cash'] -= lobby['ante']
            update_user_data(uid, udata)
            pot += lobby['ante']

        lobby['started'] = True
        await interaction.response.send_message(f"🎮 Игра начата в лобби {code}! Игра: High Card Duel. Банк: {format_money(pot)} GSCoin. Сейчас тянем карты...", ephemeral=False)

        results = []
        for uid in lobby['players']:
            card = random.randint(1, 13)
            results.append((uid, card))
        results_sorted = sorted(results, key=lambda x: x[1], reverse=True)
        top_value = results_sorted[0][1]
        winners = [uid for (uid, val) in results_sorted if val == top_value]

        if len(winners) == 1:
            winner = winners[0]
            winner_data = get_user_data(winner)
            winner_data['cash'] += pot
            winner_data['stats']['total_won'] += pot
            winner_data['stats']['last_10_games'].insert(0, f"Win {format_money(pot)} in {code}")
            winner_data['stats']['last_10_games'] = winner_data['stats']['last_10_games'][:10]
            update_user_data(winner, winner_data)

            txt = "Результаты розыгрыша:\n"
            for uid, card in results:
                try:
                    user = await self.bot.fetch_user(uid)
                    txt += f"{user.display_name}: {card}\n"
                except Exception:
                    txt += f"{uid}: {card}\n"
            winner_user = await self.bot.fetch_user(winner)
            await interaction.followup.send(txt)
            await interaction.followup.send(f"🏆 Победитель: {winner_user.mention}! Вы выиграли {format_money(pot)} GSCoin!")
        else:
            share = pot // len(winners)
            for w in winners:
                wd = get_user_data(w)
                wd['cash'] += share
                wd['stats']['total_won'] += share
                wd['stats']['last_10_games'].insert(0, f"Split {format_money(share)} in {code}")
                wd['stats']['last_10_games'] = wd['stats']['last_10_games'][:10]
                update_user_data(w, wd)

            txt = "Результаты розыгрыша (ничья, делим банк):\n"
            for uid, card in results:
                try:
                    user = await self.bot.fetch_user(uid)
                    txt += f"{user.display_name}: {card}\n"
                except Exception:
                    txt += f"{uid}: {card}\n"
            await interaction.followup.send(txt)
            winner_mentions = ", ".join([(await self.bot.fetch_user(w)).mention for w in winners])
            await interaction.followup.send(f"🤝 Ничья! Победители: {winner_mentions}. Каждый получает {format_money(share)} GSCoin.")

        for uid, card in results:
            if uid not in winners:
                ud = get_user_data(uid)
                ud['stats']['total_spent'] += lobby['ante']
                ud['stats']['last_10_games'].insert(0, f"Lose {format_money(lobby['ante'])} in {code}")
                ud['stats']['last_10_games'] = ud['stats']['last_10_games'][:10]
                update_user_data(uid, ud)

        try:
            del LOBBIES[code]
        except KeyError:
            pass

    
    @app_commands.command(name="pcoin", description="[Админ] Начислить пользователю GSCoin.")
    @app_commands.checks.has_role("id admin role here")
    async def pcoin(self, interaction: Interaction, member: discord.Member, amount: int):
        if amount <= 0:
            await interaction.response.send_message("Сумма должна быть положительной!", ephemeral=True)
            return

        user_data = get_user_data(member.id)
        user_data['cash'] += amount
        update_user_data(member.id, user_data)
        await interaction.response.send_message(f"✅ Начислено {format_money(amount)} GSCoin пользователю {member.mention}.", ephemeral=True)

    @app_commands.command(name="scoin", description="[Админ] Списать у пользователя GSCoin.")
    @app_commands.checks.has_role("id admin role here")
    async def scoin(self, interaction: Interaction, member: discord.Member, amount: int):
        if amount <= 0:
            await interaction.response.send_message("Сумма должна быть положительной!", ephemeral=True)
            return

        user_data = get_user_data(member.id)
        user_data['cash'] -= amount
        update_user_data(member.id, user_data)
        await interaction.response.send_message(f"✅ Списано {format_money(amount)} GSCoin у пользователя {member.mention}.", ephemeral=True)

    @app_commands.command(name="reset", description="[Админ] Сбросить статистику и баланс пользователя.")
    @app_commands.checks.has_role("id admin role here")
    async def reset(self, interaction: Interaction, member: discord.Member):
        data = load_data()
        user_id_str = str(member.id)
        if user_id_str in data:
            del data[user_id_str]
            save_data(data)
            await interaction.response.send_message(f"🗑️ Вся статистика и баланс пользователя {member.mention} были сброшены.", ephemeral=True)
        else:
            await interaction.response.send_message("У этого пользователя и так нет данных.", ephemeral=True)

    
    @tasks.loop(hours=24)
    async def check_credits_and_lottery(self):
        data = load_data()
        updated = False
        for user_id_str, user_data in data.items():
            if user_data.get('credit'):
                due_date = datetime.fromisoformat(user_data['credit']['due_date'])
                if datetime.now() > due_date:
                    user_data['credit']['amount_owed'] = round(user_data['credit']['amount_owed'] * 1.05, 2)
                    updated = True
                    try:
                        user = await self.bot.fetch_user(int(user_id_str))
                        await user.send(f"⚠️ **Просрочка по кредиту!** Ваш долг увеличен на 5% и теперь составляет {user_data['credit']['amount_owed']:,.2f} GSCoin.")
                    except (discord.NotFound, discord.Forbidden):
                        pass
        if updated:
            save_data(data)

        if datetime.now().weekday() == 6: 
            global LOTTERY_TICKETS
            if LOTTERY_TICKETS:
                winner_id = random.choice(LOTTERY_TICKETS)
                prize_pool = len(LOTTERY_TICKETS) * 1000
                winner_data = get_user_data(winner_id)
                winner_data['cash'] += prize_pool
                update_user_data(winner_id, winner_data)
                try:
                    winner_user = await self.bot.fetch_user(winner_id)
                    await winner_user.send(f"🎉 **Поздравляем!** Вы выиграли в еженедельной лотерее! Ваш выигрыш: {format_money(prize_pool)} GSCoin!")
                except (discord.NotFound, discord.Forbidden):
                    pass
                LOTTERY_TICKETS = []

    @tasks.loop(minutes=60)
    async def business_income_loop(self):
        data = load_data()
        updated = False
        for uid_str, udata in data.items():
            businesses = udata.get('businesses', [])
            if not businesses:
                continue
            now = datetime.now()
            total_gain = 0
            for b in businesses:
                last = datetime.fromisoformat(b.get('last_collected', now.isoformat()))
                hours = int((now - last).total_seconds() // 3600)
                if hours > 0:
                    gain = b['income'] * hours
                    total_gain += gain
                    b['last_collected'] = now.isoformat()
            if total_gain > 0:
                udata['cash'] += total_gain
                updated = True
                try:
                    user = await self.bot.fetch_user(int(uid_str))
                    await user.send(f"💼 Автосбор: Вы получили {format_money(total_gain)} GSCoin с ваших бизнесов.")
                except (discord.NotFound, discord.Forbidden):
                    pass
        if updated:
            save_data(data)

    @check_credits_and_lottery.before_loop
    async def before_check_credits(self):
        await self.bot.wait_until_ready()

    @business_income_loop.before_loop
    async def before_business_loop(self):
        await self.bot.wait_until_ready()

    def cog_unload(self):
        self.check_credits_and_lottery.cancel()
        self.business_income_loop.cancel()


@bot.event
async def on_ready():
    print(f'Бот {bot.user} успешно запущен!')
    print('--------------------------------')
    try:
        await bot.add_cog(GameBotCog(bot))
    except Exception as e:
        print("Ошибка при добавлении COG:", e)
    guild = discord.Object(id=GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
    print("Команды синхронизированы.")


if __name__ == "__main__":
    bot.run(BOT_TOKEN)

