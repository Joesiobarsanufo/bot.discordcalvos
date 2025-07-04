import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os # Importa o módulo os para ler variáveis de ambiente

# --- Configurações Iniciais ---
# O bot agora vai buscar o token de uma variável de ambiente chamada DISCORD_BOT_TOKEN
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Verificação simples para garantir que o token foi carregado
if TOKEN is None:
    print("ERRO: O token do bot não foi encontrado nas variáveis de ambiente.")
    print("Certifique-se de que a variável de ambiente 'DISCORD_BOT_TOKEN' está definida.")
    exit(1) # Sai do programa se o token não for encontrado

# Configura o bot para responder a comandos que começam com '!'
intents = discord.Intents.default()
intents.message_content = True # Precisamos disso para o bot ler o conteúdo das mensagens
intents.voice_states = True    # Precisamos disso para o bot gerenciar estados de voz

bot = commands.Bot(command_prefix='!', intents=intents)

# --- Fila de Músicas ---
# Usaremos um dicionário para armazenar a fila de músicas para cada servidor
# Ex: { id_servidor: [url_musica1, url_musica2, ...], ... }
queues = {}

# --- Configuração do yt-dlp ---
# Configurações para baixar apenas o áudio e com a melhor qualidade disponível
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True, # Não mostra mensagens de status no console
    'extract_flat': 'in_playlist' # Para lidar melhor com playlists, se for o caso
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
        # Pega a próxima música da fila
        url = queues[guild_id][0]
        
        try:
            # Extrai a URL direta do stream de áudio do YouTube
            with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
                info = ydl.extract_info(url, download=False)
                audio_url = info['url'] # URL direta do áudio
            
            # Toca a música no canal de voz
            # No Linux, 'ffmpeg' já deve estar no PATH se você instalou com apt
            ctx.voice_client.play(discord.FFmpegPCMAudio(audio_url, executable='ffmpeg'), 
                                   after=lambda e: bot.loop.call_soon_threadsafe(
                                       asyncio.create_task, play_next_song(ctx)))
            
            await ctx.send(f'Tocando agora: **{info.get("title", "Música sem título")}**')
        except Exception as e:
            await ctx.send(f'Deu um erro ao tentar tocar a música: {e}')
            queues[guild_id].pop(0) # Remove a música com erro da fila
            await play_next_song(ctx) # Tenta tocar a próxima
    else:
        # Se não há mais músicas na fila, o bot sai do canal de voz
        await ctx.send("Fila vazia. Saindo do canal de voz em breve.")
        await asyncio.sleep(60) # Espera 1 minuto antes de sair, caso alguém adicione algo
        if not (guild_id in queues and queues[guild_id]): # Verifica de novo pra ter certeza
            await ctx.voice_client.disconnect()
            queues.pop(guild_id, None) # Limpa a fila do servidor

# --- Comando: !play <URL> ---
@bot.command(name='play', help='Toca uma música do YouTube (coloque a URL).')
async def play(ctx, url: str):
    # Verifica se o usuário está em um canal de voz
    if not ctx.author.voice:
        return await ctx.send("Você precisa estar em um canal de voz para usar este comando!")

    voice_channel = ctx.author.voice.channel
    guild_id = ctx.guild.id

    # Conecta ao canal de voz, se ainda não estiver conectado
    if not ctx.voice_client:
        await voice_channel.connect()
    elif ctx.voice_client.channel != voice_channel:
        # Se o bot está em outro canal, move para o canal do usuário
        await ctx.voice_client.move_to(voice_channel)

    # Adiciona a música à fila
    if guild_id not in queues:
        queues[guild_id] = []
    queues[guild_id].append(url)
    
    await ctx.send(f'**{url}** adicionada à fila!')

    # Se não houver música tocando, começa a tocar
    if not ctx.voice_client.is_playing():
        await play_next_song(ctx)

# --- Comando: !skip ---
@bot.command(name='skip', help='Pula a música atual.')
async def skip(ctx):
    guild_id = ctx.guild.id
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop() # Isso vai disparar o `after` e chamar `play_next_song`
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
            del queues[guild_id] # Limpa a fila do servidor
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
        # ESTA É A LINHA QUE FOI CORRIGIDA (Indentação)
        await ctx.send("A fila de músicas está vazia.")


# --- Inicia o Bot ---
bot.run(TOKEN)
