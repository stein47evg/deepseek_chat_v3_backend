# Тесты для подсчёта токенов.
import pytest
from app.services.token_counter import count_tokens, calculate_cost


class TestTokenCounter:
    # Тесты подсчёта токенов.

    def test_count_tokens_simple(self):
        # Подсчёт токенов для простого текста.
        text = "Hello world"
        tokens = count_tokens(text)
        assert tokens > 0

    def test_count_tokens_russian(self):
        # Подсчёт токенов для русского текста.
        text = "Привет мир"
        tokens = count_tokens(text)
        assert tokens > 0

    def test_count_tokens_empty(self):
        # Подсчёт токенов для пустого текста.
        tokens = count_tokens("")
        assert tokens == 0

    def test_calculate_cost_flash(self):
        # Расчёт стоимости для flash модели.
        cost = calculate_cost(1000, 500, "flash")
        assert cost > 0
        assert cost < 0.01

    def test_calculate_cost_pro(self):
        # Расчёт стоимости для pro модели.
        cost = calculate_cost(1000, 500, "pro")
        assert cost > 0
        assert cost > calculate_cost(1000, 500, "flash")
