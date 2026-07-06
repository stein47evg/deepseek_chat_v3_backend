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

        logger.info(f"Инициализация DeepSeek клиента")
        logger.info(f"Base URL: {settings.DEEPSEEK_BASE_URL}")

        self.client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            timeout=httpx.Timeout(60.0, read=120.0)
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
        max_tokens: int = 4096,
        stream: bool = True
    ) -> AsyncGenerator[str, None]:
        try:
            model_name = self._get_model(model)
            logger.info(f"Отправка запроса к DeepSeek. Модель: {model_name}")
            logger.info(f"Сообщений: {len(messages)}")

            response = await self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )

            if stream:
                async for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            else:
                yield response.choices[0].message.content

        except Exception as e:
            logger.error(f"Ошибка DeepSeek API: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise DeepSeekAPIError(detail=str(e))
