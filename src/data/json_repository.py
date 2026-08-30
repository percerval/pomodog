import json
import os
from datetime import date

class JSONRepository:
    """
    Gerencia a persistência de dados e o histórico de sessões do Pomodoro em um arquivo JSON.
    Seguindo o padrão Repository para desacoplar o armazenamento de dados das interfaces.
    """

    def __init__(self, file_path: str = "data/stats.json"):
        self.file_path = file_path
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """
        Método privado que garante que a pasta e o arquivo JSON existam no disco.
        """
        folder = os.path.dirname(self.file_path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)

        if not os.path.exists(self.file_path):
            initial_data = {
                "total_focus_time_minutes": 0,
                "history": {}
            }
            self._write_json(initial_data)
    
    def _read_json(self) -> dict:
        """
        Lê e converte o conteúdo do arquivo JSON para um dicionário Python.
        """
        try:
            with open(self.file_path, "r", encoding="utf-8") as  file:
                return json.load(file)
        except(json.JSONDecodeError, FileNotFoundError):
            # Se o arquivo estiver corrompido ou ausente, restaura a estrutura inicial
            initial_data = {
                "total_focus_time_minutes": 0,
                "history": {}
            }
            self._write_json(initial_data)
            return initial_data

    def _write_json(self, data: dict):
        """
        Escreve a estrutura de dados novamente no JSON com formatação legível.
        """
        with open(self.file_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

    #---------------------------------------------------
    # Métodos Públicos (Interface utilizada pelo App/UI)
    #---------------------------------------------------
    def save_completed_session(self, focus_minutes: int):
        """
        Registra uma sessão de foco concluída no histórico de hoje.
        Incrementa os minutos acumulados e a contagem do dia.
        """
        data = self._read_json()
        today = date.today().isoformat() # YYYY-MM-DD
        
        # Atualiza o total acumulado do sistema
        data["total_focus_time_minutes"] = data.get("total_focus_time_minutes", 0) + focus_minutes

        # Garante a estrutura para a data de hoje
        if today not in data["history"]:
            data["history"][today] = {
                "completed_sessions": 0,
                "focus_minutes": 0
            }

        data["history"][today]["completed_sessions"] += 1
        data["history"][today]["focus_minutes"] += focus_minutes

        self._write_json(data)

    def get_stats(self) -> dict:
        """
        Retorna o dicionário completo de estatísticas e histórico.
        """
        return self._read_json()

    def get_today_stats(self) -> dict:
        """Retorna estatísticas apenas da data atual (sessões e minutos)."""
        data = self._read_json()
        today = date.today().isoformat()
        return data["history"].get(today, {"completed_sessions": 0, "focus_minutes": 0})