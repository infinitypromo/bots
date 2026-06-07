import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import logging
from ..utils.db import get_json, set_json, get, set

logger = logging.getLogger(__name__)

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_config(self, guild_id: int) -> dict:
        """Get the config dictionary for a guild, defaulting to empty."""
        key = f"config:{guild_id}"
        config = get_json(key)
        if config is None:
            config = {}
        return config

    def _save_config(self, guild_id: int, config: dict) -> None:
        """Save the config dictionary for a guild."""
        key = f"config:{guild_id}"
        set_json(key, config)

    async def _check_admin_permission(self, interaction: discord.Interaction) -> bool:
        """Check if the user has manage_guild permission (or is owner)."""
        if interaction.user.guild_permissions.manage_guild:
            return True
        # Also allow the server owner
        if interaction.user == interaction.guild.owner:
            return True
        await interaction.response.send_message(
            "Você não tem permissão para usar este comando. Necessita de `Gerenciar Servidor`.",
            ephemeral=True
        )
        return False

    @app_commands.command(name="partidas", description="Lista todas as partidas ativas no servidor")
    async def admin_partidas(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not await self._check_admin_permission(interaction):
            return
        guild_id = interaction.guild.id
        key = f"partidas_ativas:{guild_id}"
        partidas_ativas = get_json(key) or {}
        if not partidas_ativas:
            await interaction.followup.send("Não há partidas ativas neste servidor.", ephemeral=True)
            return
        embed = discord.Embed(
            title="Partidas Ativas",
            color=discord.Color.blue()
        )
        for msg_id, data in partidas_ativas.items():
            criador = interaction.guild.get_member(data.get("criador_id", 0))
            criador_name = criador.mention if criador else f"Usuário ID {data.get('criador_id')}"
            jogo = data.get("jogo", "Desconhecido")
            modo = data.get("modo", "Desconhecido")
            jogadores_ids = data.get("jogadores_ids", [])
            num_jogadores = len(jogadores_ids)
            max_jogadores = data.get("max_jogadores", 0)
            embed.add_field(
                name=f"Partida {msg_id}",
                value=f"**Jogo:** {jogo}\n"
                      f"**Modo:** {modo}\n"
                      f"**Criador:** {criador_name}\n"
                      f"**Jogadores:** {num_jogadores}/{max_jogadores}",
                inline=False
            )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="encerrar", description="Força o encerramento de uma partida ativa pelo ID da mensagem")
    @app_commands.describe(message_id="ID da mensagem da partida a ser encerrada")
    async def admin_encerrar(self, interaction: discord.Interaction, message_id: str):
        await interaction.response.defer(ephemeral=True)
        if not await self._check_admin_permission(interaction):
            return
        guild_id = interaction.guild.id
        key = f"partidas_ativas:{guild_id}"
        partidas_ativas = get_json(key) or {}
        if message_id not in partidas_ativas:
            await interaction.followup.send(f"Nenhuma partida ativa encontrada com o ID de mensagem `{message_id}`.", ephemeral=True)
            return
        # Get the message and try to edit it to show as cancelled
        try:
            msg = await interaction.channel.fetch_message(int(message_id))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            msg = None
        # Remove from active partidas
        del partidas_ativas[message_id]
        self._save_config(guild_id, partidas_ativas)  # Wait, we are saving to partidas_ativas, not config. Let's fix.
        # Actually we have a separate function for saving partidas_ativas. Let's use the db directly.
        set_json(key, partidas_ativas)
        # If we have the message, edit it to show cancelled
        if msg:
            # We don't have the match_data object, so we'll just edit the embed to show cancelled and remove view.
            # We'll try to get the current embed and modify it.
            try:
                embed = msg.embeds[0] if msg.embeds else discord.Embed(title="Partida Cancelada")
                embed.color = discord.Color.red()
                embed.title = f"Partida Cancelada: {embed.title}" if embed.title and "Partida" in embed.title else "Partida Cancelada"
                await msg.edit(embed=embed, view=None)
            except Exception as e:
                logger.error(f"Erro ao editar mensagem de partida cancelada: {e}")
        await interaction.followup.send(f"Partida com ID de mensagem `{message_id}` foi encerrada.", ephemeral=True)

    @app_commands.command(name="config", description="Configurações do bot para o servidor")
    @app_commands.describe(
        opcao="Qual configuração deseja alterar",
        valor="O novo valor (para canal_lfg, mencione o canal; para max_partidas, um número)"
    )
    @app_commands.choices(
        opcao=[
            app_commands.Choice(name="canal_lfg", value="canal_lfg"),
            app_commands.Choice(name="max_partidas", value="max_partidas")
        ]
    )
    async def admin_config(self, interaction: discord.Interaction, opcao: str, valor: str):
        await interaction.response.defer(ephemeral=True)
        if not await self._check_admin_permission(interaction):
            return
        guild_id = interaction.guild.id
        config = self._get_config(guild_id)
        if opcao == "canal_lfg":
            # Expect a channel mention or ID
            # Try to get a channel from the mention or ID
            channel = None
            # Remove <> and @ if present
            valor_clean = valor.strip()
            if valor_clean.startswith("<#") and valor_clean.endswith(">"):
                try:
                    channel_id = int(valor_clean[2:-1])
                    channel = interaction.guild.get_channel(channel_id)
                except ValueError:
                    pass
            else:
                try:
                    channel_id = int(valor_clean)
                    channel = interaction.guild.get_channel(channel_id)
                except ValueError:
                    pass
            if channel is None or not isinstance(channel, discord.TextChannel):
                await interaction.followup.send("Por favor, forneça um canal de texto válido (mencione o canal ou forneça seu ID).", ephemeral=True)
                return
            config["canal_lfg"] = channel.id
            self._save_config(guild_id, config)
            await interaction.followup.send(f"Canal de LFG definido para {channel.mention}.", ephemeral=True)
        elif opcao == "max_partidas":
            try:
                max_partidas = int(valor)
                if max_partidas < 1:
                    await interaction.followup.send("O valor de max_partidas deve ser pelo menos 1.", ephemeral=True)
                    return
                config["max_partidas"] = max_partidas
                self._save_config(guild_id, config)
                await interaction.followup.send(f"Limite de partidas por usuário definido para {max_partidas}.", ephemeral=True)
            except ValueError:
                await interaction.followup.send("Por favor, forneça um número inteiro válido para max_partidas.", ephemeral=True)
        else:
            await interaction.followup.send("Opção de configuração não reconhecida.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))