# Pomodog

Aplicativo Pomodoro para terminal, construído com Python e Textual. O Pomodog
controla ciclos de foco e descanso e registra estatísticas locais em JSON.

## Escopo

O escopo atual é intencionalmente pequeno:

- interface TUI;
- ciclos de foco, pausa curta e pausa longa;
- controles para iniciar, pausar, pular e resetar;
- persistência local de sessões concluídas e focos parciais salvos em JSON;
- notificação sonora ao concluir foco ou pausa;
- notificação desktop com ícone ao concluir foco ou pausa.

O roadmap prevê associar sessões a tarefas e gerar relatórios de foco em PDF e
outros formatos. Essas funcionalidades ainda não estão implementadas.

## Requisitos

- Python 3.13;
- [uv](https://docs.astral.sh/uv/);
- `notify-send` (`libnotify`) para popups desktop — opcional; sem ele, apenas o som funciona.

As versões exatas das dependências são registradas em `uv.lock`.

## Instalação

Na raiz do projeto, reconstrua o ambiente virtual a partir do lockfile:

```bash
uv sync
```

## Execução

```bash
uv run python main.py
```

## Precisão do timer

O intervalo de um segundo da TUI serve apenas para atualizar a tela. O engine
calcula o tempo restante a partir de um deadline, portanto callbacks atrasados
não prolongam a sessão artificialmente.

No Linux, o relógio usa `CLOCK_BOOTTIME`, que é monotônico e inclui o período em
que o sistema permaneceu suspenso. Em outras plataformas, o fallback é
`time.monotonic()`. Pause e resume preservam também as frações de segundo já
decorridas. Timestamps são ancorados em UTC e avançados pela mesma linha de
tempo monotônica, evitando atribuir a uma sessão o horário de um callback
atrasado ou de um relógio civil reajustado.

Atalhos disponíveis:

| Tecla | Ação |
|---|---|
| Espaço | Iniciar ou pausar |
| `s` | Pular a fase atual |
| `r` | Resetar o timer |
| `m` | Ativar ou silenciar o som |
| `q` | Sair |

Uma fase pulada não é contabilizada como sessão concluída.

Ao resetar um foco parcialmente consumido, a TUI oferece três opções:

- `Save Partial`: registra o tempo como sessão interrompida e reseta o ciclo;
- `Discard`: descarta o tempo parcial e reseta o ciclo;
- `Cancel`: fecha o modal e restaura o estado anterior do timer.

Reset restaura o estado inicial e também zera os ciclos concluídos. Em pausas,
no estado inicial ou antes de consumir tempo de foco, o reset é imediato.

## Notificação sonora

O mesmo sino curto é reproduzido quando um foco ou uma pausa termina
naturalmente. Skip, Reset, Save Partial, Discard e Cancel permanecem silenciosos.

O áudio fica em `assets/sounds/session-complete.wav`. A reprodução ocorre fora
do event loop e tenta, nesta ordem, `pw-play`, `paplay` e `aplay`. Se nenhum
backend conseguir reproduzir o arquivo, a aplicação usa o terminal bell do
Textual. Não há dependência Python adicional para áudio.

O atalho `m` alterna mute durante a execução. A preferência ainda não é
persistida entre execuções.

## Notificação desktop

Um popup do sistema é exibido quando um foco ou uma pausa termina
naturalmente, com mensagens distintas para cada caso. Skip, Reset,
Save Partial, Discard e Cancel permanecem silenciosos.

O envio usa `notify-send` em thread dedicada, sem bloquear o event loop,
com o ícone `assets/icons/pomodog.png`. O mute (`m`) vale apenas para o
áudio — os popups continuam aparecendo. Se o `notify-send` estiver ausente
ou o serviço de notificações falhar, o popup é ignorado silenciosamente.

## Testes

```bash
uv run pytest
```

## Arquitetura

O projeto é um monólito local dividido em quatro responsabilidades:

```text
main.py                     composição das dependências
  |-- src/core/             estado e regras do timer
  |-- src/data/             persistência local em JSON
  |-- src/notifications/    áudio e popups do sistema
  `-- src/ui/               interface Textual e orquestração
```

`main.py` cria o engine, o repository, o notifier de áudio e o notifier
desktop e os injeta na TUI. O Core não depende da interface, da persistência
nem das notificações. A UI coordena o timer, registra no repository fases
concluídas e focos parciais que o usuário escolheu salvar e solicita som e
popup aos notifiers.

Essa organização é uma arquitetura em camadas simples, não uma implementação
formal de MVC. Novas camadas devem ser introduzidas apenas quando tarefas,
relatórios ou outra necessidade concreta exigirem novas fronteiras.

## Persistência

As estatísticas ficam em `data/stats.json`:

```json
{
  "schema_version": 2,
  "total_focus_seconds": 754,
  "history": {
    "2026-09-05": {
      "completed_sessions": 0,
      "focus_seconds": 754
    }
  },
  "sessions": [
    {
      "id": "a1b2c3d4-...",
      "started_at": "2026-09-05T14:00:00-03:00",
      "ended_at": "2026-09-05T14:12:34-03:00",
      "planned_seconds": 1500,
      "actual_seconds": 754,
      "status": "interrupted"
    }
  ]
}
```

O arquivo é local e não é versionado. O caminho é definido em `main.py` a
partir da raiz do projeto, portanto a aplicação pode ser iniciada de qualquer
diretório.

Segundos são a unidade canônica para evitar perda de precisão. Sessões
`completed` e `interrupted` somam tempo de foco, mas somente `completed`
incrementa a quantidade de sessões e o ciclo usado para calcular pausas longas.
Durações subsegundo são preservadas e os agregados são normalizados para evitar
erros cumulativos de ponto flutuante.

Arquivos no formato legado são migrados automaticamente. Os totais históricos
são preservados, mas não podem ser convertidos em sessões individuais porque o
formato antigo não registrava horários nem durações por sessão.

As sessões são agrupadas pela data de término e as gravações usam substituição
atômica do arquivo para reduzir o risco de corrupção por interrupções.

## Estrutura

```text
pomodog/
|-- main.py
|-- pyproject.toml
|-- uv.lock
|-- assets/
|   |-- icons/
|   |   `-- pomodog.png
|   `-- sounds/
|       `-- session-complete.wav
|-- data/
|   `-- stats.json
|-- src/
|   |-- core/
|   |   `-- pomodoro_engine.py
|   |-- data/
|   |   `-- json_repository.py
|   |-- notifications/
|   |   |-- desktop_notifier.py
|   |   `-- sound_notifier.py
|   `-- ui/
|       `-- tui_app.py
`-- tests/
```

## Roadmap

1. Recuperar uma sessão em andamento após encerramento inesperado.
2. Associar sessões de foco a tarefas.
3. Criar consultas e resumos de produtividade.
4. Exportar relatórios para Markdown e CSV.
5. Exportar relatórios para PDF e outros documentos.
