# Тесты для эндпоинтов статистики.
import pytest
from fastapi import status


class TestStats:
    # Тесты для /api/v1/stats.

    def test_get_chat_stats(self, client, test_project_data, test_chat_data):
        # Получение статистики чата.
        # Создаём проект
        project_response = client.post("/api/v1/projects", json=test_project_data)
        project_id = project_response.json()["id"]

        # Создаём чат
        test_chat_data["project_id"] = project_id
        chat_response = client.post("/api/v1/chats", json=test_chat_data)
        chat_id = chat_response.json()["id"]

        # Получаем статистику
        response = client.get(f"/api/v1/stats/chats/{chat_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_input_tokens" in data
        assert "total_output_tokens" in data
        assert "total_tokens" in data
        assert "total_cost" in data
        assert "messages_count" in data
        assert "files_generated" in data

    def test_get_chat_stats_not_found(self, client):
        # Статистика для несуществующего чата.
        response = client.get("/api/v1/stats/chats/999")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "не найден" in response.json()["detail"].lower()

    def test_get_project_stats(self, client, test_project_data):
        # Получение статистики проекта.
        # Создаём проект
        project_response = client.post("/api/v1/projects", json=test_project_data)
        project_id = project_response.json()["id"]

        # Получаем статистику
        response = client.get(f"/api/v1/stats/projects/{project_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_input_tokens" in data
        assert "total_output_tokens" in data
        assert "total_tokens" in data
        assert "total_cost" in data
        assert "chats_count" in data
        assert "snapshots_count" in data

    def test_context_tokens(self, client, test_project_data, test_chat_data):
        # Подсчёт токенов в контексте.
        # Создаём проект и чат
        project_response = client.post("/api/v1/projects", json=test_project_data)
        project_id = project_response.json()["id"]

        test_chat_data["project_id"] = project_id
        chat_response = client.post("/api/v1/chats", json=test_chat_data)
        chat_id = chat_response.json()["id"]

        # Подсчёт токенов
        token_request = {
            "query": "Тестовый запрос",
            "selected_files": [],
            "history_limit": 10
        }
        response = client.post(
            f"/api/v1/stats/chats/{chat_id}/context-tokens",
            json=token_request
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_tokens" in data
        assert "breakdown" in data
        assert "files_count" in data
        assert "history_count" in data
        assert "estimated_cost" in data
