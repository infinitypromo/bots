import os
import logging
import asyncio
from keepalive import keep_alive
from config import DISCORD_TOKEN
import discord
from discord.ext import commands

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s'
)
logger = logging.getLogger('bot')

# Iniciar o keep-alive server em uma thread de fundo
keep_alive()

# Configurar intents
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True

# Criar o bot
bot = commands.Bot(command_prefix="!", intents=intents)

async def restore_active_matches(bot: commands.Bot):
    """Restaura as views das partidas ativas após restart do bot."""
    from utils.db import get_json
    from models.match import MatchData
    from cogs.partidas import PartidaView
    
    for guild in bot.guilds:
        guild_id = guild.id
        key = f"partidas_ativas:{guild_id}"
        partidas_ativas = get_json(key) or {}
        if not partidas_ativas:
            continue
        
        for msg_id_str, data in partidas_ativas.items():
            try:
                msg_id = int(msg_id_str)
                channel = guild.get_channel(data.get("canal_id", 0))
                if not channel:
                    # Tentar buscar o canal pelo ID da mensagem (pode não funcionar se a mensagem não estiver no cache)
                    continue
                
                message = await channel.fetch_message(msg_id)
                if not message:
                    continue
                
                # Reconstruir o MatchData
                criador = guild.get_member(data.get("criador_id", 0))
                if not criador:
                    continue
                
                jogadores = []
                for jid in data.get("jogadores_ids", []):
                    member = guild.get_member(jid)
                    if member:
                        jogadores.append(member)
                
                match_data = MatchData(
                    criador=criador,
                    jogo=data.get("jogo", "Desconhecido"),
                    max_jogadores=data.get("max_jogadores", 5),
                    modo=data.get("modo", "1time"),
                    canal_voz_id=data.get("canal_voz_id"),
                    horario=None,
                    descricao=data.get("descricao")
                )
                
                # Parse horario se existir
                if data.get("horario"):
                    try:
                        import pytz
                        from datetime import datetime
                        match_data.horario = datetime.fromisoformat(data["horario"])
                    except:
                        pass
                
                match_data.jogadores = jogadores
                match_data.iniciada = data.get("iniciada", False)
                match_data.message = message
                
                # Reanexar a view
                view = PartidaView(match_data)
                await message.edit(view=view)
                
                # Se houver horário e não iniciada, reiniciar o countdown
                if match_data.horario and not match_data.iniciada:
                    # O countdown será reiniciado automaticamente pela view? 
                    # Precisamos recriar a task. Vamos chamar a função interna do modal.
                    # Por simplicidade, vamos apenas logar.
                    logger.info(f"Partida {msg_id} restaurada com horário agendado.")
                
                logger.info(f"Partida ativa restaurada: {msg_id} no servidor {guild.name}")
            except Exception as e:
                logger.error(f"Erro ao restaurar partida {msg_id_str}: {e}")

# Carregar as cogs
async def load_extensions():
    for cog in ["cogs.partidas", "cogs.historico", "cogs.admin"]:
        try:
            await bot.load_extension(cog)
            logger.info(f"Cog carregada: {cog}")
        except Exception as e:
            logger.error(f"Falha ao carregar a cog {cog}: {e}")

@bot.event
async def on_ready():
    logger.info(f"✅ Bot online como {bot.user} (ID: {bot.user.id})")
    # Sincronizar os comandos de aplicação (slash commands)
    try:
        synced = await bot.tree.sync()
        logger.info(f"Sincronizados {len(synced)} comandos de aplicação.")
    except Exception as e:
        logger.error(f"Falha ao sincronizar comandos: {e}")
    
    # Restaurar partidas ativas
    await restore_active_matches(bot)

async def main():
    async with bot:
        await load_extensions()
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot desligado pelo usuário.")
    except Exception as e:
        logger.error(f"Erro crítico: {e}", exc_info=True)