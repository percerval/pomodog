from src.data.json_repository import JSONRepository


def main():
    repo = JSONRepository()

    print("--- Testando JSONRepository ---")

    # 1. Simula a conclusão de uma sessão de 25 minutos de foco
    repo.save_completed_session(focus_minutes=25)
    print("Sessão de 25 minutos registrada com sucesso!")

    # 2. Lê as estatísticas do dia atual
    today_stats = repo.get_today_stats()
    print(f"Estatísticas de Hoje: {today_stats}")

    # 3. Lê o relatório completo
    all_stats = repo.get_stats()
    print(f"Relatório Geral: {all_stats}")


if __name__ == "__main__":
    main()