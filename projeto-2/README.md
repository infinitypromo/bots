# Discord Bot para Organização de Partidas

Este bot foi criado para facilitar a organização de partidas em servidores de jogos no Discord.
Ele permite a criação de partidas, inscrição de jogadores, sorteio de times, lembretes e muito mais.

## Funcionalidades

- Criação de partidas via modal com informações do jogo, número de jogadores, modo (1time, 2times, 3times), canal de voz e horário.
- Embed informativo com barra de progresso, countdown ao vivo (se houver horário) e thumbnail do jogo.
- Botões interativos para entrar, sair, cancelar, ver lista, definir lembrete e ressortear times.
- Início automático da partida quando lotar ou no horário marcado.
- Criação de threads privadas para cada time (para 2times e 3times) com arquivamento automático após 2 horas.
- Histórico de partidas salvo no Replit DB, acessível via `/historico` e `/stats`.
- Comandos administrativos para listar partidas ativas, forçar encerramento e configurar o bot.
- Keep-alive para evitar hibernação no Replit.

## Pré-requisitos

- Uma conta no [Replit](https://replit.com/)
- Um bot do Discord com o token salvo nos Secrets do Replit
- O UptimeRobot (ou similar) configurado para pingar a URL do seu Repl a cada 5 minutos

## Passo a passo para setup no Replit

1.  **Crie um novo Repl** (escolha a linguagem Python).
2.  **Clone este repositório** ou copie os arquivos para o seu Repl.
    - Você pode usar o `git clone` ou fazer upload dos arquivos.
3.  **Configure os Secrets**:
    - Vá para a aba "Secrets" (ícone de cadeado na barra lateral).
    - Adicione duas variáveis de ambiente:
        - `DISCORD_TOKEN`: O token do seu bot do Discord.
        - `REPLIT_KEEP_ALIVE_PORT`: A porta para o servidor keep-alive (padrão é 8080, você pode deixar assim).
4.  **Instale as dependências**:
    - No Replit, o arquivo `requirements.txt` já está presente. O Replit deve instalá-las automaticamente.
    - Se não instalar, abra o shell e execute: `pip install -r requirements.txt`
5.  **Execute o bot**:
    - O ponto de entrada é `main.py`. O Replit já deve estar configurado para executá-lo.
    - Caso não, execute no shell: `python main.py`
6.  **Configure o UptimeRobot**:
    - Crie uma conta no [UptimeRobot](https://uptimerobot.com/) (se não tiver).
    - Adicione um novo monitor do tipo "HTTP(s)".
    - URL: `https://<seu-repl>.<seu-username>.repl.co/` (substitua `<seu-repl>` e `<seu-username>` pelos valores do seu Repl).
    - Intervalo de monitoramento: 5 minutos.
    - Salve o monitor.

## Comandos do Bot

### Comandos de Usuário (Slash Commands)

- `/partida` - Abre o modal para criar uma nova partida.
- `/historico [usuario]` - Mostra as últimas 5 partidas do usuário especificado (ou do próprio autor se nenhum for mencionado).
- `/stats [usuario]` - Mostra estatísticas do usuário especificado (ou do próprio autor).

### Comandos Administrativos (requerem permissão de "Gerenciar Servidor")

- `/admin partidas` - Lista todas as partidas ativas no servidor.
- `/admin encerrar <message_id>` - Força o encerramento de uma partida ativa pelo ID da mensagem.
- `/admin config canal_lfg <canal>` - Define o canal onde as partidas podem ser criadas (mensione o canal ou forneça o ID).
- `/admin config max_partidas <n>` - Define o limite máximo de partidas ativas por usuário.

## Estrutura de Pastas

```
.
├── main.py                 # Ponto de entrada: inicia o keep-alive e o bot
├── config.py               # Constantes e leitura de secrets
├── keepalive.py            # Servidor Flask para keep-alive
├── requirements.txt        # Dependências do projeto
├── README.md               # Este arquivo
├── cogs/
│   ├── __init__.py
│   ├── partidas.py         # Criação e gerenciamento de partidas
│   ├── historico.py        # Registro e consulta de partidas passadas
│   └── admin.py            # Comandos administrativos
├── models/
│   ├── __init__.py
│   └── match.py            # Classe MatchData
└── utils/
    ├── __init__.py
    ├── embeds.py           # Builders de embed
    ├── times.py            # Sorteio de times
    └── db.py               # Wrapper para Replit DB
```

## Tecnologias Utilizadas

- [discord.py](https://github.com/Rapptz/discord.py) versão 2.3.2
- [Flask](https://flask.palletsprojects.com/) versão 3.0.3 (para keep-alive)
- [pytz](https://pypi.org/project/pytz/) versão 2024.1
- [replit](https://pypi.org/project/replit/) versão 3.4.0 (para Replit DB)

## Notas Importantes

- O bot é projetado para rodar no Replit, portanto, toda a persistência é feita usando o Replit DB (via o pacote `replit`).
- Não há escrita em disco persistente; todos os dados são salvos no Replit DB.
- O token do bot **nunca** deve ser hardcoded ou salvo em arquivos. Use os Secrets do Replit.
- O keep-alive é essencial para evitar que o Replit hiberne o processo. Certifique-se de que o UptimeRobot está configurado corretamente.

## Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para mais detalhes.

```
