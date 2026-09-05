# Pomodog

Aplicativo Pomodoro para terminal, construído com Python e Textual. O Pomodog
controla ciclos de foco e descanso e registra estatísticas locais em JSON.

## Escopo

O escopo atual é intencionalmente pequeno:

- interface TUI;
- ciclos de foco, pausa curta e pausa longa;
- controles para iniciar, pausar, pular e resetar;
- persistência local de sessões concluídas e focos parciais salvos em JSON.

O roadmap prevê associar sessões a tarefas e gerar relatórios de foco em PDF e
outros formatos. Essas funcionalidades ainda não estão implementadas.

## Requisitos

- Python 3.13;
- [uv](https://docs.astral.sh/uv/).

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

Atalhos disponíveis:

| Tecla | Ação |
|---|---|
| Espaço | Iniciar ou pausar |
| `s` | Pular a fase atual |
| `r` | Resetar o timer |
| `q` | Sair |

Uma fase pulada não é contabilizada como sessão concluída.

Ao resetar um foco parcialmente consumido, a TUI oferece três opções:

- `Save Partial`: registra o tempo como sessão interrompida e reseta o ciclo;
- `Discard`: descarta o tempo parcial e reseta o ciclo;
- `Cancel`: fecha o modal e restaura o estado anterior do timer.

Reset restaura o estado inicial e também zera os ciclos concluídos. Em pausas,
no estado inicial ou antes de consumir tempo de foco, o reset é imediato.

## Testes

```bash
uv run pytest
```

## Arquitetura

O projeto é um monólito local dividido em três responsabilidades:

```text
main.py                     composição das dependências
  |-- src/core/             estado e regras do timer
  |-- src/data/             persistência local em JSON
  `-- src/ui/               interface Textual e orquestração
```

`main.py` cria o engine e o repository e os injeta na TUI. O Core não depende
da interface nem da persistência. A UI coordena o timer e registra no repository
fases concluídas e focos parciais que o usuário escolheu salvar.

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
|-- data/
|   `-- stats.json
|-- src/
|   |-- core/
|   |   `-- pomodoro_engine.py
|   |-- data/
|   |   `-- json_repository.py
|   `-- ui/
|       `-- tui_app.py
`-- tests/
```

## Roadmap

1. Consolidar precisão e recuperação do timer.
2. Associar sessões de foco a tarefas.
3. Criar consultas e resumos de produtividade.
4. Exportar relatórios para Markdown e CSV.
5. Exportar relatórios para PDF e outros documentos.
