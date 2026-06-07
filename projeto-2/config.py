import os

# Secrets from Replit
DISCORD_TOKEN: str = os.environ["DISCORD_TOKEN"]  # obrigatório — definir em Secrets

# Configurações gerais
FUSO_HORARIO: str = "America/Sao_Paulo"
MAX_JOGADORES: int = 20
MIN_JOGADORES: int = 2
MAX_PARTIDAS_POR_USUARIO: int = 1
TEMPO_ARQUIVAR_THREADS_H: int = 2
COUNTDOWN_INTERVAL_S: int = 60
KEEP_ALIVE_PORT: int = int(os.getenv("REPLIT_KEEP_ALIVE_PORT", "8080"))

# Mapeamento de imagens para jogos (thumbnail do embed)
IMAGENS_JOGOS: dict = {
    "Valorant": "https://static.wikia.nocookie.net/valorant/images/6/66/Valorant_logo_-_red.png",
    "League of Legends": "https://static.wikia.nocookie.net/leagueoflegends/images/9/93/LoL_icon.png",
    "CS2": "https://cdn.cloudflare.steamstatic.com/apps/730/capsule_231x87.jpg",
    "Fortnite": "https://cdn2.unrealengine.com/fortnite-fn-logo-400x400-400x400-294204892.png",
    "Rocket League": "https://cdn.cloudflare.steamstatic.com/apps/252950/capsule_231x87.jpg",
}