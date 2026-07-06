"""
Сервис для генерации кода.
"""
import json
from typing import AsyncGenerator, List, Dict, Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.chat import Chat
from app.models.message import Message
from app.models.file_version import FileVersion
from app.models.snapshot import Snapshot
from app.models.system_prompt import SystemPrompt
from app.schemas.generate import GenerateRequest
from app.services.deepseek_client import DeepSeekClient
from app.services.parser import parse_ai_response
from app.services.token_counter import count_tokens, calculate_cost
from app.services.snapshot_service import SnapshotService
from app.utils.hash_utils import compute_hash


class GenerateService:
    """Сервис для обработки запросов генерации."""

    def __init__(self, db: Session, chat: Chat):
        self.db = db
        self.chat = chat
        self.client = DeepSeekClient()

    async def generate_stream(self, request: GenerateRequest) -> AsyncGenerator[str, None]:
        """
        Основной метод генерации с возвратом SSE стрима.
        """
        try:
            # 1. Формируем контекст
            context = self._build_context(request)

            # 2. Сохраняем сообщение пользователя
            user_message = Message(
                chat_id=self.chat.id,
                role="user",
                content=request.query,
                input_tokens=context["total_tokens"]
            )
            self.db.add(user_message)
            self.db.flush()

            # 3. Отправляем запрос в DeepSeek
            full_response = ""
            input_tokens = context["total_tokens"]
            output_tokens = 0

            # 4. Стримим ответ
            async for chunk in self.client.generate(
                messages=context["messages"],
                model=request.model or "flash",
                temperature=request.temperature or settings.DEFAULT_TEMPERATURE
            ):
                full_response += chunk
                output_tokens += len(chunk.split())  # приблизительно
                yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"

            # 5. Парсим ответ
            text, files = parse_ai_response(full_response)

            # 6. Сохраняем сообщение ассистента
            assistant_message = Message(
                chat_id=self.chat.id,
                role="assistant",
                content=text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                cost=calculate_cost(input_tokens, output_tokens, request.model or "flash")
            )
            self.db.add(assistant_message)
            self.db.flush()

            # 7. Сохраняем файлы
            for file_data in files:
                if file_data["type"] == "file":
                    file_version = FileVersion(
                        chat_id=self.chat.id,
                        message_id=assistant_message.id,
                        filename=file_data["filename"],
                        content=file_data["content"],
                        content_hash=compute_hash(file_data["content"]),
                        language=file_data["language"],
                        file_type="generated",
                        is_current=False,
                        applied=False
                    )
                    self.db.add(file_version)

                    # Отправляем информацию о файле
                    yield f"data: {json.dumps({'file': {'filename': file_data['filename'], 'content': file_data['content']}})}\n\n"

            # 8. Создаём снимок состояния (уровень 2)
            manifest = self._get_current_manifest()
            SnapshotService.create(
                db=self.db,
                project_id=self.chat.project_id,
                snapshot_type="apply",
                level=2,
                name=f"Генерация #{assistant_message.id}",
                files_manifest=manifest
            )

            self.db.commit()

            # 9. Финальное событие
            yield f"data: {json.dumps({'done': True, 'message_id': assistant_message.id})}\n\n"

        except Exception as e:
            self.db.rollback()
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    def _build_context(self, request: GenerateRequest) -> Dict:
        """
        Формирует контекст для отправки в DeepSeek.
        """
        messages = []

        # 1. Системный промпт
        if request.system_prompt_id:
            prompt = self.db.query(SystemPrompt).filter(
                SystemPrompt.id == request.system_prompt_id
            ).first()
            if prompt:
                messages.append({"role": "system", "content": prompt.content})
        else:
            # Промпт по умолчанию
            default_prompt = self.db.query(SystemPrompt).filter(
                SystemPrompt.is_default == True
            ).first()
            if default_prompt:
                messages.append({"role": "system", "content": default_prompt.content})

        # 2. История сообщений (последние N)
        history = self.db.query(Message).filter(
            Message.chat_id == self.chat.id
        ).order_by(Message.created_at.desc()).limit(settings.HISTORY_LIMIT).all()

        for msg in reversed(history):
            messages.append({"role": msg.role, "content": msg.content})

        # 3. Файлы в контексте
        files_content = ""
        for filename in request.selected_files:
            version = self.db.query(FileVersion).filter(
                FileVersion.chat_id == self.chat.id,
                FileVersion.filename == filename,
                FileVersion.is_current == True
            ).first()

            if version:
                files_content += f"--- {version.filename} ---\n{version.content}\n\n"

        # 4. Запрос пользователя
        user_prompt = request.query
        if files_content:
            user_prompt = f"{request.query}\n\nФайлы проекта:\n{files_content}"

        messages.append({"role": "user", "content": user_prompt})

        # 5. Подсчёт токенов
        total_tokens = sum(count_tokens(msg["content"]) for msg in messages)

        return {
            "messages": messages,
            "total_tokens": total_tokens
        }

    def _get_current_manifest(self) -> Dict[str, str]:
        """Собирает мэнифест текущих файлов."""
        manifest = {}
        current_files = self.db.query(FileVersion).filter(
            FileVersion.chat_id == self.chat.id,
            FileVersion.is_current == True
        ).all()

        for version in current_files:
            manifest[version.filename] = version.content_hash

        return manifest
