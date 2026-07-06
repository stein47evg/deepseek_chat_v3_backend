# Тесты для эндпоинтов чатов.
import pytest
from fastapi import status


class TestChats:
    # Тесты для /api/v1/chats.

    def test_create_chat(self, client, test_project_data, test_chat_data):
        # Создание чата.
        # Создаём проект
        project_response = client.post("/api/v1/projects", json=test_project_data)
        project_id = project_response.json()["id"]

        # Создаём чат
        test_chat_data["project_id"] = project_id
        response = client.post("/api/v1/chats", json=test_chat_data)
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["title"] == test_chat_data["title"]
        assert data["project_id"] == project_id
        assert "id" in data
        assert "created_at" in data

    def test_get_chats_by_project(self, client, test_project_data, test_chat_data):
        # Получение списка чатов проекта.
        # Создаём проект
        project_response = client.post("/api/v1/projects", json=test_project_data)
        project_id = project_response.json()["id"]

        # Создаём чат
        test_chat_data["project_id"] = project_id
        client.post("/api/v1/chats", json=test_chat_data)

        # Получаем список чатов
        response = client.get(f"/api/v1/chats?project_id={project_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1
        assert data[0]["project_id"] == project_id

    def test_get_chat_by_id(self, client, test_project_data, test_chat_data):
        # Получение чата по ID.
        # Создаём проект и чат
        project_response = client.post("/api/v1/projects", json=test_project_data)
        project_id = project_response.json()["id"]

        test_chat_data["project_id"] = project_id
        create_response = client.post("/api/v1/chats", json=test_chat_data)
        chat_id = create_response.json()["id"]

        # Получаем чат по ID
        response = client.get(f"/api/v1/chats/{chat_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == chat_id
        assert data["title"] == test_chat_data["title"]

    def test_get_chat_not_found(self, client):
        # Получение несуществующего чата.
        response = client.get("/api/v1/chats/999")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "не найден" in response.json()["detail"].lower()

    def test_delete_chat(self, client, test_project_data, test_chat_data):
        # Удаление чата.
        # Создаём проект и чат
        project_response = client.post("/api/v1/projects", json=test_project_data)
        project_id = project_response.json()["id"]

        test_chat_data["project_id"] = project_id
        create_response = client.post("/api/v1/chats", json=test_chat_data)
        chat_id = create_response.json()["id"]

        # Удаляем чат
        response = client.delete(f"/api/v1/chats/{chat_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Проверяем, что удалён
        get_response = client.get(f"/api/v1/chats/{chat_id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
