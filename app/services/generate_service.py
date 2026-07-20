import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chat import Chat
from app.models.file_version import FileVersion
from app.models.message import Message
from app.models.project import Project
from app.models.system_prompt import SystemPrompt
from app.schemas.generate import GenerateRequest
from app.services.deepseek_client import DeepSeekClient
from app.services.generation_manager import generation_manager
from app.services.parser import parse_ai_response
from app.services.snapshot_service import SnapshotService
from app.services.token_counter import calculate_cost, count_tokens
from app.utils.hash_utils import compute_hash

logger = logging.getLogger(__name__)


class GenerateService:
    """
    Сервис для генерации кода с использованием DeepSeek.

    Поддерживает три стратегии формирования контекста:
    1. full_history - полная история диалога (для обсуждения)
    2. no_history - только текущий запрос (для генерации кода)
    3. flexible - гибкая стратегия с управлением контекстом
    """

    def __init__(self, db: Session, chat_id: int, project_id: int):
        self.db = db
        self.chat_id = chat_id
        self.project_id = project_id
        self.client = DeepSeekClient()
        self.last_finish_reason = None  # Храним причину завершения

    # ============================================================
    # 1. ПОЛУЧЕНИЕ СИСТЕМНОГО ПРОМПТА
    # ============================================================

    def _get_system_prompt(self, request: GenerateRequest) -> str:
        """
        Получает системный промпт для нейросети.

        Приоритет:
        1. system_prompt_id из запроса (всегда передаётся фронтом)
        2. Промпт по умолчанию (fallback)
        """
        if request.system_prompt_id:
            prompt = (
                self.db.query(SystemPrompt)
                .filter(SystemPrompt.id == request.system_prompt_id)
                .first()
            )
            if prompt:
                return prompt.content

        # Fallback: промпт по умолчанию
        default = (
            self.db.query(SystemPrompt).filter(SystemPrompt.is_default == True).first()
        )
        return default.content if default else "Ты — полезный ассистент."

    # ============================================================
    # 2. ПОЛУЧЕНИЕ СТРАТЕГИИ
    # ============================================================

    def _get_chat_strategy(self) -> str:
        """Возвращает стратегию чата (full_history, no_history, flexible)."""
        chat = self.db.query(Chat).filter(Chat.id == self.chat_id).first()
        return chat.generation_strategy if chat else "flexible"

    # ============================================================
    # 3. ВОССТАНОВЛЕНИЕ КОДА ИЗ ПЛЕЙСХОЛДЕРОВ
    # ============================================================

    def _restore_full_content(self, message: Message) -> str:
        """
        Восстанавливает полный код из сообщения, заменяя плейсхолдеры на реальный код.

        Плейсхолдер имеет формат:
        [здесь был код, сгенерированный нейросетью, ID: 177]

        Функция находит все плейсхолдеры и заменяет их на содержимое файла из БД.
        """
        content = message.content

        # Паттерн для поиска плейсхолдеров с ID
        pattern = r"\[здесь был код, сгенерированный нейросетью, ID: (\d+)\]"

        def replace_placeholder(match):
            file_id = int(match.group(1))
            version = (
                self.db.query(FileVersion).filter(FileVersion.id == file_id).first()
            )
            if version:
                return version.content
            return f"[Файл {file_id} не найден]"

        restored = re.sub(pattern, replace_placeholder, content)
        return restored

    # ============================================================
    # 4. ПОЛУЧЕНИЕ ФАЙЛОВ ИЗ ПЕРВОГО СООБЩЕНИЯ ИСТОРИИ
    # ============================================================

    def _get_history_start_files(self) -> list[FileVersion]:
        """
        Находит первое сообщение пользователя в текущей истории,
        у которого есть приложенные файлы, и возвращает эти файлы.

        Используется в гибкой стратегии для подтягивания файлов
        при продолжении истории.
        """
        # Находим первое сообщение с файлами в истории
        first_with_files = (
            self.db.query(Message)
            .filter(
                Message.chat_id == self.chat_id,
                Message.role == "user",
                Message.context_data.isnot(None),
                func.json_length(Message.context_data, "$.file_version_ids") > 0,
            )
            .order_by(Message.created_at.asc())
            .first()
        )

        if not first_with_files:
            return []

        # Получаем ID файлов из context_data
        file_ids = first_with_files.context_data.get("file_version_ids", [])
        if not file_ids:
            return []

        # Загружаем файлы из БД
        files = self.db.query(FileVersion).filter(FileVersion.id.in_(file_ids)).all()

        return files

    # ============================================================
    # 5. ПОСТРОЕНИЕ ИСТОРИИ
    # ============================================================

    def _get_history_messages(self, strategy: str) -> list[Message]:
        """
        Возвращает список сообщений истории в зависимости от стратегии.

        - full_history: все сообщения чата
        - no_history: пустой список
        - flexible: сообщения от последнего сообщения с файлами
        """
        if strategy == "no_history":
            return []

        query = self.db.query(Message).filter(Message.chat_id == self.chat_id)

        if strategy == "flexible":
            # Находим последнее сообщение с файлами (маркер начала истории)
            last_with_files = (
                self.db.query(Message)
                .filter(
                    Message.chat_id == self.chat_id,
                    Message.role == "user",
                    Message.context_data.isnot(None),
                    func.json_length(Message.context_data, "$.file_version_ids") > 0,
                )
                .order_by(Message.created_at.desc())
                .first()
            )

            if last_with_files:
                # Берём историю от последнего сообщения с файлами
                query = query.filter(Message.id >= last_with_files.id)
            else:
                # Если нет сообщений с файлами — вся история
                pass

        # Сортировка по возрастанию (от старых к новым)
        return query.order_by(Message.created_at.asc()).all()

    # ============================================================
    # 6. ПОСТРОЕНИЕ КОНТЕКСТА
    # ============================================================

    def _build_context(self, request: GenerateRequest, strategy: str) -> dict[str, Any]:
        """
        Формирует контекст для отправки в DeepSeek.

        Структура контекста:
        1. Системный промпт
        2. История (в зависимости от стратегии)
        3. Файлы из начала истории (для гибкой стратегии)
        4. Файлы из текущего запроса
        5. Запрос пользователя
        """
        messages = []

        # 1. Системный промпт (всегда от фронта)
        system_prompt = self._get_system_prompt(request)
        messages.append({"role": "system", "content": system_prompt})

        # 2. История в зависимости от стратегии
        history_messages = self._get_history_messages(strategy)

        for msg in history_messages:
            if msg.role == "assistant":
                # Восстанавливаем полный код для сообщений ассистента
                content = self._restore_full_content(msg)
            else:
                content = msg.content
            messages.append({"role": msg.role, "content": content})

        # 3. Файлы из начала истории (только для гибкой стратегии)
        if strategy == "flexible":
            history_files = self._get_history_start_files()
            if history_files:
                files_content = ""
                for f in history_files:
                    files_content += f"--- {f.filename} ---\n{f.content}\n\n"
                messages.append(
                    {
                        "role": "user",
                        "content": f"Файлы из начала истории:\n{files_content}",
                    }
                )

        # 4. Файлы из текущего запроса
        if request.selected_files:
            files_content = ""
            for filename in request.selected_files:
                version = (
                    self.db.query(FileVersion)
                    .filter(
                        FileVersion.chat_id == self.chat_id,
                        FileVersion.filename == filename,
                        FileVersion.is_current == True,
                    )
                    .first()
                )
                if version:
                    files_content += (
                        f"--- {version.filename} ---\n{version.content}\n\n"
                    )

            if files_content:
                messages.append(
                    {
                        "role": "user",
                        "content": f"Текущие файлы проекта:\n{files_content}",
                    }
                )

        # 5. Запрос пользователя
        messages.append({"role": "user", "content": request.query})

        # Подсчёт токенов
        total_tokens = sum(count_tokens(msg["content"]) for msg in messages)

        return {"messages": messages, "total_tokens": total_tokens}

    # ============================================================
    # 7. СОХРАНЕНИЕ СООБЩЕНИЯ С КОНТЕКСТОМ
    # ============================================================

    def _save_user_message(self, request: GenerateRequest, context: dict) -> Message:
        """
        Сохраняет сообщение пользователя с контекстными данными.

        В context_data сохраняются:
        - selected_files: имена приложенных файлов
        - file_version_ids: ID версий приложенных файлов
        - strategy: стратегия генерации
        """
        # Собираем ID версий приложенных файлов
        file_version_ids = []
        if request.selected_files:
            for filename in request.selected_files:
                version = (
                    self.db.query(FileVersion)
                    .filter(
                        FileVersion.chat_id == self.chat_id,
                        FileVersion.filename == filename,
                        FileVersion.is_current == True,
                    )
                    .first()
                )
                if version:
                    file_version_ids.append(version.id)

        user_message = Message(
            chat_id=self.chat_id,
            role="user",
            content=request.query,
            input_tokens=context["total_tokens"],
            context_data={
                "selected_files": request.selected_files or [],
                "file_version_ids": file_version_ids,
                "strategy": request.strategy or self._get_chat_strategy(),
                "model": request.model or "flash",
                "temperature": request.temperature or settings.DEFAULT_TEMPERATURE,
            },
        )
        self.db.add(user_message)
        self.db.flush()

        return user_message

    # ============================================================
    # 8. ФОРМИРОВАНИЕ СООБЩЕНИЯ ДЛЯ ПОЛЬЗОВАТЕЛЯ
    # ============================================================

    def _build_message_with_markers(self, text: str, file_ids: list[dict]) -> str:
        # Создаёт сообщение для пользователя с маркерами и плейсхолдерами
        # Формат:
        # ### FILE: filename.ext
        # ```language
        # [здесь был код, сгенерированный нейросетью, ID: 177]
        # ```
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

    # ============================================================
    # 9. ОСНОВНОЙ МЕТОД ГЕНЕРАЦИИ
    # ============================================================

    async def generate_stream(
        self, request: GenerateRequest, max_tokens: int = 8192, use_stream: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Основной метод генерации с возвратом SSE стрима.

        Этапы:
        1. Создание task_id для управления генерацией
        2. Формирование контекста согласно стратегии
        3. Сохранение сообщения пользователя
        4. Отправка запроса в DeepSeek
        5. Обработка завершения (полное / обрезанное)
        6. Парсинг ответа
        7. Сохранение файлов
        8. Обновление статистики
        9. Создание снимка состояния
        """
        task_id = None

        try:
            # 1. Создаём task_id для управления генерацией
            current_task = asyncio.current_task()
            task_id = generation_manager.create_task(self.chat_id, current_task)

            # Отправляем task_id клиенту
            yield f"data: {json.dumps({'task_id': task_id, 'status': 'started'})}\n\n"

            # 2. Определяем стратегию
            strategy = request.strategy or self._get_chat_strategy()
            logger.info(f"Используется стратегия: {strategy}")

            # 3. Формируем контекст
            context = self._build_context(request, strategy)
            self._log_request_context(request, context)

            # 4. Сохраняем сообщение пользователя с контекстом
            user_message = self._save_user_message(request, context)

            # 5. Отправляем запрос в DeepSeek
            full_response = ""
            input_tokens = context["total_tokens"]
            output_tokens = 0

            buffer = ""
            BUFFER_SIZE = 50
            chunk_count = 0
            finish_reason = None

            # 6. Стримим ответ
            async for chunk_data in self.client.generate(
                messages=context["messages"],
                model=request.model or "flash",
                temperature=request.temperature or settings.DEFAULT_TEMPERATURE,
                max_tokens=max_tokens,
                stream=use_stream,
            ):
                # Проверяем, не отменена ли задача
                if generation_manager.is_cancelled(task_id):
                    logger.info(f"Генерация {task_id} отменена пользователем")
                    yield f"data: {json.dumps({'status': 'cancelled', 'done': True})}\n\n"
                    return

                # Если пришёл словарь с finish_reason (от клиента)
                if isinstance(chunk_data, dict):
                    finish_reason = chunk_data.get("finish_reason")
                    continue

                # Обычный чанк с контентом
                if chunk_data:
                    chunk_count += 1
                    full_response += chunk_data
                    output_tokens += len(chunk_data.split())
                    buffer += chunk_data

                    if len(buffer) >= BUFFER_SIZE:
                        yield f"data: {json.dumps({'content': buffer, 'done': False})}\n\n"
                        buffer = ""
                        await asyncio.sleep(0.005)

            if buffer:
                yield f"data: {json.dumps({'content': buffer, 'done': False})}\n\n"

            # 7. Проверяем отмену
            if generation_manager.is_cancelled(task_id):
                logger.info(f"Генерация {task_id} отменена перед сохранением")
                yield f"data: {json.dumps({'status': 'cancelled', 'done': True})}\n\n"
                return

            # 8. Проверяем причину завершения
            if finish_reason == "length":
                # Достигнут лимит токенов — сохраняем как неполное сообщение
                logger.warning(
                    f"Достигнут лимит токенов ({max_tokens}). Ответ обрезан."
                )

                # Создаём неполное сообщение
                assistant_message = Message(
                    chat_id=self.chat_id,
                    role="assistant",
                    content="",  # Заполним позже
                    is_complete=False,
                    partial_content=full_response,  # Сырой нераспарсенный ответ
                    context_data={
                        "query": request.query,
                        "selected_files": request.selected_files or [],
                        "system_prompt_id": request.system_prompt_id,
                        "model": request.model or "flash",
                        "temperature": request.temperature,
                        "max_tokens": max_tokens,
                        "strategy": strategy,
                    },
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                    cost=calculate_cost(
                        input_tokens, output_tokens, request.model or "flash"
                    ),
                )
                self.db.add(assistant_message)
                self.db.flush()

                message_id = assistant_message.id
                logger.info(f"Создано НЕПОЛНОЕ сообщение ассистента (ID: {message_id})")

                # Формируем content с маркерами (плейсхолдеры будут позже, когда до генерятся файлы)
                # Пока сохраняем сырой ответ как есть
                assistant_message.content = full_response
                self.db.commit()

                # Отправляем клиенту информацию о том, что ответ обрезан
                yield f"data: {
                    json.dumps(
                        {
                            'done': False,
                            'has_more': True,
                            'message_id': message_id,
                            'task_id': task_id,
                            'finish_reason': 'length',
                            'message': 'Достигнут лимит генерации. Нажмите Продолжить, чтобы завершить.',
                        }
                    )
                }\n\n"

                # Возвращаемся, не завершая генерацию
                return

            # 9. Проверяем ответ (полный)
            if not full_response.strip():
                logger.warning("Пустой ответ от ИИ")
                yield f"data: {json.dumps({'error': 'Пустой ответ от ИИ'})}\n\n"
                return

            # 10. Проверяем закрытие маркеров
            if "```" in full_response and full_response.count("```") % 2 != 0:
                logger.warning(
                    "Обнаружен незакрытый маркер кода. Добавляем завершение."
                )
                full_response += "\n```\n"

            # 11. Логируем сырой ответ
            logger.info("=" * 80)
            logger.info("СЫРОЙ ОТВЕТ ОТ НЕЙРОСЕТИ")
            logger.info("=" * 80)
            logger.info(f"Длина ответа: {len(full_response)} символов")
            logger.info(f"Количество чанков: {chunk_count}")
            logger.info(f"Содержимое:\n{full_response}")
            logger.info("=" * 80)

            # 12. Парсим ответ
            logger.info("Парсинг ответа...")
            text, files = parse_ai_response(full_response)

            logger.info("Результат парсинга:")
            logger.info(f"  - Текст: {len(text)} символов")
            logger.info(f"  - Найдено файлов: {len(files)}")
            for f in files:
                logger.info(
                    f"    - {f.get('type', 'unknown')}: {f.get('filename', 'без имени')} ({len(f.get('content', ''))} символов)"
                )

            # 13. Проверяем отмену перед сохранением в БД
            if generation_manager.is_cancelled(task_id):
                logger.info(f"Генерация {task_id} отменена перед сохранением в БД")
                yield f"data: {json.dumps({'status': 'cancelled', 'done': True})}\n\n"
                return

            # 14. Создаём полное сообщение ассистента
            assistant_message = Message(
                chat_id=self.chat_id,
                role="assistant",
                content="",  # Заполним позже
                is_complete=True,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                cost=calculate_cost(
                    input_tokens, output_tokens, request.model or "flash"
                ),
            )
            self.db.add(assistant_message)
            self.db.flush()

            message_id = assistant_message.id
            logger.info(f"Сообщение ассистента создано (ID: {message_id})")

            # 15. Сохраняем файлы
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
                        applied=False,
                    )
                    self.db.add(file_version)
                    self.db.flush()
                    file_ids.append(
                        {
                            "id": file_version.id,
                            "filename": file_data["filename"],
                            "language": file_data["language"],
                        }
                    )
                    logger.info(
                        f"Файл сохранён в БД: {file_data['filename']} (ID: {file_version.id})"
                    )

            # 16. Формируем content для пользователя (с плейсхолдерами)
            content_with_markers = self._build_message_with_markers(text, file_ids)
            assistant_message.content = content_with_markers
            self.db.commit()

            # 17. Обновляем статистику проекта
            project = (
                self.db.query(Project).filter(Project.id == self.project_id).first()
            )
            if project:
                project.total_input_tokens = (
                    project.total_input_tokens or 0
                ) + input_tokens
                project.total_output_tokens = (
                    project.total_output_tokens or 0
                ) + output_tokens
                project.total_cost = float(project.total_cost or 0.0) + float(
                    assistant_message.cost or 0.0
                )

            # 18. Обновляем статистику чата
            chat = self.db.query(Chat).filter(Chat.id == self.chat_id).first()
            if chat:
                chat.total_input_tokens = (chat.total_input_tokens or 0) + input_tokens
                chat.total_output_tokens = (
                    chat.total_output_tokens or 0
                ) + output_tokens
                chat.total_cost = float(chat.total_cost or 0.0) + float(
                    assistant_message.cost or 0.0
                )

            # 19. Создаём снимок
            manifest = {}
            current_files = (
                self.db.query(FileVersion)
                .filter(
                    FileVersion.chat_id == self.chat_id, FileVersion.is_current == True
                )
                .all()
            )
            for version in current_files:
                manifest[version.filename] = version.content_hash or ""

            SnapshotService.create(
                db=self.db,
                project_id=self.project_id,
                snapshot_type="apply",
                level=2,
                name=f"Генерация #{message_id}",
            )

            self.db.commit()

            # 20. Отправляем файлы клиенту
            for file_data in files:
                if file_data["type"] == "file":
                    yield f"data: {json.dumps({'file': {'filename': file_data['filename'], 'content': file_data['content']}})}\n\n"

            # 21. Финальное событие
            yield f"data: {json.dumps({'done': True, 'message_id': message_id})}\n\n"

            logger.info(f"Генерация #{message_id} завершена успешно")

        except asyncio.CancelledError:
            logger.info(f"Генерация {task_id} отменена")
            yield f"data: {json.dumps({'status': 'cancelled'})}\n\n"
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Ошибка генерации: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            if task_id:
                generation_manager.remove_task(task_id)

    # ============================================================
    # 10. ПРОДОЛЖЕНИЕ ГЕНЕРАЦИИ
    # ============================================================

    async def continue_stream(
        self,
        message_id: int,
        request: GenerateRequest,
        max_tokens: int = 8192,
        use_stream: bool = True,
    ) -> AsyncGenerator[str, None]:
        """
        Продолжает обрезанную генерацию.

        Берёт неполное сообщение, восстанавливает контекст и продолжает генерацию.
        """
        try:
            # 1. Находим неполное сообщение
            assistant_message = (
                self.db.query(Message)
                .filter(Message.id == message_id, Message.is_complete == False)
                .first()
            )

            if not assistant_message:
                yield f"data: {json.dumps({'error': 'Неполное сообщение не найдено'})}\n\n"
                return

            # 2. Восстанавливаем контекст из сообщения
            context_data = assistant_message.context_data
            if not context_data:
                yield f"data: {json.dumps({'error': 'Контекст для продолжения не найден'})}\n\n"
                return

            # 3. Формируем запрос на продолжение
            continue_request = GenerateRequest(
                query=context_data.get("query", "Продолжи генерацию"),
                selected_files=context_data.get("selected_files", []),
                system_prompt_id=context_data.get("system_prompt_id"),
                model=context_data.get("model", "flash"),
                temperature=context_data.get("temperature", 0.7),
                max_tokens=max_tokens,
            )

            # 4. Получаем стратегию
            strategy = context_data.get("strategy", "flexible")

            # 5. Формируем контекст
            context = self._build_context(continue_request, strategy)

            # 6. Добавляем инструкцию для продолжения
            partial_content = assistant_message.partial_content or ""
            context["messages"].append(
                {
                    "role": "user",
                    "content": f"Продолжи с того места, где остановился. Не повторяй уже сгенерированный код.\n\nТекущий частичный ответ:\n{partial_content}",
                }
            )

            # 7. Обновляем токены
            input_tokens = context["total_tokens"] + count_tokens(partial_content)

            # 8. Запускаем генерацию
            full_response = partial_content
            output_tokens = 0
            chunk_count = 0
            buffer = ""
            BUFFER_SIZE = 50
            finish_reason = None

            async for chunk_data in self.client.generate(
                messages=context["messages"],
                model=continue_request.model or "flash",
                temperature=continue_request.temperature
                or settings.DEFAULT_TEMPERATURE,
                max_tokens=max_tokens,
                stream=use_stream,
            ):
                if isinstance(chunk_data, dict):
                    finish_reason = chunk_data.get("finish_reason")
                    continue

                if chunk_data:
                    chunk_count += 1
                    full_response += chunk_data
                    output_tokens += len(chunk_data.split())
                    buffer += chunk_data

                    if len(buffer) >= BUFFER_SIZE:
                        yield f"data: {json.dumps({'content': buffer, 'done': False})}\n\n"
                        buffer = ""
                        await asyncio.sleep(0.005)

            if buffer:
                yield f"data: {json.dumps({'content': buffer, 'done': False})}\n\n"

            # 9. Проверяем завершение
            if finish_reason == "length":
                # Снова обрезано — обновляем partial_content
                assistant_message.partial_content = full_response
                assistant_message.output_tokens = output_tokens
                assistant_message.total_tokens = input_tokens + output_tokens
                assistant_message.cost = calculate_cost(
                    input_tokens, output_tokens, continue_request.model or "flash"
                )
                self.db.commit()

                yield f"data: {
                    json.dumps(
                        {
                            'done': False,
                            'has_more': True,
                            'message_id': message_id,
                            'finish_reason': 'length',
                            'message': 'Снова достигнут лимит. Продолжите ещё раз.',
                        }
                    )
                }\n\n"
                return

            # 10. Полный ответ — парсим и сохраняем
            if "```" in full_response and full_response.count("```") % 2 != 0:
                full_response += "\n```\n"

            text, files = parse_ai_response(full_response)

            # 11. Сохраняем файлы
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
                        applied=False,
                    )
                    self.db.add(file_version)
                    self.db.flush()
                    file_ids.append(
                        {
                            "id": file_version.id,
                            "filename": file_data["filename"],
                            "language": file_data["language"],
                        }
                    )
                    logger.info(
                        f"Файл сохранён в БД: {file_data['filename']} (ID: {file_version.id})"
                    )

            # 12. Обновляем сообщение
            content_with_markers = self._build_message_with_markers(text, file_ids)
            assistant_message.content = content_with_markers
            assistant_message.is_complete = True
            assistant_message.partial_content = None
            assistant_message.output_tokens = output_tokens
            assistant_message.total_tokens = input_tokens + output_tokens
            assistant_message.cost = calculate_cost(
                input_tokens, output_tokens, continue_request.model or "flash"
            )
            self.db.commit()

            # 13. Отправляем файлы клиенту
            for file_data in files:
                if file_data["type"] == "file":
                    yield f"data: {json.dumps({'file': {'filename': file_data['filename'], 'content': file_data['content']}})}\n\n"

            # 14. Финальное событие
            yield f"data: {json.dumps({'done': True, 'message_id': message_id})}\n\n"

            logger.info(f"Продолжение генерации #{message_id} завершено успешно")

        except Exception as e:
            self.db.rollback()
            logger.error(f"Ошибка продолжения генерации: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    # ============================================================
    # 11. ЛОГИРОВАНИЕ
    # ============================================================

    def _log_request_context(self, request: GenerateRequest, context: dict) -> None:
        """Логирует данные, отправляемые в ИИ."""
        logger.info("=" * 80)
        logger.info("ОТПРАВКА ЗАПРОСА В ИИ")
        logger.info("=" * 80)
        logger.info(f"Chat ID: {self.chat_id}")
        logger.info(f"Project ID: {self.project_id}")
        logger.info(f"Модель: {request.model or 'flash'}")
        logger.info(
            f"Температура: {request.temperature or settings.DEFAULT_TEMPERATURE}"
        )
        logger.info(f"Всего токенов в контексте: {context['total_tokens']}")
        logger.info(f"system_prompt_id: {request.system_prompt_id}")
        logger.info(f"Стратегия: {request.strategy or self._get_chat_strategy()}")
        logger.info(
            f"Приложено файлов: {len(request.selected_files) if request.selected_files else 0}"
        )
        logger.info("=" * 80)
