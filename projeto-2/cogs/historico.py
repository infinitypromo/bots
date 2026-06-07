import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List
import logging
from ..utils.db import get_json, set_json

logger = logging.getLogger(__name__)

class Historico(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="historico", description="Mostra o histórico de partidas de um usuário (ou do próprio autor)")
    async def historico(self, interaction: discord.Interaction, usuario: Optional[discord.Member] = None):
        await interaction.response.defer(ephemeral=False)
        guild_id = interaction.guild.id
        if usuario is None:
            usuario = interaction.user
        historico_key = f"historico:{guild_id}"
        historico = get_json(historico_key) or []
        # Filtrar partidas do usuário
        partidas_usuario = [p for p in historico if usuario.id in p.get("jogadores_ids", [])]
        # Pegar as últimas 5
        ultimas = partidas_usuario[-5:][::-1]  # mais recente primeiro
        if not ultimas:
            await interaction.followup.send(f"{usuario.mention} não tem partidas no histórico.", ephemeral=False)
            return
        embeds = []
        for partida in ultimas:
            jogo = partida.get("jogo", "Desconhecido")
            modo = partida.get("modo", "Desconhecido")
            timestamp_inicio = partida.get("timestamp_inicio")
            if timestamp_inicio:
                try:
                    dt = discord.utils.parse_time(timestamp_inicio)
                except:
                    dt = None
                data_str = discord.utils.format_dt(dt, style="f") if dt else timestamp_inicio
            else:
                data_str = "Data não disponível"
            # Contagem de jogadores
            num_jogadores = len(partida.get("jogadores_ids", []))
            embed = discord.Embed(
                title=f"Partida de {jogo}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Modo", value=modo, inline=True)
            embed.add_field(name="Jogadores", value=f"{num_jogadores} jogadores", inline=True)
            embed.add_field(name="Data de início", value=data_str, inline=False)
            # Se houver times, mostrar
            times = partida.get("times")
            if times:
                for time_nome, ids in times.items():
                    embed.add_field(name=time_nome, value=f"{len(ids)} jogadores", inline=True)
            embeds.append(embed)
        # Se houver múltiplos embeds, podemos enviar como uma lista ou usar paginação simples.
        # Por simplicidade, vamos enviar apenas o primeiro embed e mencionar que há mais.
        # Mas o requisito é mostrar as últimas 5, então vamos enviar todos em uma única mensagem?
        # Discord limita embeds por mensagem a 10, então podemos enviar até 5.
        await interaction.followup.send(embeds=embeds)

    @app_commands.command(name="stats", description="Mostra estatísticas de um usuário (ou do próprio autor)")
    async def stats(self, interaction: discord.Interaction, usuario: Optional[discord.Member] = None):
        await interaction.response.defer(ephemeral=False)
        guild_id = interaction.guild.id
        if usuario is None:
            usuario = interaction.user
        historico_key = f"historico:{guild_id}"
        historico = get_json(historico_key) or []
        partidas_usuario = [p for p in historico if usuario.id in p.get("jogadores_ids", [])]
        if not partidas_usuario:
            await interaction.followup.send(f"{usuario.mention} não tem partidas no histórico.", ephemeral=False)
            return
        total_partidas = len(partidas_usuario)
        # Jogo favorito: o que aparece mais vezes
        jogos = [p.get("jogo") for p in partidas_usuario if p.get("jogo")]
        jogo_favorito = max(set(jogos), key=jogos.count) if jogos else "Nenhum"
        # Horário mais ativo: analisar a hora do dia das partidas
        horas = []
        for p in partidas_usuario:
            timestamp_inicio = p.get("timestamp_inicio")
            if timestamp_inicio:
                try:
                    dt = discord.utils.parse_time(timestamp_inicio)
                    if dt:
                        horas.append(dt.hour)
                except:
                    pass
        if horas:
            hora_mais_ativa = max(set(horas), key=horas.count)
            horario_str = f"{hora_mais_ativa:02d}:00"
        else:
            horario_str = "Não disponível"
        embed = discord.Embed(
            title=f"Estatísticas de {usuario.display_name}",
            color=discord.Color.gold()
        )
        embed.add_field(name="Total de partidas", value=str(total_partidas), inline=True)
        embed.add_field(name="Jogo favorito", value=jogo_favorito, inline=True)
        embed.add_field(name="Horário mais ativo", value=horario_str, inline=False)
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Historico(bot))