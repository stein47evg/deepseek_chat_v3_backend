# Тесты для эндпоинтов системных промптов.
import pytest
from fastapi import status


class TestSystemPrompts:
    # Тесты для /api/v1/system-prompts.

    def test_get_prompts(self, client):
        # Получение списка промптов.
        response = client.get("/api/v1/system-prompts")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 5  # Минимум 5 предустановленных

    def test_get_quick_prompts(self, client):
        # Получение быстрых промптов.
        response = client.get("/api/v1/system-prompts/quick")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 3

    def test_create_custom_prompt(self, client):
        # Создание пользовательского промпта.
        prompt_data = {
            "name": "Мой промпт",
            "content": "Ты — эксперт по Python",
            "is_quick": True
        }
        response = client.post("/api/v1/system-prompts", json=prompt_data)
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == prompt_data["name"]
        assert data["content"] == prompt_data["content"]
        assert data["is_custom"] is True
        assert "id" in data

    def test_update_custom_prompt(self, client):
        # Обновление пользовательского промпта.
        # Создаём
        prompt_data = {
            "name": "Для обновления",
            "content": "Старое содержимое",
            "is_quick": False
        }
        create_response = client.post("/api/v1/system-prompts", json=prompt_data)
        prompt_id = create_response.json()["id"]

        # Обновляем
        update_data = {
            "name": "Обновлённый промпт",
            "content": "Новое содержимое",
            "is_quick": True
        }
        response = client.put(f"/api/v1/system-prompts/{prompt_id}", json=update_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["content"] == update_data["content"]
        assert data["is_quick"] is True

    def test_delete_custom_prompt(self, client):
        # Удаление пользовательского промпта.
        # Создаём
        prompt_data = {
            "name": "Для удаления",
            "content": "Удалить меня"
        }
        create_response = client.post("/api/v1/system-prompts", json=prompt_data)
        prompt_id = create_response.json()["id"]

        # Удаляем
        response = client.delete(f"/api/v1/system-prompts/{prompt_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Проверяем список (не должно быть)
        get_response = client.get("/api/v1/system-prompts")
        assert all(p["id"] != prompt_id for p in get_response.json())
