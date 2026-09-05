# Pomodog

Aplicativo Pomodoro para terminal, construído com Python e Textual. O Pomodog
controla ciclos de foco e descanso e registra estatísticas locais em JSON.

## Escopo

O escopo atual é intencionalmente pequeno:

- interface TUI;
- ciclos de foco, pausa curta e pausa longa;
- controles para iniciar, pausar, pular e resetar;
- persistência local de sessões concluídas em JSON.

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
somente as fases de foco efetivamente concluídas.

Essa organização é uma arquitetura em camadas simples, não uma implementação
formal de MVC. Novas camadas devem ser introduzidas apenas quando tarefas,
relatórios ou outra necessidade concreta exigirem novas fronteiras.

## Persistência

As estatísticas ficam em `data/stats.json`:

```json
{
  "total_focus_time_minutes": 25,
  "history": {
    "2026-09-05": {
      "completed_sessions": 1,
      "focus_minutes": 25
    }
  }
}
```

O arquivo é local e não é versionado. O caminho é definido em `main.py` a
partir da raiz do projeto, portanto a aplicação pode ser iniciada de qualquer
diretório.

O schema atual guarda somente agregados. Antes de associar foco a tarefas ou
emitir relatórios detalhados, será necessário registrar sessões individuais,
com informações como início, fim, duração e identificador da tarefa.

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

1. Consolidar testes e regras do timer.
2. Evoluir o JSON de agregados para registros individuais de sessão.
3. Associar sessões de foco a tarefas.
4. Criar consultas e resumos de produtividade.
5. Exportar relatórios para PDF e outros documentos.
