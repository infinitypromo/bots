import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict, List
import asyncio
from datetime import datetime, timedelta
import pytz
import logging

from ..config import FUSO_HORARIO, MAX_JOGADORES, MIN_JOGADORES, MAX_PARTIDAS_POR_USUARIO, KEEP_ALIVE_PORT, TEMPO_ARQUIVAR_THREADS_H, COUNTDOWN_INTERVAL_S
from ..models.match import MatchData
from ..utils.embeds import criar_embed_partida
from ..utils.times import sortear_times
from ..utils.db import get_json, set_json, get, set, delete

logger = logging.getLogger(__name__)

class CriarPartidaModal(discord.ui.Modal, title="Criar Partida"):
    jogo = discord.ui.TextInput(label="Jogo", placeholder="Ex: Valorant, CS2, LoL...", max_length=40)
    max_jogadores = discord.ui.TextInput(label="Número máximo de jogadores", placeholder="Ex: 5", max_length=2)
    modo = discord.ui.TextInput(label="Modo (1time, 2times, 3times)", max_length=10)
    canal_voz = discord.ui.TextInput(label="ID do canal de voz (ou deixe 0)", max_length=20, required=False)
    horario = discord.ui.TextInput(label="Horário (HH:MM) — opcional", max_length=5, required=False)
    descricao = discord.ui.TextInput(label="Descrição (opcional)", style=discord.TextStyle.paragraph, max_length=200, required=False)

    def __init__(self):
        super().__init__()

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Validar entradas
        try:
            max_jog = int(self.max_jogadores.value)
            if max_jog < MIN_JOGADORES or max_jog > MAX_JOGADORES:
                await interaction.followup.send(
                    f"O número de jogadores deve estar entre {MIN_JOGADORES} e {MAX_JOGADORES}.",
                    ephemeral=True
                )
                return
        except ValueError:
            await interaction.followup.send("Número máximo de jogadores deve ser um número inteiro.", ephemeral=True)
            return

        modo_val = self.modo.value.lower()
        if modo_val not in ["1time", "2times", "3times"]:
            await interaction.followup.send("Modo deve ser '1time', '2times' ou '3times'.", ephemeral=True)
            return

        canal_voz_id = None
        if self.canal_voz.value.strip():
            try:
                canal_voz_id = int(self.canal_voz.value)
                if canal_voz_id == 0:
                    canal_voz_id = None
            except ValueError:
                await interaction.followup.send("ID do canal de voz deve ser um número inteiro ou vazio.", ephemeral=True)
                return

        horario_dt = None
        if self.horario.value.strip():
            try:
                # Parse HH:MM and assume today in the configured timezone
                tz = pytz.timezone(FUSO_HORARIO)
                agora = datetime.now(tz)
                hora, minuto = map(int, self.horario.value.split(":"))
                horario_dt = tz.localize(datetime(agora.year, agora.month, agora.day, hora, minuto))
                # Se o horário já passou, agendar para o dia seguinte
                if horario_dt < agora:
                    horario_dt += timedelta(days=1)
            except Exception as e:
                logger.error(f"Erro ao parsear horário: {e}")
                await interaction.followup.send("Formato de horário inválido. Use HH:MM (ex: 21:30).", ephemeral=True)
                return

        # Verificar limite de partidas ativas por usuário
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        
        # Verificar restrição de canal LFG
        config_key = f"config:{guild_id}"
        config = get_json(config_key) or {}
        canal_lfg_id = config.get("canal_lfg")
        if canal_lfg_id and interaction.channel.id != canal_lfg_id:
            canal_lfg = interaction.guild.get_channel(canal_lfg_id)
            canal_mention = canal_lfg.mention if canal_lfg else f"<#{canal_lfg_id}>"
            await interaction.followup.send(
                f"Partidas só podem ser criadas no canal {canal_mention}.",
                ephemeral=True
            )
            return
        
        partidas_ativas_key = f"partidas_ativas:{guild_id}"
        partidas_ativas = get_json(partidas_ativas_key) or {}
        # Contar partidas ativas deste usuário
        count = sum(1 for msg_id, data in partidas_ativas.items() if data.get("criador_id") == user_id)
        # Usar config do servidor ou padrão
        max_partidas_config = config.get("max_partidas", MAX_PARTIDAS_POR_USUARIO)
        if count >= max_partidas_config:
            await interaction.followup.send(
                f"Você já tem o máximo de {max_partidas_config} partida(s) ativa(s).",
                ephemeral=True
            )
            return

        # Criar a partida
        match_data = MatchData(
            criador=interaction.user,
            jogo=self.jogo.value,
            max_jogadores=max_jog,
            modo=modo_val,
            canal_voz_id=canal_voz_id,
            horario=horario_dt,
            descricao=self.descricao.value if self.descricao.value.strip() else None
        )

        # Criar o embed inicial
        embed = criar_embed_partida(
            titulo=f"Partida de {match_data.jogo}",
            jogo=match_data.jogo,
            modo=match_data.modo,
            max_jogadores=match_data.max_jogadores,
            jogadores=match_data.jogadores,
            horario=match_data.horario,
            iniciada=match_data.iniciada,
            cancelada=False,
            descricao=match_data.descricao
        )

        # Criar a view (botões)
        view = PartidaView(match_data)

        # Enviar a mensagem
        try:
            msg = await interaction.followup.send(embed=embed, view=view, wait=True)
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem da partida: {e}")
            await interaction.followup.send("Erro ao criar a partida. Tente novamente.", ephemeral=True)
            return

        # Salvar a partida ativa no Replit DB
        partidas_ativas[str(msg.id)] = {
            "criador_id": match_data.criador.id,
            "jogo": match_data.jogo,
            "max_jogadores": match_data.max_jogadores,
            "modo": match_data.modo,
            "canal_voz_id": match_data.canal_voz_id,
            "horario": match_data.horario.isoformat() if match_data.horario else None,
            "descricao": match_data.descricao,
            "jogadores_ids": [j.id for j in match_data.jogadores],
            "iniciada": match_data.iniciada,
            "message_id": msg.id,
            "canal_id": msg.channel.id
        }
        set_json(partidas_ativas_key, partidas_ativas)

        # Armazenar a referência da mensagem e da task no objeto MatchData
        match_data.message = msg
        # Iniciar o countdown se houver horário
        if match_data.horario:
            match_data.task = asyncio.create_task(self._countdown_task(msg, match_data))

        await interaction.followup.send("Partida criada com sucesso!", ephemeral=True)

    async def _countdown_task(self, message: discord.Message, match_data: MatchData):
        """Task que atualiza o embed com countdown a cada minuto até o horário."""
        try:
            while not match_data.iniciada and not match_data.esta_cheia():
                agora = datetime.now(pytz.timezone(FUSO_HORARIO))
                diff = match_data.horario - agora
                if diff.total_seconds() <= 0:
                    break
                horas, resto = divmod(int(diff.total_seconds()), 3600)
                minutos, segundos = divmod(resto, 60)
                countdown_str = f"Inicia em {horas}h {minutos}m {segundos}s"
                # Atualizar o embed
                embed = criar_embed_partida(
                    titulo=f"Partida de {match_data.jogo}",
                    jogo=match_data.jogo,
                    modo=match_data.modo,
                    max_jogadores=match_data.max_jogadores,
                    jogadores=match_data.jogadores,
                    horario=match_data.horario,
                    iniciada=match_data.iniciada,
                    cancelada=False,
                    descricao=match_data.descricao
                )
                # Substituir o campo de status (assumindo que é o último campo adicionado pelo embed builder?)
                # Instead, we rebuild the embed with a custom field for status.
                # Let's rebuild the embed with a custom status field.
                # We'll create a new embed and then replace the status field.
                # But for simplicity, we'll just update the entire embed with a new one that has the countdown.
                # We'll recreate the embed with the same data but add a countdown field.
                # Actually, the embed builder doesn't have a countdown field by default.
                # We'll modify the embed builder to accept a countdown string? Or we can do it here.
                # Let's do: create the embed as before, then replace the field named "Status" or add one.
                # Since the embed builder already adds a "Status" field when there's a horario? 
                # Looking at the embed builder: it adds a field "Horário" and then a field "Status" with "Aguardando início...".
                # We want to update that status field.
                # We'll do a simpler approach: rebuild the embed with a custom status.
                # We'll create a new embed using the same parameters but then manually set the status field.
                # However, to avoid duplicating the embed builder logic, we'll just update the message with a new embed that we build similarly.
                # Let's create a helper function that builds the embed with a custom status string.
                # For now, we'll just update the entire embed by calling the builder and then replacing the status field.
                # We'll get the current embed, find the status field, and update it.
                # But we don't have the current embed stored. So we'll store the embed in the match_data? Not ideal.
                # Instead, we'll rebuild the embed from scratch with the same data and a custom status.
                # We'll create a temporary embed builder function that takes an optional status string.
                # Since we don't have that, let's do a quick and dirty: we'll create the embed and then edit the field by name.
                # We'll assume the embed has a field named "Status" (if horario exists) and update it.
                # We'll do:
                embed = criar_embed_partida(
                    titulo=f"Partida de {match_data.jogo}",
                    jogo=match_data.jogo,
                    modo=match_data.modo,
                    max_jogadores=match_data.max_jogadores,
                    jogadores=match_data.jogadores,
                    horario=match_data.horario,
                    iniciada=match_data.iniciada,
                    cancelada=False,
                    descricao=match_data.descricao
                )
                # Now, replace the field named "Status" with the countdown string.
                for i, field in enumerate(embed.fields):
                    if field.name == "Status":
                        embed.set_field_at(i, name="Status", value=countdown_str, inline=False)
                        break
                await message.edit(embed=embed)
                # Wait for a minute or until the time is up
                await asyncio.sleep(60)
            # Se sair do loop porque o tempo acabou ou a partida está cheia ou iniciada
            if not match_data.iniciada and match_data.esta_cheia():
                # Iniciar a partida automaticamente quando lotar
                await iniciar_partida(message.id, match_data)
            elif not match_data.iniciada and diff.total_seconds() <= 0:
                # Horário atingido
                await iniciar_partida(message.id, match_data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Erro no countdown task: {e}")

async def iniciar_partida(message_id: int, match_data: MatchData):
    """Inicia a partida: sorteia times, atualiza embed, menciona jogadores, cria threads."""
    try:
        match_data.iniciada = True
        # Cancelar o countdown task se existir
        if match_data.task:
            match_data.task.cancel()

        # Sortear times
        times = sortear_times(match_data.jogadores, match_data.modo)

        # Atualizar o embed para estado iniciada
        embed = criar_embed_partida(
            titulo=f"Partida de {match_data.jogo}",
            jogo=match_data.jogo,
            modo=match_data.modo,
            max_jogadores=match_data.max_jogadores,
            jogadores=match_data.jogadores,
            horario=match_data.horario,
            iniciada=True,
            cancelada=False,
            times=times,
            descricao=match_data.descricao
        )
        await match_data.message.edit(embed=embed, view=None)  # Remove os botões

        # Construir menção dos jogadores e link do canal de voz
        jogadores_mentions = " ".join([j.mention for j in match_data.jogadores])
        canal_voz = match_data.message.guild.get_channel(match_data.canal_voz_id) if match_data.canal_voz_id else None
        if not canal_voz and match_data.criador.voice and match_data.criador.voice.channel:
            canal_voz = match_data.criador.voice.channel
        if not canal_voz:
            # Fallback: primeiro canal de voz acessível
            for c in match_data.message.guild.voice_channels:
                if c.permissions_for(match_data.message.guild.me).connect:
                    canal_voz = c
                    break
        canal_voz_mention = canal_voz.mention if canal_voz else "`nenhum canal de voz`"

        # Enviar mensagem de início no mesmo canal
        inicio_msg = f"🚀 {match_data.jogo} começou! {jogadores_mentions}  🔊 {canal_voz_mention}"
        await match_data.message.channel.send(inicio_msg)

        # Criar threads para cada time (se modo for 2times ou 3times)
        if match_data.modo in ["2times", "3times"] and times:
            for time_nome, membros in times.items():
                if membros:
                    thread_name = f"🔵 {time_nome} — {match_data.jogo}" if time_nome == "Time A" else f"🔴 {time_nome} — {match_data.jogo}"
                    # Criar thread privada (apenas para os membros do time)
                    thread = await match_data.message.channel.create_thread(
                        name=thread_name,
                        type=discord.ChannelType.private_thread,
                        invitable=False
                    )
                    # Adicionar os membros do time à thread
                    for membro in membros:
                        await thread.add_user(membro)
                    # Arquivar após TEMPO_ARQUIVAR_THREADS_H horas (do config)
                    # We'll schedule a task to archive the thread after the delay.
                    async def archive_thread_later(t=thread, delay=TEMPO_ARQUIVAR_THREADS_H*3600):
                        await asyncio.sleep(delay)
                        if not t.archived:
                            await t.archive()
                    asyncio.create_task(archive_thread_later())

        # Atualizar o banco de dados: remover de partidas ativas e adicionar ao histórico
        guild_id = match_data.message.guild.id
        partidas_ativas_key = f"partidas_ativas:{guild_id}"
        partidas_ativas = get_json(partidas_ativas_key) or {}
        if str(message_id) in partidas_ativas:
            del partidas_ativas[str(message_id)]
            set_json(partidas_ativas_key, partidas_ativas)

        # Salvar no histórico
        historico_key = f"historico:{guild_id}"
        historico = get_json(historico_key) or []
        historico.append({
            "jogo": match_data.jogo,
            "modo": match_data.modo,
            "jogadores_ids": [j.id for j in match_data.jogadores],
            "times": {k: [m.id for m in v] for k, v in times.items()} if times else {},
            "timestamp_inicio": datetime.now(pytz.timezone(FUSO_HORARIO)).isoformat(),
            "timestamp_criacao": match_data.message.created_at.isoformat(),
            "duracao_ate_inicio": (match_data.horario - match_data.message.created_at).total_seconds() if match_data.horario else None
        })
        set_json(historico_key, historico)

    except Exception as e:
        logger.error(f"Erro ao iniciar partida: {e}")
        try:
            await match_data.message.channel.send("Erro ao iniciar a partida. Veja os logs para mais detalhes.")
        except:
            pass

class PartidaView(discord.ui.View):
    def __init__(self, match_data: MatchData):
        super().__init__(timeout=None)  # Persistente
        self.match_data = match_data

    @discord.ui.button(label="✅ Entrar", style=discord.ButtonStyle.green, custom_id="entrar_partida")
    async def entrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if self.match_data.iniciada:
            await interaction.followup.send("Esta partida já começou.", ephemeral=True)
            return
        if self.match_data.esta_cheia():
            await interaction.followup.send("Esta partida já está cheia.", ephemeral=True)
            return
        if interaction.user in self.match_data.jogadores:
            await interaction.followup.send("Você já está nesta partida.", ephemeral=True)
            return
        # Adicionar jogador
        if self.match_data.adicionar_jogador(interaction.user):
            # Atualizar embed
            embed = criar_embed_partida(
                titulo=f"Partida de {self.match_data.jogo}",
                jogo=self.match_data.jogo,
                modo=self.match_data.modo,
                max_jogadores=self.match_data.max_jogadores,
                jogadores=self.match_data.jogadores,
                horario=self.match_data.horario,
                iniciada=self.match_data.iniciada,
                cancelada=False,
                descricao=self.match_data.descricao
            )
            await interaction.message.edit(embed=embed)
            await interaction.followup.send("Você entrou na partida!", ephemeral=True)
            # Atualizar o banco de dados (partidas_ativas)
            guild_id = interaction.guild.id
            partidas_ativas_key = f"partidas_ativas:{guild_id}"
            partidas_ativas = get_json(partidas_ativas_key) or {}
            msg_id_str = str(interaction.message.id)
            if msg_id_str in partidas_ativas:
                partidas_ativas[msg_id_str]["jogadores_ids"] = [j.id for j in self.match_data.jogadores]
                set_json(partidas_ativas_key, partidas_ativas)
        else:
            await interaction.followup.send("Não foi possível entrar na partida (peut estar cheia ou iniciada).", ephemeral=True)

    @discord.ui.button(label="❌ Sair", style=discord.ButtonStyle.red, custom_id="sair_partida")
    async def sair(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if self.match_data.iniciada:
            await interaction.followup.send("Esta partida já começou, você não pode sair.", ephemeral=True)
            return
        if interaction.user not in self.match_data.jogadores:
            await interaction.followup.send("Você não está nesta partida.", ephemeral=True)
            return
        # Remover jogador
        if self.match_data.remover_jogador(interaction.user):
            # Atualizar embed
            embed = criar_embed_partida(
                titulo=f"Partida de {self.match_data.jogo}",
                jogo=self.match_data.jogo,
                modo=self.match_data.modo,
                max_jogadores=self.match_data.max_jogadores,
                jogadores=self.match_data.jogadores,
                horario=self.match_data.horario,
                iniciada=self.match_data.iniciada,
                cancelada=False,
                descricao=self.match_data.descricao
            )
            await interaction.message.edit(embed=embed)
            await interaction.followup.send("Você saiu da partida.", ephemeral=True)
            # Atualizar o banco de dados
            guild_id = interaction.guild.id
            partidas_ativas_key = f"partidas_ativas:{guild_id}"
            partidas_ativas = get_json(partidas_ativas_key) or {}
            msg_id_str = str(interaction.message.id)
            if msg_id_str in partidas_ativas:
                partidas_ativas[msg_id_str]["jogadores_ids"] = [j.id for j in self.match_data.jogadores]
                set_json(partidas_ativas_key, partidas_ativas)
        else:
            await interaction.followup.send("Não foi possível sair da partida.", ephemeral=True)

    @discord.ui.button(label="🗑 Cancelar", style=discord.ButtonStyle.grey, custom_id="cancelar_partida")
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if interaction.user != self.match_data.criador:
            await interaction.followup.send("Apenas o criador pode cancelar a partida.", ephemeral=True)
            return
        if self.match_data.iniciada:
            await interaction.followup.send("Esta partida já começou, não pode ser cancelada.", ephemeral=True)
            return
        # Marcar como cancelada
        self.match_data.iniciada = False  # Não iniciada, mas vamos usar um flag de cancelada no embed
        # Cancelar o countdown task
        if self.match_data.task:
            self.match_data.task.cancel()
        # Atualizar embed para cancelada
        embed = criar_embed_partida(
            titulo=f"Partida de {self.match_data.jogo}",
            jogo=self.match_data.jogo,
            modo=self.match_data.modo,
            max_jogadores=self.match_data.max_jogadores,
            jogadores=self.match_data.jogadores,
            horario=self.match_data.horario,
            iniciada=False,
            cancelada=True,
            descricao=self.match_data.descricao
        )
        await interaction.message.edit(embed=embed, view=None)  # Remove os botões
        await interaction.followup.send("Partida cancelada.", ephemeral=True)
        # Atualizar o banco de dados: remover de partidas ativas
        guild_id = interaction.guild.id
        partidas_ativas_key = f"partidas_ativas:{guild_id}"
        partidas_ativas = get_json(partidas_ativas_key) or {}
        msg_id_str = str(interaction.message.id)
        if msg_id_str in partidas_ativas:
            del partidas_ativas[msg_id_str]
            set_json(partidas_ativas_key, partidas_ativas)

    @discord.ui.button(label="👥 Ver lista", style=discord.ButtonStyle.blurple, custom_id="ver_lista_partida")
    async def ver_lista(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not self.match_data.jogadores:
            await interaction.followup.send("Nenhum jogador na partida ainda.", ephemeral=True)
            return
        lista = "\n".join([f"• {j.mention}" for j in self.match_data.jogadores])
        await interaction.followup.send(f"**Jogadores na partida:**\n{lista}", ephemeral=True)

    @discord.ui.button(label="🔔 Me lembrar", style=discord.ButtonStyle.grey, custom_id="lembrar_partida")
    async def lembrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not self.match_data.horario:
            await interaction.followup.send("Esta partida não tem horário definido.", ephemeral=True)
            return
        # Agendar um lembrete para 5 minutos antes
        agora = datetime.now(pytz.timezone(FUSO_HORARIO))
        diff = self.match_data.horario - agora
        if diff.total_seconds() <= 300:  # 5 minutos
            await interaction.followup.send("O lembrete será enviado agora (menos de 5 minutos para começar).", ephemeral=True)
            # Enviar DM agora
            try:
                await interaction.user.send(
                    f"⏰ Sua partida de {self.match_data.jogo} começa em menos de 5 minutos!\n"
                    f"👥 {len(self.match_data.jogadores)}/{self.match_data.max_jogadores} confirmados\n"
                    f"🔊 {self.match_data.message.guild.get_channel(self.match_data.canal_voz_id).mention if self.match_data.canal_voz_id else 'canal de voz não definido'}"
                )
            except:
                await interaction.followup.send("Não foi possível enviar o DM. Verifique suas configurações de privacidade.", ephemeral=True)
            return
        # Agendar para daqui a (diff - 300) segundos
        delay = diff.total_seconds() - 300
        async def enviar_lembrete_later():
            await asyncio.sleep(delay)
            try:
                await interaction.user.send(
                    f"⏰ Sua partida de {self.match_data.jogo} começa em 5 minutos!\n"
                    f"👥 {len(self.match_data.jogadores)}/{self.match_data.max_jogadores} confirmados\n"
                    f"🔊 {self.match_data.message.guild.get_channel(self.match_data.canal_voz_id).mention if self.match_data.canal_voz_id else 'canal de voz não definido'}"
                )
            except:
                pass  # Ignorar erro de DM
        asyncio.create_task(enviar_lembrete_later())
        await interaction.followup.send("Lembrete agendado para 5 minutos antes do início.", ephemeral=True)

    @discord.ui.button(label="🔁 Ressortear", style=discord.ButtonStyle.grey, custom_id="ressortear_partida")
    async def ressortear(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if interaction.user != self.match_data.criador:
            await interaction.followup.send("Apenas o criador pode ressortear a partida.", ephemeral=True)
            return
        if not self.match_data.iniciada:
            await interaction.followup.send("A partida precisa ter começado para poder ressortear.", ephemeral=True)
            return
        # Ressortear times
        times = sortear_times(self.match_data.jogadores, self.match_data.modo)
        # Atualizar embed
        embed = criar_embed_partida(
            titulo=f"Partida de {self.match_data.jogo}",
            jogo=self.match_data.jogo,
            modo=self.match_data.modo,
            max_jogadores=self.match_data.max_jogadores,
            jogadores=self.match_data.jogadores,
            horario=self.match_data.horario,
            iniciada=True,
            cancelada=False,
            times=times,
            descricao=self.match_data.descricao
        )
        await interaction.message.edit(embed=embed)
        await interaction.followup.send("Times ressorteados!", ephemeral=True)
        # Notificar no canal (opcional)
        await interaction.message.channel.send(f"{interaction.user.mention} ressorteou os times da partida.")


class Partidas(commands.Cog):
    """Cog para comandos de criação e gerenciamento de partidas."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="partida", description="Cria uma partida e convida jogadores")
    async def partida_cmd(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CriarPartidaModal())


async def setup(bot: commands.Bot):
    await bot.add_cog(Partidas(bot))
