import json
import logging
import asyncio
import re
from typing import AsyncGenerator, Dict, List, Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.chat import Chat
from app.models.message import Message
from app.models.file_version import FileVersion
from app.models.project import Project
from app.models.system_prompt import SystemPrompt
from app.schemas.generate import GenerateRequest
from app.services.deepseek_client import DeepSeekClient
from app.services.parser import parse_ai_response
from app.services.token_counter import count_tokens, calculate_cost
from app.services.snapshot_service import SnapshotService
from app.utils.hash_utils import compute_hash

logger = logging.getLogger(__name__)


class GenerateService:

    def __init__(self, db: Session, chat_id: int, project_id: int):
        self.db = db
        self.chat_id = chat_id
        self.project_id = project_id
        self.client = DeepSeekClient()

    async def generate_stream(
        self, 
        request: GenerateRequest,
        max_tokens: int = 8192,
        use_stream: bool = True
    ) -> AsyncGenerator[str, None]:
        try:
            context = self._build_context(request)
            self._log_request_context(request, context)

            user_message = Message(
                chat_id=self.chat_id,
                role="user",
                content=request.query,
                input_tokens=context["total_tokens"]
            )
            self.db.add(user_message)
            self.db.flush()

            full_response = ""
            input_tokens = context["total_tokens"]
            output_tokens = 0
            
            buffer = ""
            BUFFER_SIZE = 50
            chunk_count = 0

            async for chunk in self.client.generate(
                messages=context["messages"],
                model=request.model or "flash",
                temperature=request.temperature or settings.DEFAULT_TEMPERATURE,
                max_tokens=max_tokens,
                stream=use_stream
            ):
                if chunk:
                    chunk_count += 1
                    full_response += chunk
                    output_tokens += len(chunk.split())
                    buffer += chunk
                    
                    if len(buffer) >= BUFFER_SIZE:
                        yield f"data: {json.dumps({'content': buffer, 'done': False})}\n\n"
                        buffer = ""
                        await asyncio.sleep(0.005)
            
            if buffer:
                yield f"data: {json.dumps({'content': buffer, 'done': False})}\n\n"
            
            logger.info("=" * 80)
            logger.info("СЫРОЙ ОТВЕТ ОТ НЕЙРОСЕТИ")
            logger.info("=" * 80)
            logger.info(f"Длина ответа: {len(full_response)} символов")
            logger.info(f"Количество чанков: {chunk_count}")
            logger.info(f"Содержимое:\n{full_response}")
            logger.info("=" * 80)

            if not full_response.strip():
                logger.warning("Пустой ответ от ИИ")
                yield f"data: {json.dumps({'error': 'Пустой ответ от ИИ'})}\n\n"
                return

            if '```' in full_response and full_response.count('```') % 2 != 0:
                logger.warning("Обнаружен незакрытый маркер кода. Добавляем завершение.")
                full_response += '\n```\n'

            logger.info("Парсинг ответа...")
            text, files = parse_ai_response(full_response)
            
            logger.info(f"Результат парсинга:")
            logger.info(f"  - Текст: {len(text)} символов")
            logger.info(f"  - Найдено файлов: {len(files)}")
            for f in files:
                logger.info(f"    - {f.get('type', 'unknown')}: {f.get('filename', 'без имени')} ({len(f.get('content', ''))} символов)")

            assistant_message = Message(
                chat_id=self.chat_id,
                role="assistant",
                content="",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                cost=calculate_cost(input_tokens, output_tokens, request.model or "flash")
            )
            self.db.add(assistant_message)
            self.db.flush()
            
            message_id = assistant_message.id
            logger.info(f"Сообщение ассистента создано (ID: {message_id})")

            file_ids = []
            for file_data in files:
                if file_data["type"] == "file":
                    file_version = FileVersion(
                        chat_id=self.chat_id,
                        message_id=message_id,
                        filename=file_data["filename"],
                        content=file_data["content"],
                        content_hash=compute_hash(file_data["content"]),
                        language=file_data["language"],
                        file_type="generated",
                        is_current=False,
                        applied=False
                    )
                    self.db.add(file_version)
                    self.db.flush()
                    file_ids.append({
                        "id": file_version.id,
                        "filename": file_data["filename"],
                        "language": file_data["language"]
                    })
                    logger.info(f"Файл сохранён в БД: {file_data['filename']} (ID: {file_version.id}, {len(file_data['content'])} символов)")

            content_with_markers = self._build_message_with_markers(text, file_ids)
            assistant_message.content = content_with_markers
            self.db.commit()
            
            logger.info(f"Сообщение обновлено с маркерами (ID: {message_id})")

            project = self.db.query(Project).filter(Project.id == self.project_id).first()
            if project:
                project.total_input_tokens = (project.total_input_tokens or 0) + input_tokens
                project.total_output_tokens = (project.total_output_tokens or 0) + output_tokens
                project.total_cost = float(project.total_cost or 0.0) + float(assistant_message.cost or 0.0)

            chat = self.db.query(Chat).filter(Chat.id == self.chat_id).first()
            if chat:
                chat.total_input_tokens = (chat.total_input_tokens or 0) + input_tokens
                chat.total_output_tokens = (chat.total_output_tokens or 0) + output_tokens
                chat.total_cost = float(chat.total_cost or 0.0) + float(assistant_message.cost or 0.0)

            manifest = self._get_current_manifest()
            SnapshotService.create(
                db=self.db,
                project_id=self.project_id,
                snapshot_type="apply",
                level=2,
                name=f"Генерация #{message_id}",
                files_manifest=manifest
            )

            self.db.commit()

            for file_data in files:
                if file_data["type"] == "file":
                    yield f"data: {json.dumps({'file': {'filename': file_data['filename'], 'content': file_data['content']}})}\n\n"

            yield f"data: {json.dumps({'done': True, 'message_id': message_id})}\n\n"
            
            logger.info(f"Генерация #{message_id} завершена успешно")

        except Exception as e:
            self.db.rollback()
            logger.error(f"Ошибка генерации: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    def _build_message_with_markers(self, text: str, file_ids: List[Dict]) -> str:
        if not file_ids:
            return text
        
        result = text
        for file_info in file_ids:
            filename = file_info["filename"]
            language = file_info.get("language", "text")
            file_id = file_info["id"]
            placeholder = f"[здесь был код, сгенерированный нейросетью, ID: {file_id}]"
            
            marker = f"\n\n### FILE: {filename}\n```{language}\n{placeholder}\n```"
            result += marker
        
        return result

    def _restore_markers_for_context(self, message: Message) -> str:
        files = self.db.query(FileVersion).filter(
            FileVersion.message_id == message.id
        ).all()
        
        if not files:
            return message.content
        
        text = re.sub(r'### FILE:.*?```.*?```', '', message.content, flags=re.DOTALL)
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        
        for file in files:
            placeholder = f"[здесь был код, сгенерированный нейросетью, ID: {file.id}]"
            marker = f"\n\n### FILE: {file.filename}\n```{file.language or 'text'}\n{placeholder}\n```"
            text += marker
        
        return text

    def _build_context(self, request: GenerateRequest) -> Dict:
        messages = []

        if request.system_prompt_id:
            prompt = self.db.query(SystemPrompt).filter(
                SystemPrompt.id == request.system_prompt_id
            ).first()
            if prompt:
                messages.append({"role": "system", "content": prompt.content})
        else:
            default_prompt = self.db.query(SystemPrompt).filter(
                SystemPrompt.is_default == True
            ).first()
            if default_prompt:
                messages.append({"role": "system", "content": default_prompt.content})

        history = self.db.query(Message).filter(
            Message.chat_id == self.chat_id
        ).order_by(Message.created_at.desc()).limit(settings.HISTORY_LIMIT).all()
        
        for msg in reversed(history):
            content = self._restore_markers_for_context(msg)
            messages.append({"role": msg.role, "content": content})

        files_content = ""
        if request.selected_files:
            for filename in request.selected_files:
                version = self.db.query(FileVersion).filter(
                    FileVersion.chat_id == self.chat_id,
                    FileVersion.filename == filename,
                    FileVersion.is_current == True
                ).first()
                if version:
                    files_content += f"--- {version.filename} ---\n{version.content}\n\n"

        user_prompt = request.query
        if files_content:
            user_prompt = f"{request.query}\n\nФайлы проекта:\n{files_content}"
        messages.append({"role": "user", "content": user_prompt})

        total_tokens = sum(count_tokens(msg["content"]) for msg in messages)

        return {"messages": messages, "total_tokens": total_tokens}

    def _log_request_context(self, request: GenerateRequest, context: Dict) -> None:
        logger.info("=" * 80)
        logger.info("ОТПРАВКА ЗАПРОСА В ИИ")
        logger.info("=" * 80)
        logger.info(f"Chat ID: {self.chat_id}")
        logger.info(f"Project ID: {self.project_id}")
        logger.info(f"Модель: {request.model or 'flash'}")
        logger.info(f"Температура: {request.temperature or settings.DEFAULT_TEMPERATURE}")
        logger.info(f"Всего токенов в контексте: {context['total_tokens']}")
        logger.info("=" * 80)

    def _get_current_manifest(self) -> Dict[str, str]:
        manifest = {}
        current_files = self.db.query(FileVersion).filter(
            FileVersion.chat_id == self.chat_id,
            FileVersion.is_current == True
        ).all()

        for version in current_files:
            manifest[version.filename] = version.content_hash

        return manifest
