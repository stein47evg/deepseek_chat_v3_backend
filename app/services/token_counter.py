"""
Подсчёт токенов с использованием tiktoken.
"""
import tiktoken
from typing import List, Dict


def count_tokens(text: str) -> int:
    """
    Подсчитывает количество токенов в тексте.
    Использует токенизатор, совместимый с GPT-4 (DeepSeek).
    
    Аргументы:
        text: Текст для подсчёта
    Возвращает:
        Количество токенов
    """
    encoding = tiktoken.encoding_for_model("gpt-4")
    return len(encoding.encode(text))


def count_messages_tokens(messages: List[Dict[str, str]]) -> int:
    """
    Подсчитывает общее количество токенов в списке сообщений.
    
    Аргументы:
        messages: Список сообщений в формате OpenAI
    Возвращает:
        Общее количество токенов
    """
    total = 0
    for msg in messages:
        total += count_tokens(msg.get("content", ""))
        # Добавляем служебные токены для ролей (приблизительно)
        total += 4
    return total


def calculate_cost(input_tokens: int, output_tokens: int, model: str = "flash") -> float:
    """
    Рассчитывает стоимость запроса на основе цен DeepSeek.
    
    Аргументы:
        input_tokens: Количество входных токенов
        output_tokens: Количество выходных токенов
        model: "flash" или "pro"
    Возвращает:
        Стоимость в USD
    """
    prices = {
        "flash": {"input": 0.14, "output": 0.28},
        "pro": {"input": 0.435, "output": 0.87}
    }

    p = prices.get(model, prices["flash"])

    cost = (input_tokens / 1_000_000) * p["input"] + \
           (output_tokens / 1_000_000) * p["output"]

    return round(cost, 6)
