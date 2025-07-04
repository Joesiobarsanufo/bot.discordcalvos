import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os

# --- Configurações Iniciais ---
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

if TOKEN is None:
    print("ERRO: O token do bot não foi encontrado nas variáveis de ambiente.")
    print("Certifique-se de que a variável de ambiente 'DISCORD_BOT_TOKEN' está definida.")
    exit(1)

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
    
    # --- Sincroniza os comandos de barra ---
    try:
        synced = await bot.tree.sync() # Sincroniza comandos globais
        # Ou, para sincronizar em um servidor específico para testes mais rápidos:
        # synced = await bot.tree.sync(guild=discord.Object(id=ID_DO_SEU_SERVIDOR))
        print(f"Sincronizados {len(synced)} comandos de barra.")
    except Exception as e:
        print(f"Erro ao sincronizar comandos de barra: {e}")


# --- Função Auxiliar para Tocar Música ---
async def play_next_song(ctx_or_interaction):
    # Detecta se é um Context (comando de prefixo) ou uma Interaction (comando de barra)
    if isinstance(ctx_or_interaction, commands.Context):
        guild_id = ctx_or_interaction.guild.id
        send_func = ctx_or_interaction.send
        voice_client = ctx_or_interaction.voice_client
    else: # É uma Interaction
        guild_id = ctx_or_interaction.guild_id
        async def interaction_send(msg):
            try:
                await ctx_or_interaction.followup.send(msg)
            except discord.errors.InteractionResponded:
                await ctx_or_interaction.response.send_message(msg)
        send_func = interaction_send
        voice_client = ctx_or_interaction.guild.voice_client

    if guild_id in queues and queues[guild_id]:
        # --- MUDANÇA AQUI: Remove a música da fila ANTES de tentar tocar ---
        url = queues[guild_id].pop(0) # Remove e pega a URL da música
        
        try:
            with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
                info = ydl.extract_info(url, download=False)
                audio_url = info['url']
            
            voice_client.play(discord.FFmpegPCMAudio(audio_url, executable='ffmpeg'), 
                                   after=lambda e: bot.loop.call_soon_threadsafe(
                                       asyncio.create_task, play_next_song(ctx_or_interaction)))
            
            await send_func(f'Tocando agora: **{info.get("title", "Música sem título")}**')
        except Exception as e:
            await send_func(f'Deu um erro ao tentar tocar a música: {e}')
            # Se der erro, a música já foi removida, então só tenta a próxima
            await play_next_song(ctx_or_interaction) # Tenta tocar a próxima
    else:
        await send_func("Fila vazia. Saindo do canal de voz em breve.")
        await asyncio.sleep(60)
        if not (guild_id in queues and queues[guild_id]):
            if voice_client:
                await voice_client.disconnect()
            queues.pop(guild_id, None)

# --- Comando de Prefixo: !play <URL> ---
@bot.command(name='play', help='Toca uma música do YouTube (coloque a URL).')
async def play_prefix(ctx, url: str):
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

# --- Comando de Barra (Slash Command): /play <URL> ---
@bot.tree.command(name='play', description='Toca uma música do YouTube.')
@discord.app_commands.describe(url='URL da música do YouTube.')
async def play_slash(interaction: discord.Interaction, url: str):
    await interaction.response.send_message(f"Adicionando {url} à fila...")

    if not interaction.user.voice:
        return await interaction.followup.send("Você precisa estar em um canal de voz para usar este comando!")

    voice_channel = interaction.user.voice.channel
    guild_id = interaction.guild_id

    if not interaction.guild.voice_client:
        await voice_channel.connect()
    elif interaction.guild.voice_client.channel != voice_channel:
        await interaction.guild.voice_client.move_to(voice_channel)

    if guild_id not in queues:
        queues[guild_id] = []
    queues[guild_id].append(url)
    
    if not interaction.guild.voice_client.is_playing():
        await play_next_song(interaction)
    else:
        await interaction.followup.send(f'**{url}** foi adicionada à fila!')


# --- Comando de Prefixo: !skip ---
@bot.command(name='skip', help='Pula a música atual.')
async def skip_prefix(ctx):
    guild_id = ctx.guild.id
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop() # Isso vai disparar o `after` e chamar `play_next_song`
        await ctx.send("Música pulada!")
    else:
        await ctx.send("Nenhuma música tocando para pular.")

# --- Comando de Barra: /skip ---
@bot.tree.command(name='skip', description='Pula a música atual.')
async def skip_slash(interaction: discord.Interaction):
    await interaction.response.send_message("Tentando pular a música...")
    guild_id = interaction.guild_id
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.stop()
        await interaction.followup.send("Música pulada!")
    else:
        await interaction.followup.send("Nenhuma música tocando para pular.")


# --- Comando de Prefixo: !stop ---
@bot.command(name='stop', help='Para a música e desconecta o bot.')
async def stop_prefix(ctx):
    guild_id = ctx.guild.id
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.voice_client.disconnect()
        if guild_id in queues:
            del queues[guild_id]
        await ctx.send("Música parada e bot desconectado!")
    else:
        await ctx.send("O bot não está conectado a um canal de voz.")

# --- Comando de Barra: /stop ---
@bot.tree.command(name='stop', description='Para a música e desconecta o bot.')
async def stop_slash(interaction: discord.Interaction):
    await interaction.response.send_message("Parando a música e desconectando...")
    guild_id = interaction.guild_id
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        await interaction.guild.voice_client.disconnect()
        if guild_id in queues:
            del queues[guild_id]
        await interaction.followup.send("Música parada e bot desconectado!")
    else:
        await interaction.followup.send("O bot não está conectado a um canal de voz.")


# --- Comando de Prefixo: !queue ---
@bot.command(name='queue', help='Mostra as músicas na fila.')
async def show_queue_prefix(ctx):
    guild_id = ctx.guild.id
    if guild_id in queues and queues[guild_id]:
        queue_list = "\n".join([f"{i+1}. {song}" for i, song in enumerate(queues[guild_id])])
        await ctx.send(f"**Fila de Músicas:**\n{queue_list}")
    else:
        await ctx.send("A fila de músicas está vazia.")

# --- Comando de Barra: /queue ---
@bot.tree.command(name='queue', description='Mostra as músicas na fila.')
async def show_queue_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    guild_id = interaction.guild_id
    if guild_id in queues and queues[guild_id]:
        queue_list = "\n".join([f"{i+1}. {song}" for i, song in enumerate(queues[guild_id])])
        await interaction.followup.send(f"**Fila de Músicas:**\n{queue_list}")
    else:
        await interaction.followup.send("A fila de músicas está vazia.")


# --- Inicia o Bot ---
bot.run(TOKEN)
