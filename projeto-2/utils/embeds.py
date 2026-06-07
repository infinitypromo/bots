import discord
from typing import List, Optional
from ..config import FUSO_HORARIO, IMAGENS_JOGOS
import pytz

def criar_embed_partida(
    titulo: str,
    jogo: str,
    modo: str,
    max_jogadores: int,
    jogadores: List[discord.Member],
    horario: Optional[discord.utils.utcnow] = None,
    iniciada: bool = False,
    cancelada: bool = False,
    times: Optional[dict] = None,
    descricao: Optional[str] = None,
) -> discord.Embed:
    """
    Cria um embed para uma partida.
    :param titulo: Título do embed (geralmente "Partida de {jogo}")
    :param jogo: Nome do jogo
    :param modo: Modo da partida (1time, 2times, 3times)
    :param max_jogadores: Número máximo de jogadores
    :param jogadores: Lista de membros que estão na partida
    :param horario: Horário agendado (datetime com timezone) ou None
    :param iniciada: Se a partida já começou
    :param cancelada: Se a partida foi cancelada
    :param times: Dicionário com times (se aplicável) ex: {"Time A": [membros], ...}
    :param descricao: Descrição opcional da partida
    :return: discord.Embed
    """
    # Determinar cor baseada no estado
    if cancelada:
        cor = discord.Color.red()
    elif iniciada:
        cor = discord.Color.green()
    else:
        # Azul padrão, amarelo se >=80% cheia
        porcentagem = len(jogadores) / max_jogadores if max_jogadores > 0 else 0
        if porcentagem >= 0.8:
            cor = discord.Color.gold()
        else:
            cor = discord.Color.blue()

    embed = discord.Embed(title=titulo, color=cor)
    if descricao:
        embed.description = descricao

    # Thumbnail do jogo
    thumbnail_url = IMAGENS_JOGOS.get(jogo)
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)

    # Barra de progresso em texto
    vagas = len(jogadores)
    total = max_jogadores
    blocos = 10
    filled = int(blocos * vagas / total) if total > 0 else 0
    barra = "█" * filled + "░" * (blocos - filled)
    embed.add_field(name="Vagas", value=f"[{barra}] {vagas}/{total}", inline=False)

    # Modo
    embed.add_field(name="Modo", value=modo, inline=True)

    # Horário (se houver)
    if horario:
        # Converter para fuso horário configurado
        try:
            tz = pytz.timezone(FUSO_HORARIO)
            horario_local = horario.astimezone(tz)
            horario_str = horario_local.strftime("%d/%m/%Y %H:%M")
        except Exception:
            horario_str = horario.strftime("%d/%m/%Y %H:%M")
        embed.add_field(name="Horário", value=horario_str, inline=True)

        # Countdown (será atualizado dinamicamente pela view)
        embed.add_field(name="Status", value="Aguardando início...", inline=False)
    else:
        embed.add_field(name="Horário", value="Não definido", inline=True)

    # Lista de jogadores (se não houver muitos)
    if jogadores:
        # Limitar a 10 jogadores para não deixar o embed muito grande
        jogadores_txt = ", ".join([j.mention for j in jogadores[:10]])
        if len(jogadores) > 10:
            jogadores_txt += f" e mais {len(jogadores) - 10}"
        embed.add_field(name="Jogadores", value=jogadores_txt, inline=False)

    # Times (se iniciada e times definidos)
    if iniciada and times:
        for time_nome, membros in times.items():
            membros_txt = ", ".join([m.mention for m in membros]) if membros else "Nenhum"
            embed.add_field(name=time_nome, value=membros_txt, inline=False)

    embed.set_footer(text="Use os botões abaixo para interagir.")
    return embed