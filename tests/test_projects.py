import pytest
from fastapi import status


class TestProjects:

    def test_get_projects_empty(self, client):
        response = client.get("/api/v1/projects")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_create_project(self, client, test_project_data):
        response = client.post("/api/v1/projects", json=test_project_data)
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == test_project_data["name"]
        assert data["folder_path"] == test_project_data["folder_path"]
        assert "id" in data
        assert "created_at" in data

    def test_create_project_duplicate(self, client, test_project_data):
        # Первый раз создаём
        client.post("/api/v1/projects", json=test_project_data)
        # Второй раз — ошибка
        response = client.post("/api/v1/projects", json=test_project_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "уже существует" in response.json()["detail"].lower()

    def test_get_project_by_id(self, client, test_project_data):
        # Создаём проект
        create_response = client.post("/api/v1/projects", json=test_project_data)
        project_id = create_response.json()["id"]

        # Получаем по ID
        response = client.get(f"/api/v1/projects/{project_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == project_id
        assert data["name"] == test_project_data["name"]

    def test_get_project_not_found(self, client):
        response = client.get("/api/v1/projects/999")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "не найден" in response.json()["detail"].lower()

    def test_delete_project(self, client, test_project_data):
        # Создаём проект
        create_response = client.post("/api/v1/projects", json=test_project_data)
        project_id = create_response.json()["id"]

        # Удаляем
        response = client.delete(f"/api/v1/projects/{project_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Проверяем, что удалён
        get_response = client.get(f"/api/v1/projects/{project_id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
