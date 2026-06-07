import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
import pytz
import re

# ── Configuração ──────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Armazena partidas ativas: {message_id: MatchData}
partidas: dict[int, "MatchData"] = {}

JOGOS = ["Valorant", "League of Legends", "CS2", "Fortnite", "Rocket League", "Outro"]

# ── Modelo de Partida ─────────────────────────────────────────────────────────
class MatchData:
    def __init__(
        self,
        criador: discord.Member,
        jogo: str,
        max_jogadores: int,
        modo: str,           # "1time" ou "2times"
        canal_voz_id: int,
        horario: datetime | None = None,
    ):
        self.criador = criador
        self.jogo = jogo
        self.max_jogadores = max_jogadores
        self.modo = modo
        self.canal_voz_id = canal_voz_id
        self.horario = horario
        self.jogadores: list[discord.Member] = [criador]
        self.iniciada = False
        self.task: asyncio.Task | None = None
        self.message: discord.Message | None = None

    def esta_cheia(self):
        return len(self.jogadores) >= self.max_jogadores

    def vagas_restantes(self):
        return self.max_jogadores - len(self.jogadores)


# ── Modal de criação ──────────────────────────────────────────────────────────
class CriarPartidaModal(discord.ui.Modal, title="Criar Partida"):
    jogo = discord.ui.TextInput(
        label="Jogo",
        placeholder="Ex: Valorant, CS2, LoL...",
        max_length=40,
    )
    max_jogadores = discord.ui.TextInput(
        label="Número máximo de jogadores",
        placeholder="Ex: 5",
        max_length=2,
    )
    modo = discord.ui.TextInput(
        label="Modo (1time ou 2times)",
        placeholder="1time  →  lista de jogadores\n2times  →  sorteio Time A vs Time B",
        max_length=10,
    )
    canal_voz = discord.ui.TextInput(
        label="ID do canal de voz (ou deixe 0)",
        placeholder="Copie o ID do canal: clique direito → Copiar ID",
        max_length=20,
        required=False,
    )
    horario = discord.ui.TextInput(
        label="Horário (HH:MM) — opcional",
        placeholder="Ex: 21:30  (deixe vazio para iniciar pela lotação)",
        max_length=5,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Valida nº de jogadores
        try:
            n = int(self.max_jogadores.value.strip())
            if not (2 <= n <= 20):
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ Número de jogadores inválido. Use um valor entre 2 e 20.",
                ephemeral=True,
            )
            return

        # Valida modo
        modo_raw = self.modo.value.strip().lower().replace(" ", "")
        if modo_raw not in ("1time", "2times"):
            await interaction.response.send_message(
                "❌ Modo inválido. Use **1time** ou **2times**.",
                ephemeral=True,
            )
            return

        # Valida canal de voz
        canal_voz_id = 0
        cv_raw = self.canal_voz.value.strip() if self.canal_voz.value else ""
        if cv_raw and cv_raw != "0":
            try:
                canal_voz_id = int(cv_raw)
            except ValueError:
                await interaction.response.send_message(
                    "❌ ID do canal de voz inválido.",
                    ephemeral=True,
                )
                return

        # Valida horário
        horario_dt = None
        if self.horario.value.strip():
            match = re.match(r"^(\d{1,2}):(\d{2})$", self.horario.value.strip())
            if not match:
                await interaction.response.send_message(
                    "❌ Formato de horário inválido. Use HH:MM (ex: 21:30).",
                    ephemeral=True,
                )
                return
            h, m = int(match.group(1)), int(match.group(2))
            agora = datetime.now()
            horario_dt = agora.replace(hour=h, minute=m, second=0, microsecond=0)
            if horario_dt <= agora:
                horario_dt += timedelta(days=1)

        partida = MatchData(
            criador=interaction.user,
            jogo=self.jogo.value.strip(),
            max_jogadores=n,
            modo=modo_raw,
            canal_voz_id=canal_voz_id,
            horario=horario_dt,
        )

        await interaction.response.defer()
        embed, view = build_embed_and_view(partida)
        msg = await interaction.followup.send(embed=embed, view=view)
        partida.message = msg
        partidas[msg.id] = partida

        # Agenda início por horário
        if horario_dt:
            partida.task = asyncio.create_task(aguardar_horario(msg.id, horario_dt))


# ── Helpers de embed ──────────────────────────────────────────────────────────
def build_embed_and_view(partida: MatchData):
    modo_label = "1 time" if partida.modo == "1time" else "Time A vs Time B"
    vagas = partida.vagas_restantes()
    nomes = "\n".join(f"• {j.display_name}" for j in partida.jogadores) or "—"

    if partida.horario:
        inicio_txt = f"⏰ Inicia às **{partida.horario.strftime('%H:%M')}** ou ao completar vagas"
    else:
        inicio_txt = f"⚡ Inicia automaticamente ao completar **{partida.max_jogadores}** jogadores"

    embed = discord.Embed(
        title=f"🎮  {partida.jogo}",
        description=inicio_txt,
        color=0x5865F2,
    )
    embed.add_field(name="Modo", value=modo_label, inline=True)
    embed.add_field(
        name="Vagas",
        value=f"{len(partida.jogadores)}/{partida.max_jogadores}",
        inline=True,
    )
    embed.add_field(name="Jogadores", value=nomes, inline=False)
    embed.set_footer(text=f"Criado por {partida.criador.display_name}")
    return embed, PartidaView(partida)


async def atualizar_embed(partida: MatchData):
    if not partida.message:
        return
    embed, view = build_embed_and_view(partida)
    await partida.message.edit(embed=embed, view=view)


# ── View com botões ───────────────────────────────────────────────────────────
class PartidaView(discord.ui.View):
    def __init__(self, partida: MatchData):
        super().__init__(timeout=None)
        self.partida = partida

    def _get_partida(self, message_id: int) -> MatchData | None:
        return partidas.get(message_id)

    @discord.ui.button(label="✅ Entrar", style=discord.ButtonStyle.success, custom_id="entrar")
    async def entrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._get_partida(interaction.message.id)
        if not p or p.iniciada:
            await interaction.response.send_message("❌ Partida não disponível.", ephemeral=True)
            return
        if interaction.user in p.jogadores:
            await interaction.response.send_message("⚠️ Você já está na partida.", ephemeral=True)
            return
        if p.esta_cheia():
            await interaction.response.send_message("❌ Partida cheia.", ephemeral=True)
            return
        p.jogadores.append(interaction.user)
        await interaction.response.defer()
        await atualizar_embed(p)
        if p.esta_cheia():
            await iniciar_partida(interaction.message.id)

    @discord.ui.button(label="❌ Sair", style=discord.ButtonStyle.secondary, custom_id="sair")
    async def sair(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._get_partida(interaction.message.id)
        if not p or p.iniciada:
            await interaction.response.send_message("❌ Partida não disponível.", ephemeral=True)
            return
        if interaction.user not in p.jogadores:
            await interaction.response.send_message("⚠️ Você não está na partida.", ephemeral=True)
            return
        if interaction.user == p.criador:
            await interaction.response.send_message(
                "⚠️ O criador não pode sair. Use 🗑 Cancelar para encerrar a partida.", ephemeral=True
            )
            return
        p.jogadores.remove(interaction.user)
        await interaction.response.defer()
        await atualizar_embed(p)

    @discord.ui.button(label="🗑 Cancelar", style=discord.ButtonStyle.danger, custom_id="cancelar")
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._get_partida(interaction.message.id)
        if not p:
            await interaction.response.send_message("❌ Partida não encontrada.", ephemeral=True)
            return
        if interaction.user != p.criador and not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ Apenas o criador pode cancelar.", ephemeral=True)
            return
        if p.task:
            p.task.cancel()
        del partidas[interaction.message.id]
        embed = discord.Embed(
            title=f"🚫  {p.jogo} — Cancelada",
            description=f"Partida cancelada por {interaction.user.mention}.",
            color=0xED4245,
        )
        await interaction.response.edit_message(embed=embed, view=None)


# ── Início da partida ─────────────────────────────────────────────────────────
async def iniciar_partida(message_id: int):
    p = partidas.get(message_id)
    if not p or p.iniciada:
        return
    p.iniciada = True
    if p.task:
        p.task.cancel()

    canal = p.message.channel

    # Monta times
    import random
    jogadores = p.jogadores.copy()
    random.shuffle(jogadores)

    if p.modo == "1time":
        times_txt = "\n".join(f"• {j.mention}" for j in jogadores)
        title = f"🎮  {p.jogo} — Partida Iniciada!"
        desc = f"**Jogadores ({len(jogadores)}):**\n{times_txt}"
    else:
        meio = len(jogadores) // 2
        time_a = jogadores[:meio]
        time_b = jogadores[meio:]
        ta = "\n".join(f"• {j.mention}" for j in time_a)
        tb = "\n".join(f"• {j.mention}" for j in time_b)
        title = f"🎮  {p.jogo} — Partida Iniciada!"
        desc = f"**🔵 Time A:**\n{ta}\n\n**🔴 Time B:**\n{tb}"

    # Link do canal de voz
    voz_txt = ""
    if p.canal_voz_id:
        voz_txt = f"\n\n🔊 **Canal de voz:** <#{p.canal_voz_id}>"
    else:
        # Tenta pegar qualquer canal de voz do servidor
        guild = p.message.guild
        vc = next((c for c in guild.voice_channels if c.permissions_for(guild.me).connect), None)
        if vc:
            voz_txt = f"\n\n🔊 **Canal de voz:** <#{vc.id}>"

    embed = discord.Embed(title=title, description=desc + voz_txt, color=0x57F287)
    embed.set_footer(text=f"Criado por {p.criador.display_name}")

    # Edita o embed original e menciona todos
    await p.message.edit(embed=embed, view=None)

    mencoes = " ".join(j.mention for j in jogadores)
    await canal.send(f"🚀 A partida de **{p.jogo}** começou! {mencoes}{voz_txt}")

    del partidas[message_id]


async def aguardar_horario(message_id: int, horario: datetime):
    agora = datetime.now()
    espera = (horario - agora).total_seconds()
    if espera > 0:
        await asyncio.sleep(espera)
    await iniciar_partida(message_id)


# ── Comando slash ─────────────────────────────────────────────────────────────
@bot.tree.command(name="partida", description="Cria uma partida e convida jogadores")
async def partida_cmd(interaction: discord.Interaction):
    await interaction.response.send_modal(CriarPartidaModal())


# ── Eventos ───────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot online como {bot.user} — comandos sincronizados.")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ Defina a variável de ambiente DISCORD_TOKEN antes de rodar o bot.")
    else:
        bot.run(token)
