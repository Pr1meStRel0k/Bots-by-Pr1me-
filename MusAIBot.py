##Creating By Pr1me_StRel0k##

import os
import asyncio
import json
import traceback
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Union

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui, Interaction


import yt_dlp
from youtubesearchpython.__future__ import VideosSearch
import aiosqlite


try:
    import openai
except ImportError:
    openai = None

try:
    from shazamio import Shazam
except ImportError:
    Shazam = None


TOKEN = os.environ.get("DISCORD_TOKEN") or "YOUR_TOKEN_HERE"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


if openai and OPENAI_API_KEY:
    openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
else:
    openai_client = None


DB_PATH = "musaibot.db"

YTDL_OPTS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'skip_download': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'cookiefile': 'cookies.txt'
}
YTDL = yt_dlp.YoutubeDL(YTDL_OPTS)

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)


@dataclass
class Track:
    title: str
    url: str L
    stream_url: str 
    duration: float = 0.0
    source: str = 'youtube'
    requested_by: Optional[int] = None
    
    def to_dict(self):
        return {
            'title': self.title,
            'url': self.url,
            'duration': self.duration,
            'source': self.source
        }


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
        CREATE TABLE IF NOT EXISTS playlists (
            id INTEGER PRIMARY KEY,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            tracks_json TEXT,
            UNIQUE(guild_id, user_id, name)
        )
        ''')
        await db.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY,
            history_json TEXT
        )
        ''')
        await db.commit()

async def save_playlist(guild_id: int, user_id: int, name: str, tracks: List[Dict]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('REPLACE INTO playlists (guild_id, user_id, name, tracks_json) VALUES (?,?,?,?)',
                         (guild_id, user_id, name, json.dumps(tracks, ensure_ascii=False)))
        await db.commit()

async def load_playlist(guild_id: int, user_id: int, name: str) -> Optional[List[Dict]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT tracks_json FROM playlists WHERE guild_id=? AND user_id=? AND name=?', (guild_id, user_id, name)) as cursor:
            r = await cursor.fetchone()
            if r:
                return json.loads(r[0])
            return None

async def list_playlists(guild_id: int, user_id: int) -> List[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT name FROM playlists WHERE guild_id=? AND user_id=?', (guild_id, user_id)) as cursor:
            return [row[0] for row in await cursor.fetchall()]

async def delete_playlist(guild_id: int, user_id: int, name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM playlists WHERE guild_id=? AND user_id=? AND name=?', (guild_id, user_id, name))
        await db.commit()

async def update_profile_history(user_id: int, track: Track):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT history_json FROM profiles WHERE user_id=?', (user_id,)) as cursor:
            r = await cursor.fetchone()
        
        history = json.loads(r[0]) if (r and r[0]) else {}
        
       
        track_key = track.url
        if track_key in history:
            history[track_key]['count'] += 1
        else:
            history[track_key] = {
                'title': track.title,
                'count': 1
            }

        await db.execute('REPLACE INTO profiles (user_id, history_json) VALUES (?,?)',
                         (user_id, json.dumps(history, ensure_ascii=False)))
        await db.commit()

async def get_profile(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT history_json FROM profiles WHERE user_id=?', (user_id,)) as cursor:
            r = await cursor.fetchone()
            if r and r[0]:
                return json.loads(r[0])
            return None

async def get_all_profiles() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT user_id, history_json FROM profiles') as cursor:
            return [{'user_id': r[0], 'history': json.loads(r[1])} for r in await cursor.fetchall() if r[1]]


class GuildPlayer:
    def __init__(self, bot_loop: asyncio.AbstractEventLoop, guild: discord.Guild):
        self.loop = bot_loop
        self.guild = guild
        self.queue: List[Track] = []
        self.current: Optional[Track] = None
        self.voice_client: Optional[discord.VoiceClient] = None
        self.volume = 0.5
        self.skip_votes = set()
        self.player_task: Optional[asyncio.Task] = None

    async def connect(self, channel: discord.VoiceChannel):
        if self.voice_client and self.voice_client.is_connected():
            if self.voice_client.channel.id != channel.id:
                await self.voice_client.move_to(channel)
        else:
            self.voice_client = await channel.connect()
        return self.voice_client

    def play_next(self):
        if not self.queue:
            self.current = None
            return
        
        self.current = self.queue.pop(0)
        self.skip_votes.clear()
        
        source = create_ffmpeg_audio(self.current.stream_url, volume=self.volume)
        
        if not self.voice_client or not self.voice_client.is_connected():
            print(f"[{self.guild.name}] Voice client not connected, cannot play.")
            self.current = None
            return

        
        if self.current.requested_by:
            asyncio.run_coroutine_threadsafe(update_profile_history(self.current.requested_by, self.current), self.loop)

        self.voice_client.play(source, after=lambda e: self.loop.call_soon_threadsafe(self.after_track, e))

    def after_track(self, error):
        if error:
            print(f'Player error in guild {self.guild.id}: {error}')
        
        self.play_next()


players: Dict[int, GuildPlayer] = {}

def get_player(ctx: Union[Interaction, commands.Context]) -> GuildPlayer:
    guild = ctx.guild
    if guild.id not in players:
        players[guild.id] = GuildPlayer(bot.loop, guild)
    return players[guild.id]


async def extract_info(query: str) -> Optional[Track]:
    loop = asyncio.get_running_loop()
    try:
        data = await loop.run_in_executor(None, lambda: YTDL.extract_info(query, download=False))
        
        if 'entries' in data:
            data = data['entries'][0]

        return Track(
            title=data.get('title', 'Unknown Title'),
            url=data.get('webpage_url', ''),
            stream_url=data.get('url', ''),
            duration=data.get('duration', 0),
            source='youtube'
        )
    except Exception as e:
        print(f"Error extracting info for '{query}': {e}")
        try:
            search_result = await VideosSearch(query, limit=1).next()
            if search_result and search_result['result']:
                video_id = search_result['result'][0]['id']
                return await extract_info(f"https://www.youtube.com/watch?v={video_id}")
        except Exception as search_e:
            print(f"Fallback search also failed for '{query}': {search_e}")

    return None

def create_ffmpeg_audio(stream_url: str, volume: float = 0.5):
    source = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS)
    return discord.PCMVolumeTransformer(source, volume=volume)


async def generate_lyrics(prompt: str) -> str:
    if not openai_client:
        return "OpenAI library not installed or OPENAI_API_KEY not set."
    try:
        resp = await openai_client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {"role": "system", "content": "You are a creative songwriter."},
                {"role": "user", "content": f"Write a song chorus/verse about: {prompt}"}
            ],
            max_tokens=200, temperature=0.8,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating lyrics: {e}"

async def chat_with_ai(user_prompt: str) -> str:
    if not openai_client:
        return "OpenAI library not installed or OPENAI_API_KEY not set."
    try:
        resp = await openai_client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=300,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Error in chat: {e}"


class PlayerControls(ui.View):
    def __init__(self, player: GuildPlayer):
        super().__init__(timeout=None)
        self.player = player

    @ui.button(label='⏯️', style=discord.ButtonStyle.primary)
    async def toggle(self, interaction: Interaction, button: ui.Button):
        vc = self.player.voice_client
        if not vc or not vc.is_connected():
            await interaction.response.send_message('Бот не в голосовом канале.', ephemeral=True)
            return
        
        if vc.is_paused():
            vc.resume()
            await interaction.response.send_message('▶️ Возобновлено', ephemeral=True)
        elif vc.is_playing():
            vc.pause()
            await interaction.response.send_message('⏸️ Пауза', ephemeral=True)

    @ui.button(label='⏭️', style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: Interaction, button: ui.Button):
        if self.player.voice_client and self.player.voice_client.is_playing():
            self.player.voice_client.stop()
            await interaction.response.send_message(f'Пропущено.', ephemeral=True)
        else:
            await interaction.response.send_message('Нечего пропускать.', ephemeral=True)

    @ui.button(label='⏹️', style=discord.ButtonStyle.danger)
    async def stop(self, interaction: Interaction, button: ui.Button):
        self.player.queue.clear()
        if self.player.voice_client:
            self.player.voice_client.stop()
        await interaction.response.send_message(f'Очередь очищена и воспроизведение остановлено.', ephemeral=False)

    @ui.button(label='📜', style=discord.ButtonStyle.secondary)
    async def show_queue(self, interaction: Interaction, button: ui.Button):
        q = self.player.queue
        current = self.player.current
        
        if not q and not current:
            await interaction.response.send_message('Очередь пуста.', ephemeral=True)
            return
        
        embed = discord.Embed(title="Очередь", color=discord.Color.blue())
        if current:
            embed.add_field(name="Сейчас играет", value=f"[{current.title}]({current.url})", inline=False)

        if q:
            text = '\n'.join([f"{i+1}. {t.title}" for i, t in enumerate(q[:10])])
            embed.add_field(name="Далее в очереди", value=text, inline=False)
            if len(q) > 10:
                embed.set_footer(text=f"...и еще {len(q)-10} треков.")
            
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def process_slash_play(interaction: Interaction, query: str):
    
    player = get_player(interaction)
    user = interaction.user

    if not user.voice:
        await interaction.edit_original_response(content='Вы должны быть в голосовом канале, чтобы вызвать бота.', embed=None, view=None)
        return
        
    if not player.voice_client or not player.voice_client.is_connected():
        try:
            await player.connect(user.voice.channel)
        except Exception as e:
            await interaction.edit_original_response(content=f'Не удалось подключиться к каналу: {e}', embed=None, view=None)
            return
    
    track = await extract_info(query)
    if not track:
        await interaction.edit_original_response(content=f'Не удалось найти трек по запросу: "{query}"', embed=None, view=None)
        return
        
    track.requested_by = user.id
    player.queue.append(track)

    msg = f'🎵 **Добавлено в очередь:** [{track.title}]({track.url})'
    embed = discord.Embed(description=msg, color=discord.Color.green())
    
    
    await interaction.edit_original_response(content=None, embed=embed, view=PlayerControls(player))

    if not player.voice_client.is_playing():
        player.play_next()
async def enqueue_and_play(ctx: Union[Interaction, commands.Context], query: str):
    player = get_player(ctx)
    user = ctx.author if isinstance(ctx, commands.Context) else ctx.user

    if not user.voice:
        msg = 'Вы должны быть в голосовом канале, чтобы вызвать бота.'
        if isinstance(ctx, Interaction): await ctx.followup.send(msg, ephemeral=True)
        else: await ctx.send(msg)
        return
        
    if not player.voice_client:
        await player.connect(user.voice.channel)
    
    track = await extract_info(query)
    if not track:
        msg = f'Не удалось найти трек по запросу: "{query}"'
        if isinstance(ctx, Interaction): await ctx.followup.send(msg, ephemeral=True)
        else: await ctx.send(msg)
        return
        
    track.requested_by = user.id
    player.queue.append(track)
    
    msg = f'🎵 **Добавлено в очередь:** [{track.title}]({track.url})'
    embed = discord.Embed(description=msg, color=discord.Color.green())
    
    if isinstance(ctx, Interaction):
        await ctx.followup.send(embed=embed, view=PlayerControls(player))
    else:
        await ctx.send(embed=embed, view=PlayerControls(player))

    if not player.voice_client.is_playing():
        player.play_next()


@bot.event
async def on_ready():
    await init_db()
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print('Sync failed:', e)
    print(f'Logged in as {bot.user}')

@bot.tree.command(name='join', description='Зайти в ваш голосовой канал')
async def join(interaction: Interaction):
    player = get_player(interaction)
    if not interaction.user.voice:
        await interaction.response.send_message('Вы не в голосовом канале.', ephemeral=True)
        return
    
    channel = interaction.user.voice.channel
    await player.connect(channel)
    await interaction.response.send_message(f'Подключился к **{channel.name}**', view=PlayerControls(player))

@bot.tree.command(name='play', description='Воспроизвести трек по ссылке или названию')
@app_commands.describe(query='URL или поисковый запрос')
async def slash_play(interaction: Interaction, query: str):
    await interaction.response.defer()
    await process_slash_play(interaction, query)


@bot.tree.command(name='chat', description='Пообщаться с AI на любую тему')
@app_commands.describe(prompt='Ваше сообщение для AI')
async def slash_chat(interaction: Interaction, prompt: str):
    await interaction.response.defer()
    response_text = await chat_with_ai(prompt)
    embed = discord.Embed(title=f"Ответ на '{prompt[:50]}...'", description=response_text, color=0x9eecfa)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name='lyrics', description='Сгенерировать текст песни с помощью AI')
@app_commands.describe(prompt='Тема или строки для генерации')
async def slash_lyrics(interaction: Interaction, prompt: str):
    await interaction.response.defer()
    txt = await generate_lyrics(prompt)
    embed = discord.Embed(title=f"Текст для '{prompt}'", description=txt, color=0xfae69e)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name='recognize', description='Распознать трек по аудиофайлу')
@app_commands.describe(file='Аудиофайл для распознавания (mp3, wav, etc.)')
async def slash_recognize(interaction: Interaction, file: discord.Attachment):
    await interaction.response.defer()
    if not Shazam:
        await interaction.followup.send('Библиотека Shazamio не установлена.', ephemeral=True)
        return
    
    try:
        fp = await file.read()
        shazam = Shazam()
        out = await shazam.recognize(fp)
        
        track_info = out.get('track')
        if not track_info:
            await interaction.followup.send("Не удалось распознать трек.", ephemeral=True)
            return

        title = track_info.get('title', 'N/A')
        artist = track_info.get('subtitle', 'N/A')
        
        embed = discord.Embed(title="🎵 Трек распознан", color=discord.Color.blue())
        embed.add_field(name="Название", value=title)
        embed.add_field(name="Исполнитель", value=artist)
        if 'images' in track_info and 'coverart' in track_info['images']:
            embed.set_thumbnail(url=track_info['images']['coverart'])

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"Произошла ошибка: {e}", ephemeral=True)

@bot.tree.command(name='volume', description='Установить громкость (от 0 до 200%)')
@app_commands.describe(value='Значение громкости (например, 80)')
async def slash_volume(interaction: Interaction, value: app_commands.Range[int, 0, 200]):
    player = get_player(interaction)
    new_volume = value / 100.0
    player.volume = new_volume
    
    if player.voice_client and player.voice_client.source:
        player.voice_client.source.volume = new_volume
        
    await interaction.response.send_message(f'🔊 Громкость установлена на {value}%')


playlist_group = app_commands.Group(name="playlist", description="Управление плейлистами")

@playlist_group.command(name="save", description="Сохранить текущую очередь как плейлист")
@app_commands.describe(name="Название для вашего плейлиста")
async def playlist_save(interaction: Interaction, name: str):
    player = get_player(interaction)
    queue = [player.current.to_dict()] if player.current else []
    queue.extend([track.to_dict() for track in player.queue])
    
    if not queue:
        await interaction.response.send_message("Очередь пуста, нечего сохранять.", ephemeral=True)
        return
    
    await save_playlist(interaction.guild_id, interaction.user.id, name, queue)
    await interaction.response.send_message(f"✅ Плейлист **{name}** сохранен! ({len(queue)} треков)")

@playlist_group.command(name="load", description="Загрузить плейлист в очередь")
@app_commands.describe(name="Название плейлиста для загрузки")
async def playlist_load(interaction: Interaction, name: str):
    await interaction.response.defer()
    
    tracks_data = await load_playlist(interaction.guild_id, interaction.user.id, name)
    if not tracks_data:
        await interaction.followup.send(f"Плейлист **{name}** не найден.", ephemeral=True)
        return
    
    player = get_player(interaction)
    if not interaction.user.voice:
        await interaction.followup.send("Вы должны быть в голосовом канале.", ephemeral=True)
        return

    if not player.voice_client:
        await player.connect(interaction.user.voice.channel)
    
    count = 0
    for track_data in tracks_data:
        
        track = await extract_info(track_data['url'])
        if track:
            track.requested_by = interaction.user.id
            player.queue.append(track)
            count += 1
    
    await interaction.followup.send(f"🎵 Загружено **{count}** треков из плейлиста **{name}**.")
    
    if not player.voice_client.is_playing():
        player.play_next()

@playlist_group.command(name="list", description="Показать ваши сохраненные плейлисты")
async def playlist_list(interaction: Interaction):
    playlists = await list_playlists(interaction.guild_id, interaction.user.id)
    if not playlists:
        await interaction.response.send_message("У вас нет сохраненных плейлистов.", ephemeral=True)
        return
        
    embed = discord.Embed(title=f"Плейлисты пользователя {interaction.user.display_name}", color=0x3498db)
    embed.description = "\n".join([f"• {name}" for name in playlists])
    await interaction.response.send_message(embed=embed)

@playlist_group.command(name="delete", description="Удалить один из ваших плейлистов")
@app_commands.describe(name="Название плейлиста для удаления")
async def playlist_delete(interaction: Interaction, name: str):
    await delete_playlist(interaction.guild_id, interaction.user.id, name)
    await interaction.response.send_message(f"Плейлист **{name}** удален.", ephemeral=True)

bot.tree.add_command(playlist_group)


@bot.tree.command(name='profile', description='Показать вашу музыкальную статистику')
@app_commands.describe(user="Пользователь, чей профиль вы хотите посмотреть (необязательно)")
async def slash_profile(interaction: Interaction, user: Optional[discord.Member] = None):
    target_user = user or interaction.user
    profile_data = await get_profile(target_user.id)
    
    if not profile_data:
        await interaction.response.send_message(f"У пользователя {target_user.mention} еще нет статистики.", ephemeral=True)
        return

    sorted_tracks = sorted(profile_data.values(), key=lambda x: x['count'], reverse=True)
    total_plays = sum(track['count'] for track in sorted_tracks)

    embed = discord.Embed(title=f"Музыкальный профиль {target_user.display_name}", color=0x1abc9c)
    embed.set_thumbnail(url=target_user.display_avatar.url)
    embed.add_field(name="🎧 Всего прослушано треков", value=str(total_plays), inline=False)
    
    top_tracks_str = "\n".join([f"**{t['count']} раз** - {t['title']}" for t in sorted_tracks[:5]])
    if top_tracks_str:
        embed.add_field(name="⭐ Топ-5 треков", value=top_tracks_str, inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='top', description='Показать топ слушателей на сервере')
async def slash_top(interaction: Interaction):
    await interaction.response.defer()
    all_profiles = await get_all_profiles()
    
    guild_members_ids = {member.id for member in interaction.guild.members}
    
    leaderboard = []
    for profile in all_profiles:
        if profile['user_id'] in guild_members_ids:
            total_plays = sum(track['count'] for track in profile['history'].values())
            leaderboard.append({'user_id': profile['user_id'], 'plays': total_plays})
    
    if not leaderboard:
        await interaction.followup.send("На этом сервере еще нет статистики для составления топа.")
        return
        
    sorted_leaderboard = sorted(leaderboard, key=lambda x: x['plays'], reverse=True)[:10]

    embed = discord.Embed(title=f"🏆 Топ слушателей сервера {interaction.guild.name}", color=0xf1c40f)
    
    description_lines = []
    for i, entry in enumerate(sorted_leaderboard):
        user = interaction.guild.get_member(entry['user_id'])
        user_mention = user.mention if user else f"ID: {entry['user_id']}"
        description_lines.append(f"{i+1}. {user_mention} - **{entry['plays']}** прослушиваний")

    embed.description = "\n".join(description_lines)
    await interaction.followup.send(embed=embed)



@bot.command(aliases=['p'])
async def play(ctx: commands.Context, *, query: str):
    async with ctx.typing():
        await enqueue_and_play(ctx, query)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    print(f"Error in command {ctx.command}: {error}")
    traceback.print_exc()
    await ctx.send(f"Произошла ошибка: {error}")

if __name__ == '__main__':
    if TOKEN == 'YOUR_TOKEN_HERE' or not TOKEN:
        print('Please set the DISCORD_TOKEN environment variable.')
    else:
        bot.run(TOKEN)






