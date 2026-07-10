import json
from typing import AsyncGenerator, Optional, List, Dict
import httpx
import logging
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.exceptions import DeepSeekAPIError

logger = logging.getLogger(__name__)


class DeepSeekClient:

    def __init__(self):
        if not settings.DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY не задан в переменных окружения")

        logger.info("Инициализация DeepSeek клиента")
        logger.info(f"Base URL: {settings.DEEPSEEK_BASE_URL}")

        self.client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            timeout=httpx.Timeout(60.0, read=180.0)
        )

    def _get_model(self, model: str = "flash") -> str:
        if model == "pro":
            return settings.DEEPSEEK_MODEL_PRO
        return settings.DEEPSEEK_MODEL_FLASH

    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: str = "flash",
        temperature: float = 0.7,
        max_tokens: int = 8192,
        stream: bool = True
    ) -> AsyncGenerator[str, None]:
        try:
            model_name = self._get_model(model)
            logger.info(f"Запрос к DeepSeek. Модель: {model_name}, max_tokens: {max_tokens}, stream: {stream}")
            logger.info(f"Сообщений: {len(messages)}")

            response = await self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )

            if stream:
                full_content = ""
                chunk_count = 0
                
                async for chunk in response:
                    if chunk.choices:
                        choice = chunk.choices[0]
                        chunk_count += 1
                        
                        if choice.finish_reason:
                            logger.info(f"Finish reason: {choice.finish_reason} (получено чанков: {chunk_count})")
                            
                            if choice.finish_reason == "stop":
                                logger.info("Генерация завершена штатно")
                            elif choice.finish_reason == "length":
                                logger.warning(f"Достигнут max_tokens ({max_tokens})")
                            elif choice.finish_reason == "content_filter":
                                logger.error("Сработал фильтр контента")
                            else:
                                logger.warning(f"Неизвестный finish_reason: {choice.finish_reason}")
                        
                        if choice.delta and choice.delta.content:
                            content = choice.delta.content
                            full_content += content
                            yield content
                        
                        elif not choice.finish_reason:
                            logger.debug(f"Получен пустой чанк #{chunk_count}, ждём...")
                            continue
                
                if not full_content:
                    logger.warning("Получен пустой ответ от DeepSeek")
                    yield ""
                    
            else:
                content = response.choices[0].message.content
                if content:
                    yield content
                else:
                    logger.warning("Получен пустой ответ от DeepSeek")
                    yield ""

        except Exception as e:
            logger.error(f"Ошибка DeepSeek API: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise DeepSeekAPIError(detail=str(e))
