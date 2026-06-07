import random
from typing import List, Dict
import discord

def sortear_times(jogadores: List[discord.Member], modo: str) -> Dict[str, List[discord.Member]]:
    """
    Sorteia os jogadores em times conforme o modo.
    :param jogadores: Lista de membros que estão na partida.
    :param modo: String indicando o modo: "1time", "2times", "3times".
    :return: Dicionário com nomes dos times como chaves e listas de membros como valores.
    """
    if not jogadores:
        return {}

    # Fazer uma cópia e embaralhar
    embaralhados = jogadores[:]
    random.shuffle(embaralhados)

    times = {}
    if modo == "1time":
        times["Time Único"] = embaralhados
    elif modo == "2times":
        # Dividir em dois times o mais equilibrado possível
        meio = len(embaralhados) // 2
        times["Time A"] = embaralhados[:meio]
        times["Time B"] = embaralhados[meio:]
    elif modo == "3times":
        # Dividir em três times o mais equilibrado possível
        n = len(embaralhados)
        tamanho_base = n // 3
        resto = n % 3
        times["Time A"] = embaralhados[:tamanho_base + (1 if resto > 0 else 0)]
        times["Time B"] = embaralhados[tamanho_base + (1 if resto > 0 else 0):tamanho_base*2 + (1 if resto > 1 else 0)]
        times["Time C"] = embaralhados[tamanho_base*2 + (1 if resto > 1 else 0):]
    else:
        # Fallback: todos em um time
        times["Time Único"] = embaralhados

    return times