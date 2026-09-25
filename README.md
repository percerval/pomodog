# Pomodog

Aplicativo Pomodoro para terminal, construído com Python e Textual. O Pomodog
controla ciclos de foco e descanso e registra estatísticas locais em JSON.

## Escopo

O escopo atual é intencionalmente pequeno:

- interface TUI;
- ciclos de foco, pausa curta e pausa longa;
- controles para iniciar, pausar, pular e resetar;
- persistência local de sessões concluídas e focos parciais salvos em JSON;
- associação opcional de sessões a tasks;
- resumos de produtividade por task;
- recuperação de foco após encerramento inesperado;
- notificação sonora ao concluir foco ou pausa;
- notificação desktop com ícone ao concluir foco ou pausa.

O roadmap prevê exportar relatórios de foco em Markdown, CSV, PDF e outros
formatos. Essas funcionalidades ainda não estão implementadas.

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
| `t` | Gerenciar tasks |
| `p` | Exibir produtividade por task |
| `q` ou `Ctrl+Q` | Sair com segurança |

Uma fase pulada não é contabilizada como sessão concluída.

Ao resetar um foco parcialmente consumido, a TUI oferece três opções:

- `Save Partial`: registra o tempo como sessão interrompida e reseta o ciclo;
- `Discard`: descarta o tempo parcial e reseta o ciclo;
- `Cancel`: fecha o modal e restaura o estado anterior do timer.

Reset restaura o estado inicial e também zera os ciclos concluídos. Em pausas,
no estado inicial ou antes de consumir tempo de foco, o reset é imediato.

Ao pressionar `q` ou `Ctrl+Q`, a TUI sincroniza o timer antes de sair. Se o
deadline já passou, a conclusão é registrada e notificada normalmente. Se
existir um foco parcial, um modal oferece `Save Partial`, `Discard` e `Cancel`;
cancelar restaura o estado iniciado ou pausado anterior. A saída confirmada
aguarda brevemente som e popup já iniciados, sem ficar bloqueada indefinidamente.

## Tasks opcionais

O atalho `t` abre o gerenciador de tasks. Nele é possível criar, selecionar,
desassociar, concluir e excluir tasks. A seleção ativa é persistida entre
execuções e aparece na tela principal, mas não é obrigatória para iniciar um
foco.

Ao iniciar um foco, o Pomodog captura a task ativa naquele instante. A mesma
associação é preservada em pause/resume e em sessões parciais salvas. Para
evitar trocar a associação no meio de uma sessão, alterações ficam bloqueadas
enquanto houver um foco iniciado, mesmo que esteja pausado. Durante pausas do
ciclo e antes de iniciar o próximo foco, o gerenciamento volta a ser liberado.

`Complete` preserva a task e suas associações históricas. `Delete` pede
confirmação, informa quantas sessões serão afetadas e remove a task de forma
irreversível. Sessões e eventual checkpoint associados passam atomicamente para
`Sem task`; tempo e agregados não são alterados. Tasks abertas e concluídas
podem ser excluídas.

## Recuperação de foco

Enquanto um foco está ativo, o Pomodog persiste um checkpoint ao iniciar,
pausar, retomar e aproximadamente a cada cinco segundos. Se o processo for
interrompido sem passar pela saída segura, a próxima execução oferece:

- `Resume`: continua do tempo salvo, preservando task e timestamps;
- `Save Partial`: registra o checkpoint como sessão interrompida;
- `Discard`: descarta o foco recuperado.

Somente focos são recuperados; breaks continuam transitórios. O período após o
último checkpoint não é contabilizado, evitando tratar como trabalho o tempo em
que a aplicação ou o computador ficaram desligados. Registrar a sessão
recuperada e remover o checkpoint ocorre na mesma escrita atômica, impedindo
duplicação caso haja uma nova falha nesse momento.

## Produtividade por task

O atalho `p` abre um painel read-only com os períodos `Today` e `All Time`.
Para cada task, ele exibe status, tempo total de foco e quantidades de sessões
completas e interrompidas. Sessões sem associação aparecem como `Sem task`.

As linhas são ordenadas pelo maior tempo dedicado. Tasks ainda sem sessões
também aparecem, permitindo visualizar abertas e concluídas no mesmo resumo.
O filtro diário usa a data local de término de cada sessão.

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
popup aos notifiers. O repository também mantém tasks e sua associação com as
sessões.

Essa organização é uma arquitetura em camadas simples, não uma implementação
formal de MVC. Novas camadas devem ser introduzidas apenas quando tarefas,
relatórios ou outra necessidade concreta exigirem novas fronteiras.

## Persistência

As estatísticas ficam em `data/stats.json`:

```json
{
  "schema_version": 3,
  "total_focus_seconds": 754,
  "history": {
    "2026-09-05": {
      "completed_sessions": 0,
      "focus_seconds": 754
    }
  },
  "tasks": [
    {
      "id": "task-uuid-...",
      "title": "Estudar Python",
      "status": "open"
    }
  ],
  "active_task_id": "task-uuid-...",
  "active_focus": {
    "started_at": "2026-09-05T14:00:00-03:00",
    "checkpointed_at": "2026-09-05T14:12:30-03:00",
    "planned_seconds": 1500,
    "elapsed_seconds": 750,
    "task_id": "task-uuid-...",
    "is_running": true
  },
  "sessions": [
    {
      "id": "a1b2c3d4-...",
      "started_at": "2026-09-05T14:00:00-03:00",
      "ended_at": "2026-09-05T14:12:34-03:00",
      "planned_seconds": 1500,
      "actual_seconds": 754,
      "status": "interrupted",
      "task_id": "task-uuid-..."
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

Arquivos nos schemas legado e v2 são migrados automaticamente. Totais,
histórico e sessões existentes são preservados; sessões antigas permanecem com
`task_id: null`. Tasks concluídas não são removidas automaticamente. Quando uma
task é excluída explicitamente, suas referências passam para `task_id: null`.
Arquivos v3 anteriores à recuperação recebem `active_focus: null`
automaticamente.

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

1. Exportar relatórios para Markdown e CSV.
2. Exportar relatórios para PDF e outros documentos.
