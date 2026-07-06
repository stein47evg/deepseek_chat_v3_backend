#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Базовый класс для всех плагинов
"""

from abc import ABC, abstractmethod


class BasePlugin(ABC):
    """Абстрактный базовый класс для плагинов"""

    def __init__(self):
        self.name = self.__class__.__name__
        self.enabled = True

    @abstractmethod
    def execute(self, *args, **kwargs):
        """Основной метод выполнения плагина"""
        pass

    @abstractmethod
    def get_info(self):
        """Возвращает информацию о плагине"""
        pass

    def get_menu_items(self):
        """
        Возвращает список пунктов меню для плагина.
        Каждый пункт - словарь с ключами:
            - icon: иконка (строка)
            - name: название (строка)
            - args: аргументы для execute() (словарь)
        По умолчанию возвращает пустой список.
        """
        return []

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def is_enabled(self):
        return self.enabled
