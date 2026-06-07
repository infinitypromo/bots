from datetime import datetime
import pytz
from typing import List, Optional, Union
from discord import Member, VoiceState

# We'll define the MatchData class here.
# Note: We are using Python 3.10, so we use Union and Optional from typing.

class MatchData:
    def __init__(
        self,
        criador: Member,
        jogo: str,
        max_jogadores: int,
        modo: str,  # "1time", "2times", "3times"
        canal_voz_id: Optional[int] = None,
        horario: Optional[datetime] = None,
        descricao: Optional[str] = None,
    ):
        self.criador: Member = criador
        self.jogo: str = jogo
        self.max_jogadores: int = max_jogadores
        self.modo: str = modo
        self.canal_voz_id: Optional[int] = canal_voz_id
        self.horario: Optional[datetime] = horario  # stored as timezone-aware datetime
        self.descricao: Optional[str] = descricao
        self.jogadores: List[Member] = [criador]
        self.iniciada: bool = False
        self.task: Optional[object] = None  # asyncio.Task for countdown
        self.message: Optional[object] = None  # discord.Message

    def esta_cheia(self) -> bool:
        return len(self.jogadores) >= self.max_jogadores

    def vagas_restantes(self) -> int:
        return self.max_jogadores - len(self.jogadores)

    def adicionar_jogador(self, jogador: Member) -> bool:
        if self.esta_cheia() or self.iniciada:
            return False
        self.jogadores.append(jogador)
        return True

    def remover_jogador(self, jogador: Member) -> bool:
        if jogador in self.jogadores and not self.iniciada:
            self.jogadores.remove(jogador)
            return True
        return False