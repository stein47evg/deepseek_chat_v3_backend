# Тесты для эндпоинтов снимков.
import pytest
from fastapi import status


class TestSnapshots:
    # Тесты для /api/v1/snapshots.

    def test_get_snapshots(self, client, test_project_data):
        # Получение списка снимков проекта.
        # Создаём проект
        project_response = client.post("/api/v1/projects", json=test_project_data)
        project_id = project_response.json()["id"]

        # Получаем снимки
        response = client.get(f"/api/v1/snapshots/projects/{project_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1  # Должен быть initial снимок

    def test_create_manual_snapshot(self, client, test_project_data):
        # Создание ручного снимка.
        # Создаём проект
        project_response = client.post("/api/v1/projects", json=test_project_data)
        project_id = project_response.json()["id"]

        # Создаём ручной снимок
        snapshot_data = {
            "name": "Мой снимок",
            "description": "Тестовый снимок"
        }
        response = client.post(
            f"/api/v1/snapshots/projects/{project_id}",
            json=snapshot_data
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == snapshot_data["name"]
        assert data["description"] == snapshot_data["description"]
        assert data["type"] == "manual"
        assert data["level"] == 1

    def test_get_snapshot_by_id(self, client, test_project_data):
        # Получение снимка по ID.
        # Создаём проект
        project_response = client.post("/api/v1/projects", json=test_project_data)
        project_id = project_response.json()["id"]

        # Создаём снимок
        snapshot_data = {"name": "Тестовый снимок"}
        create_response = client.post(
            f"/api/v1/snapshots/projects/{project_id}",
            json=snapshot_data
        )
        snapshot_id = create_response.json()["id"]

        # Получаем по ID
        response = client.get(f"/api/v1/snapshots/{snapshot_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == snapshot_id

    def test_get_snapshot_not_found(self, client):
        # Получение несуществующего снимка.
        response = client.get("/api/v1/snapshots/999")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "не найден" in response.json()["detail"].lower()

    def test_delete_manual_snapshot(self, client, test_project_data):
        # Удаление ручного снимка.
        # Создаём проект
        project_response = client.post("/api/v1/projects", json=test_project_data)
        project_id = project_response.json()["id"]

        # Создаём снимок
        snapshot_data = {"name": "Для удаления"}
        create_response = client.post(
            f"/api/v1/snapshots/projects/{project_id}",
            json=snapshot_data
        )
        snapshot_id = create_response.json()["id"]

        # Удаляем
        response = client.delete(f"/api/v1/snapshots/{snapshot_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Проверяем, что удалён
        get_response = client.get(f"/api/v1/snapshots/{snapshot_id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
