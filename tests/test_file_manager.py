import os
import pytest
from fastapi import status
from sqlalchemy.orm import Session
from app.models.project import Project
from app.models.chat import Chat
from app.models.file_version import FileVersion
from app.models.snapshot import Snapshot
from app.core.database import get_db


class TestFileManager:
    """Тесты для файлового менеджера (/api/v1/file-manager)."""

    def test_get_disk_files_empty(self, client, test_project_data):
        """Получение файлов с диска для пустого проекта."""
        # Создаём проект
        project_response = client.post("/api/v1/projects", json=test_project_data)
        assert project_response.status_code == status.HTTP_201_CREATED
        project_id = project_response.json()["id"]

        # Получаем файлы с диска
        response = client.get(f"/api/v1/file-manager/{project_id}/disk-files")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    def test_get_disk_files_with_ignored(self, client, test_project_data, tmp_path):
        """Получение файлов с диска с игнорируемыми файлами."""
        # Создаём проект с папкой
        project_folder = tmp_path / "test_project"
        project_folder.mkdir()
        
        # Создаём файлы
        (project_folder / "main.py").write_text("print('Hello')")
        (project_folder / "node_modules").mkdir()
        (project_folder / "node_modules" / "package.json").write_text("{}")

        project_data = {
            "name": "TestProject",
            "folder_path": str(project_folder)
        }
        project_response = client.post("/api/v1/projects", json=project_data)
        assert project_response.status_code == status.HTTP_201_CREATED
        project_id = project_response.json()["id"]

        # Получаем файлы (без игнорируемых)
        response = client.get(f"/api/v1/file-manager/{project_id}/disk-files")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "main.py"

        # Получаем файлы (с игнорируемыми)
        response = client.get(f"/api/v1/file-manager/{project_id}/disk-files?show_ignored=true")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # node_modules может быть отфильтрован, но файл package.json внутри него не показывается
        assert len(data) >= 1

    def test_sync_disk_files(self, client, test_project_data, tmp_path):
        """Синхронизация файлов с диска в БД."""
        project_folder = tmp_path / "test_project"
        project_folder.mkdir()
        (project_folder / "main.py").write_text("print('Hello')")

        project_data = {
            "name": "TestProject",
            "folder_path": str(project_folder)
        }
        project_response = client.post("/api/v1/projects", json=project_data)
        assert project_response.status_code == status.HTTP_201_CREATED
        project_id = project_response.json()["id"]

        # Синхронизация
        response = client.post(f"/api/v1/file-manager/{project_id}/disk-files/sync")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "synced"
        assert data["created"] == 1

        # Проверяем, что файл появился в БД
        response = client.get(f"/api/v1/projects/{project_id}/files")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["path"] == "main.py"

    def test_delete_file_soft(self, client, test_project_data, tmp_path, db_session):
        """Мягкое удаление файла (с диска, но в БД остаётся)."""
        project_folder = tmp_path / "test_project"
        project_folder.mkdir()
        (project_folder / "main.py").write_text("print('Hello')")

        project_data = {
            "name": "TestProject",
            "folder_path": str(project_folder)
        }
        project_response = client.post("/api/v1/projects", json=project_data)
        assert project_response.status_code == status.HTTP_201_CREATED
        project_id = project_response.json()["id"]

        # Синхронизируем
        sync_response = client.post(f"/api/v1/file-manager/{project_id}/disk-files/sync")
        assert sync_response.status_code == status.HTTP_200_OK

        # Проверяем, что файл в БД
        response = client.get(f"/api/v1/projects/{project_id}/files")
        assert len(response.json()) == 1

        # Мягкое удаление
        response = client.delete(
            f"/api/v1/file-manager/{project_id}/files/main.py?hard=false"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "soft_deleted"
        assert data["was_in_database"] is True

        # Проверяем, что файл на диске удалён
        assert not (project_folder / "main.py").exists()

    def test_delete_file_hard(self, client, test_project_data, tmp_path):
        """Полное удаление файла (с диска и из БД)."""
        project_folder = tmp_path / "test_project"
        project_folder.mkdir()
        (project_folder / "main.py").write_text("print('Hello')")

        project_data = {
            "name": "TestProject",
            "folder_path": str(project_folder)
        }
        project_response = client.post("/api/v1/projects", json=project_data)
        assert project_response.status_code == status.HTTP_201_CREATED
        project_id = project_response.json()["id"]

        # Синхронизируем
        sync_response = client.post(f"/api/v1/file-manager/{project_id}/disk-files/sync")
        assert sync_response.status_code == status.HTTP_200_OK

        # Полное удаление
        response = client.delete(
            f"/api/v1/file-manager/{project_id}/files/main.py?hard=true"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "hard_deleted"
        assert data["was_in_database"] is True
        assert data["versions_deleted"] >= 1

        # Проверяем, что файл на диске удалён
        assert not (project_folder / "main.py").exists()

        # Проверяем, что из БД удалён
        response = client.get(f"/api/v1/projects/{project_id}/files")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 0

    def test_delete_file_not_in_db(self, client, test_project_data, tmp_path):
        """Удаление файла, которого нет в БД."""
        project_folder = tmp_path / "test_project"
        project_folder.mkdir()
        (project_folder / "temp.log").write_text("log")

        project_data = {
            "name": "TestProject",
            "folder_path": str(project_folder)
        }
        project_response = client.post("/api/v1/projects", json=project_data)
        assert project_response.status_code == status.HTTP_201_CREATED
        project_id = project_response.json()["id"]

        # Удаляем файл (его нет в БД)
        response = client.delete(
            f"/api/v1/file-manager/{project_id}/files/temp.log?hard=false"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "soft_deleted"
        assert data["was_in_database"] is False

        # Проверяем, что файл на диске удалён
        assert not (project_folder / "temp.log").exists()

    def test_delete_file_not_found(self, client, test_project_data):
        """Удаление несуществующего файла."""
        project_response = client.post("/api/v1/projects", json=test_project_data)
        assert project_response.status_code == status.HTTP_201_CREATED
        project_id = project_response.json()["id"]

        response = client.delete(
            f"/api/v1/file-manager/{project_id}/files/not_exist.py"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_flatten_history(self, client, test_project_data, tmp_path):
        """Сброс истории состояний."""
        project_folder = tmp_path / "test_project"
        project_folder.mkdir()
        (project_folder / "main.py").write_text("print('Hello')")

        project_data = {
            "name": "TestProject",
            "folder_path": str(project_folder)
        }
        project_response = client.post("/api/v1/projects", json=project_data)
        assert project_response.status_code == status.HTTP_201_CREATED
        project_id = project_response.json()["id"]

        # Синхронизируем
        client.post(f"/api/v1/file-manager/{project_id}/disk-files/sync")

        # Создаём несколько снимков
        client.post(f"/api/v1/snapshots/projects/{project_id}",
                    json={"name": "Снимок 1"})
        client.post(f"/api/v1/snapshots/projects/{project_id}",
                    json={"name": "Снимок 2"})

        # Проверяем, что снимков 3 (initial + 2 ручных)
        response = client.get(f"/api/v1/snapshots/projects/{project_id}")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 3

        # Сбрасываем историю
        response = client.post(f"/api/v1/file-manager/{project_id}/history/flatten")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "flattened"
        assert data["deleted_snapshots"] == 3
        assert data["preserved_files"] == 1

        # Проверяем, что остался только 1 снимок
        response = client.get(f"/api/v1/snapshots/projects/{project_id}")
        assert response.status_code == status.HTTP_200_OK
        snapshots = response.json()
        assert len(snapshots) == 1
        assert snapshots[0]["type"] == "initial"
        assert snapshots[0]["name"] == "История сброшена"

    def test_flatten_history_no_current(self, client, test_project_data, db_session):
        """Сброс истории без текущего состояния."""
        project_response = client.post("/api/v1/projects", json=test_project_data)
        assert project_response.status_code == status.HTTP_201_CREATED
        project_id = project_response.json()["id"]

        # Удаляем текущий снимок (нештатная ситуация)
        current = db_session.query(Snapshot).filter(
            Snapshot.project_id == project_id,
            Snapshot.is_current == True
        ).first()
        if current:
            db_session.delete(current)
            db_session.commit()

        response = client.post(f"/api/v1/file-manager/{project_id}/history/flatten")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_disk_files_invalid_project(self, client):
        """Получение файлов для несуществующего проекта."""
        response = client.get("/api/v1/file-manager/999/disk-files")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_file_invalid_project(self, client):
        """Удаление файла в несуществующем проекте."""
        response = client.delete("/api/v1/file-manager/999/files/main.py")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_directory(self, client, test_project_data, tmp_path):
        """Попытка удалить папку (должна быть ошибка)."""
        project_folder = tmp_path / "test_project"
        project_folder.mkdir()
        (project_folder / "src").mkdir()

        project_data = {
            "name": "TestProject",
            "folder_path": str(project_folder)
        }
        project_response = client.post("/api/v1/projects", json=project_data)
        assert project_response.status_code == status.HTTP_201_CREATED
        project_id = project_response.json()["id"]

        response = client.delete(
            f"/api/v1/file-manager/{project_id}/files/src"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Нельзя удалить папку" in response.json()["detail"]
