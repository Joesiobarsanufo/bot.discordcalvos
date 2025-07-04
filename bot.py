import discord
from discord.ext import commands
import yt_dlp
import asyncio

# --- Configurações Iniciais ---
# Substitua 'SEU_TOKEN_DO_BOT_AQUI' pelo token que você copiou do Discord Developer Portal
TOKEN = 'MTE1Mjg1MTMxNTU0MjcyMDUzMg.Givjj7._euq6DbXhQu_AO0VN2R6zkKEUGvvDT19Z-gpLk'

# Configura o bot para responder a comandos que começam com '!'
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

# --- Fila de Músicas ---
queues = {}

# --- Configuração do yt-dlp ---
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'extract_flat': 'in_playlist'
}

# --- Evento: Quando o Bot Estiver Online ---
@bot.event
async def on_ready():
    print(f'Bot {bot.user.name} está online!')
    print(f'ID do Bot: {bot.user.id}')
    print(f'Pronto para servir {len(bot.guilds)} servidores!')

# --- Função Auxiliar para Tocar Música ---
async def play_next_song(ctx):
    guild_id = ctx.guild.id
    if guild_id in queues and queues[guild_id]:
        url = queues[guild_id][0]
        try:
            with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
                info = ydl.extract_info(url, download=False)
                audio_url = info['url']

            ctx.voice_client.play(discord.FFmpegPCMAudio(audio_url, executable='ffmpeg'), 
                                   after=lambda e: bot.loop.call_soon_threadsafe(
                                       asyncio.create_task, play_next_song(ctx)))

            await ctx.send(f'Tocando agora: **{info.get("title", "Música sem título")}**')
        except Exception as e:
            await ctx.send(f'Deu um erro ao tentar tocar a música: {e}')
            queues[guild_id].pop(0)
            await play_next_song(ctx)
    else:
        await ctx.send("Fila vazia. Saindo do canal de voz em breve.")
        await asyncio.sleep(60)
        if not (guild_id in queues and queues[guild_id]):
            await ctx.voice_client.disconnect()
            queues.pop(guild_id, None)

# --- Comando: !play <URL> ---
@bot.command(name='play', help='Toca uma música do YouTube (coloque a URL).')
async def play(ctx, url: str):
    if not ctx.author.voice:
        return await ctx.send("Você precisa estar em um canal de voz para usar este comando!")

    voice_channel = ctx.author.voice.channel
    guild_id = ctx.guild.id

    if not ctx.voice_client:
        await voice_channel.connect()
    elif ctx.voice_client.channel != voice_channel:
        await ctx.voice_client.move_to(voice_channel)

    if guild_id not in queues:
        queues[guild_id] = []
    queues[guild_id].append(url)

    await ctx.send(f'**{url}** adicionada à fila!')

    if not ctx.voice_client.is_playing():
        await play_next_song(ctx)

# --- Comando: !skip ---
@bot.command(name='skip', help='Pula a música atual.')
async def skip(ctx):
    guild_id = ctx.guild.id
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Música pulada!")
    else:
        await ctx.send("Nenhuma música tocando para pular.")

# --- Comando: !stop ---
@bot.command(name='stop', help='Para a música e desconecta o bot.')
async def stop(ctx):
    guild_id = ctx.guild.id
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.voice_client.disconnect()
        if guild_id in queues:
            del queues[guild_id]
        await ctx.send("Música parada e bot desconectado!")
    else:
        await ctx.send("O bot não está conectado a um canal de voz.")

# --- Comando: !queue ---
@bot.command(name='queue', help='Mostra as músicas na fila.')
async def show_queue(ctx):
    guild_id = ctx.guild.id
    if guild_id in queues and queues[guild_id]:
        queue_list = "\n".join([f"{i+1}. {song}" for i, song in enumerate(queues[guild_id])])
        await ctx.send(f"**Fila de Músicas:**\n{queue_list}")
    else:
    await ctx.send("A fila de músicas está vazia.")


# --- Inicia o Bot ---
bot.run(TOKEN)