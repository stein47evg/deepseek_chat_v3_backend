#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Плагин для применения патчей к файлам проекта.
Полностью автономный, не зависит от main.py.

Синтаксис патча:
    === Файл: путь/к/файлу ===
    + N          - вставить содержимое перед строкой N
    - N-M        - удалить строки с N по M
    - N:K        - удалить K строк начиная с N
    ~ N-M        - заменить строки с N по M на содержимое
    ~ N          - заменить строку N на содержимое
    >            - вставить содержимое в конец файла

Особенности:
    - Содержимое должно начинаться с пробела (служебный символ)
    - Комментарии начинаются с # и игнорируются
    - Поддерживается несколько файлов в одном патче
    - Двухпроходное применение: сначала проверка (dry-run), потом сохранение
"""

import os
import sys
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime
import platform

# ============================================================================
# НАСТРОЙКА КОДИРОВКИ ДЛЯ WINDOWS
# ============================================================================

if platform.system() == "Windows":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    os.system('chcp 65001 > nul 2>&1')

# ============================================================================
# ПОДКЛЮЧЕНИЕ БАЗОВОГО КЛАССА ПЛАГИНА
# ============================================================================

try:
    from plugins.base_plugin import BasePlugin
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from plugins.base_plugin import BasePlugin


# ============================================================================
# ЦВЕТА ДЛЯ ВЫВОДА
# ============================================================================

class Colors:
    """Цвета для красивого вывода в консоль"""
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


class Icons:
    """Иконки для вывода в консоль"""
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    ARROW = "👉"
    EXIT = "🚪"


# ============================================================================
# СТРУКТУРА ДЛЯ ОШИБОК С УКАЗАНИЕМ МЕСТА
# ============================================================================

class PatchError:
    """
    Представление ошибки с кодом и указанием места в патче.
    """
    
    ERROR_MESSAGES = {
        'E001': "Номер строки '{value}' должен быть целым положительным числом",
        'E002': "Отсутствует номер строки для команды '{command}'",
        'E003': "Номер строки не может быть отрицательным: {value}",
        'E004': "Начало диапазона ({start}) больше конца ({end})",
        'E005': "Диапазон не может содержать 0 строк",
        'E006': "Количество строк '{value}' должно быть числом",
        'E007': "Некорректный разделитель диапазона. Используйте '-' или ':'",
        'E008': "Неизвестная команда '{command}'. Допустимые: +, -, ~, >",
        'E009': "Команда '>' не должна содержать номер строки",
        'E010': "Команда '-' не поддерживает содержимое",
        'E011': "Команда '+' требует содержимого на следующей строке",
        'E012': "Команда '~' требует содержимого на следующей строке",
        'E013': "Команда '>' требует содержимого на следующей строке",
        'E014': "Строка содержимого не связана ни с одной командой: '{content}'",
        'E015': "Незакрытый блок содержимого для команды '{command}'",
        'E016': "Ожидается '=== Файл: путь/к/файлу ==='",
        'E017': "Каждый файл должен начинаться с маркера '=== Файл: ... ==='",
        'E018': "Файл патча не содержит операций",
        'E019': "Комментарий не может быть пустым",
        'E020': "Строка {num} не существует в файле {file}",
        'E021': "Строка {num} уже удалена",
        'E022': "Строка {num} уже заменена",
        'E023': "Нельзя удалить строку {num}, так как она была заменена",
        'E024': "Нельзя вставить перед строкой {num}, так как она удалена",
        'E025': "Диапазон {start}-{end} выходит за границы файла (всего {total} строк)",
        'E026': "Диапазоны {start1}-{end1} и {start2}-{end2} перекрываются",
        'E027': "Команда '{action}' требует номер строки",
        'E028': "Файл не найден: {file}",
        'E029': "Ошибка кодировки файла {file}. Ожидается UTF-8",
        'E030': "Нет прав на запись: {file}",
        'E031': "Файл патча не найден: {file}",
        'E032': "Ошибка чтения файла патча: {error}",
        'E033': "Ошибка сохранения {file}: {error}",
    }
    
    def __init__(self, code: str, message: str = "", file: str = "", 
                 line_num: int = 0, line_content: str = "", **kwargs):
        self.code = code
        if not message:
            template = self.ERROR_MESSAGES.get(code, "Неизвестная ошибка")
            self.message = template.format(**kwargs) if kwargs else template
        else:
            self.message = message
        self.file = file
        self.line_num = line_num
        self.line_content = line_content
        self.kwargs = kwargs
    
    def __str__(self):
        result = []
        if self.file and self.line_num:
            result.append(f"{self.file}:{self.line_num}")
        elif self.line_num:
            result.append(f"Строка {self.line_num}")
        
        if self.line_content:
            result.append(f"{self.line_num}|{self.line_content}")
        
        if self.line_content:
            indent = len(str(self.line_num)) + 1
            result.append(" " * indent + f"^ {self.code}: {self.message}")
        else:
            result.append(f"   ^ {self.code}: {self.message}")
        
        return "\n".join(result)


# ============================================================================
# СТРУКТУРА ДАННЫХ: СТРОКА ФАЙЛА
# ============================================================================

class Line:
    """Представление строки файла с двойной нумерацией"""
    
    def __init__(self, original_num: Optional[int], content: str):
        self.original_num = original_num
        self.current_num = original_num
        self.content = content.rstrip('\n')
    
    def __repr__(self):
        orig = f"{self.original_num:3d}" if self.original_num is not None else "---"
        curr = f"{self.current_num:3d}" if self.current_num is not None else "---"
        return f"[{orig}->{curr}] {self.content[:30]}"


# ============================================================================
# СТРУКТУРА ДАННЫХ: ОПЕРАЦИЯ ПАТЧА
# ============================================================================

class PatchOperation:
    """Представление одной макрокоманды патча"""
    
    def __init__(self, action: str, original_num: Optional[int], content: str = "", 
                 range_end: Optional[int] = None, source_line: int = 0):
        self.action = action
        self.original_num = original_num
        self.content = content
        self.range_end = range_end
        self.is_range = range_end is not None
        self.source_line = source_line
    
    def __repr__(self):
        if self.is_range:
            return f"{self.action} {self.original_num}-{self.range_end}"
        return f"{self.action} {self.original_num}"


# ============================================================================
# ПАРСЕР ПАТЧ-ФАЙЛА
# ============================================================================

class PatchParser:
    """Парсер файла патча"""
    
    def __init__(self):
        self.errors: List[PatchError] = []
        self.warnings: List[PatchError] = []
        self.current_file = ""
        self._line_processed = False  # флаг, что строка уже обработана как команда
    
    def add_error(self, code: str, line_num: int = 0, 
                  line_content: str = "", **kwargs):
        self.errors.append(PatchError(
            code=code,
            file=self.current_file,
            line_num=line_num,
            line_content=line_content,
            **kwargs
        ))
    
    def add_warning(self, code: str, line_num: int = 0, 
                    line_content: str = "", **kwargs):
        self.warnings.append(PatchError(
            code=code,
            file=self.current_file,
            line_num=line_num,
            line_content=line_content,
            **kwargs
        ))
    
    def normalize_command(self, line: str) -> str:
        """Нормализует строку команды, удаляя лишние пробелы."""
        result = []
        for char in line:
            if char in '+->~:':
                result.append(char)
            elif char.isdigit():
                result.append(char)
        return ''.join(result)
    
    def parse_command(self, line: str, line_num: int) -> Optional[Tuple[str, Optional[int], Optional[int]]]:
        """
        Парсит строку команды.
        Возвращает (action, num, extra) или None.
        Устанавливает self._line_processed = True если строка является командой.
        """
        self._line_processed = False
        line = line.strip()
        
        # Команда > (вставка в конец)
        if line == '>':
            self._line_processed = True
            return ('>', None, None)
        
        normalized = self.normalize_command(line)
        
        # Проверяем на команду с диапазоном: -7-12
        match = re.match(r'^([+~-])(\d+)-(\d+)$', normalized)
        if match:
            action = match.group(1)
            start = int(match.group(2))
            end = int(match.group(3))
            if start > end:
                self.add_error('E004', line_num, line, start=start, end=end)
                return None
            self._line_processed = True
            return (action, start, end)
        
        # Проверяем на команду с количеством: +10:3
        match = re.match(r'^([+~-])(\d+):(\d+)$', normalized)
        if match:
            action = match.group(1)
            num = int(match.group(2))
            count = int(match.group(3))
            if count <= 0:
                self.add_error('E005', line_num, line)
                return None
            # Проверяем, что количество — число
            if not str(count).isdigit():
                self.add_error('E006', line_num, line, value=count)
                return None
            self._line_processed = True
            return (action, num, count)
        
        # Проверяем на простую команду: -10
        match = re.match(r'^([+~-])(\d+)$', normalized)
        if match:
            action = match.group(1)
            num = int(match.group(2))
            if num < 1:
                self.add_error('E003', line_num, line, value=num)
                return None
            self._line_processed = True
            return (action, num, 1)
        
        # Проверяем на команду с буквой вместо числа
        match = re.match(r'^([+~-])([a-zA-Z]+)$', normalized)
        if match:
            action = match.group(1)
            value = match.group(2)
            self.add_error('E001', line_num, line, value=value)
            self._line_processed = True
            return None
        
        # Проверяем на команду без номера (кроме >)
        match = re.match(r'^([+~-])$', normalized)
        if match:
            action = match.group(1)
            self.add_error('E002', line_num, line, command=action)
            self._line_processed = True
            return None
        
        # Проверяем на команду > с номером
        match = re.match(r'^>(\d+)$', normalized)
        if match:
            self.add_error('E009', line_num, line)
            self._line_processed = True
            return None
        
        # Проверяем на неизвестную команду
        if re.match(r'^[^+\-~>\s#]', line):
            cmd_match = re.match(r'^([^+\-~>\s#]+)', line)
            if cmd_match:
                self.add_error('E008', line_num, line, command=cmd_match.group(1))
            else:
                self.add_error('E008', line_num, line, command=line[:1])
            self._line_processed = True
            return None
        
        return None
    
    def parse(self, patch_file: str) -> Dict[str, List[PatchOperation]]:
        """Парсит файл патча и возвращает словарь {file_path: [макрокоманды]}."""
        self.current_file = patch_file
        
        if not os.path.exists(patch_file):
            self.add_error('E031', file=patch_file)
            return {}
        
        try:
            with open(patch_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            self.add_error('E032', error=str(e))
            return {}
        
        result = {}
        current_file = None
        current_ops = []
        pending_action = None
        pending_num = None
        pending_range_end = None
        pending_content = []
        pending_line = 0
        has_operations = False
        in_content = False  # флаг, что мы внутри блока содержимого
        
        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            line_num = i + 1
            
            # Пропускаем пустые строки (между командами)
            if not line.strip():
                i += 1
                continue
            
            # Проверяем на комментарий
            if line.lstrip().startswith('#'):
                if line.strip() == '#':
                    self.add_warning('E019', line_num, line)
                i += 1
                continue
            
            # Проверяем маркер файла
            file_match = re.match(r'^=== Файл:\s*(.+?)\s*===', line)
            if file_match:
                if current_file and current_ops:
                    result[current_file] = current_ops
                
                current_file = file_match.group(1).strip()
                current_ops = []
                pending_action = None
                pending_content = []
                in_content = False
                has_operations = False
                i += 1
                continue
            
            # Если нет маркера файла — ошибка
            if not current_file:
                self.add_error('E017', line_num, line)
                i += 1
                continue
            
            # Проверяем, является ли строка командой
            cmd = self.parse_command(line, line_num)
            if cmd:
                # Если была ожидающая команда — сохраняем её
                if pending_action:
                    self._save_pending_command(current_ops, pending_action, pending_num, 
                                              pending_range_end, pending_content, pending_line)
                    pending_content = []
                    in_content = False
                
                # Начинаем новую команду
                action, num, extra = cmd
                pending_action = action
                pending_num = num
                pending_range_end = extra if action in ['-', '~'] else None
                pending_content = []
                pending_line = line_num
                in_content = True
                has_operations = True
                i += 1
                continue
            
            # Если строка уже была обработана как команда — пропускаем
            if self._line_processed:
                i += 1
                continue
            
            # Если строка начинается с пробела — это содержимое
            if line.startswith(' '):
                if pending_action and in_content:
                    pending_content.append(line[1:])  # удаляем служебный пробел
                else:
                    self.add_error('E014', line_num, line, content=line)
                i += 1
                continue
            
            # Если ничего не подошло — ошибка
            self.add_error('E014', line_num, line, content=line)
            i += 1
        
        # Сохраняем последнюю ожидающую команду
        if pending_action and in_content:
            self._save_pending_command(current_ops, pending_action, pending_num,
                                      pending_range_end, pending_content, pending_line)
        
        # Сохраняем последний файл
        if current_file and current_ops:
            result[current_file] = current_ops
        
        if not result and not self.errors:
            self.add_error('E018')
        
        return result
    
    def _save_pending_command(self, ops: List[PatchOperation], action: str, 
                              num: Optional[int], range_end: Optional[int], 
                              content: List[str], line_num: int):
        """Сохраняет накопленную макрокоманду."""
        # Для команд +, ~ и > нужно содержимое
        if action in ['+', '~', '>'] and not content:
            if action == '>':
                self.add_error('E013', line_num, f">{num if num else ''}" if num else ">")
            else:
                cmd_str = f"{action}{num}" if num else action
                if action == '+':
                    self.add_error('E011', line_num, cmd_str)
                elif action == '~':
                    self.add_error('E012', line_num, cmd_str)
            return
        
        # Для команды - содержимое не допускается
        if action == '-' and content:
            self.add_error('E010', line_num, f"- {num}")
            return
        
        # Для команды > не должно быть номера
        if action == '>' and num is not None:
            self.add_error('E009', line_num, f">{num}")
            return
        
        content_str = '\n'.join(content) if content else ""
        ops.append(PatchOperation(action, num, content_str, range_end, line_num))


# ============================================================================
# ПРИМЕНЕНИЕ ПАТЧА
# ============================================================================

class PatchApplier:
    """Применяет патч к файлам с двухпроходной проверкой."""
    
    def __init__(self, dry_run: bool = False, patch_file: str = ""):
        self.dry_run = dry_run
        self.patch_file = patch_file
        self.errors: List[PatchError] = []
        self.warnings: List[PatchError] = []
    
    def _print_status(self, icon, text, status="info"):
        colors = {
            "success": Colors.GREEN,
            "error": Colors.RED,
            "warning": Colors.YELLOW,
            "info": Colors.BLUE,
            "process": Colors.CYAN,
        }
        print(f"{colors.get(status, Colors.RESET)}{icon} {text}{Colors.RESET}")
    
    def _print_separator(self, char="=", length=58):
        print(f"{Colors.DIM}{char * length}{Colors.RESET}")
    
    def _add_error(self, code: str, op: PatchOperation = None, **kwargs):
        if op and op.source_line:
            error = PatchError(
                code=code,
                file=self.patch_file,
                line_num=op.source_line,
                line_content=f"{op.action}{op.original_num}" if op.original_num else op.action,
                **kwargs
            )
            self.errors.append(error)
        else:
            self.errors.append(PatchError(code=code, **kwargs))
    
    def load_file(self, file_path: str) -> List[Line]:
        if not os.path.exists(file_path):
            self.errors.append(PatchError('E028', file=file_path))
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            self.errors.append(PatchError('E029', file=file_path))
            return []
        except Exception as e:
            self.errors.append(PatchError('E032', error=str(e)))
            return []
        
        result = []
        for i, line in enumerate(lines, 1):
            result.append(Line(i, line.rstrip('\n')))
        
        fake_line = Line(len(result) + 1, "__END_OF_FILE__")
        result.append(fake_line)
        return result
    
    def save_file(self, file_path: str, lines: List[Line]) -> bool:
        active_lines = [line for line in lines 
                       if line.current_num is not None 
                       and line.content != "__END_OF_FILE__"]
        
        if self.dry_run:
            if not os.access(file_path, os.W_OK):
                self.errors.append(PatchError('E030', file=file_path))
                return False
            return True
        
        try:
            active_lines.sort(key=lambda x: x.current_num)
            with open(file_path, 'w', encoding='utf-8') as f:
                for line in active_lines:
                    f.write(line.content + '\n')
            return True
        except Exception as e:
            self.errors.append(PatchError('E033', file=file_path, error=str(e)))
            return False
    
    def shift_numbers_plus(self, lines: List[Line], from_num: int):
        for line in lines:
            if line.current_num is not None and line.current_num >= from_num:
                line.current_num += 1
    
    def shift_numbers_minus(self, lines: List[Line], from_num: int):
        for line in lines:
            if line.current_num is not None and line.current_num > from_num:
                line.current_num -= 1
    
    def _recalculate_numbers(self, lines: List[Line]):
        counter = 1
        for line in lines:
            if line.current_num is not None:
                line.current_num = counter
                counter += 1
    
    def apply_macro(self, file_path: str, lines: List[Line], op: PatchOperation) -> bool:
        if op.action in ['+', '-', '~'] and op.original_num is None:
            self._add_error('E027', op, action=op.action)
            return False
        
        if op.action == '>' and op.original_num is not None:
            self._add_error('E009', op)
            return False
        
        if op.action in ['+', '-', '~']:
            exists = False
            for line in lines:
                if line.original_num == op.original_num:
                    exists = True
                    break
            if not exists:
                self._add_error('E020', op, num=op.original_num, file=file_path)
                return False
        
        start_num = op.original_num
        end_num = op.range_end if op.is_range else start_num
        
        if op.is_range and start_num > end_num:
            self._add_error('E004', op, start=start_num, end=end_num)
            return False
        
        # --- УДАЛЕНИЕ ---
        if op.action == '-':
            if op.content:
                self._add_error('E010', op)
                return False
            
            for num in range(start_num, end_num + 1):
                found = False
                for line in lines:
                    if line.original_num == num:
                        if line.current_num is None:
                            self._add_error('E021', op, num=num)
                            return False
                        found = True
                        break
                if not found:
                    self._add_error('E020', op, num=num, file=file_path)
                    return False
            
            for num in range(end_num, start_num - 1, -1):
                for line in lines:
                    if line.original_num == num:
                        line.current_num = None
                        break
            
            self._recalculate_numbers(lines)
            return True
        
        # --- ЗАМЕНА ---
        elif op.action == '~':
            if op.is_range:
                for num in range(start_num, end_num + 1):
                    found = False
                    for line in lines:
                        if line.original_num == num:
                            if line.current_num is None:
                                self._add_error('E021', op, num=num)
                                return False
                            found = True
                            break
                    if not found:
                        self._add_error('E020', op, num=num, file=file_path)
                        return False
                
                insert_pos = 0
                for i, line in enumerate(lines):
                    if line.original_num == start_num:
                        insert_pos = i
                        break
                
                for num in range(end_num, start_num - 1, -1):
                    for line in lines:
                        if line.original_num == num:
                            line.current_num = None
                            break
                
                if op.content:
                    content_lines = op.content.split('\n')
                    for content in reversed(content_lines):
                        new_line = Line(None, content)
                        lines.insert(insert_pos, new_line)
                
                self._recalculate_numbers(lines)
                return True
            
            else:
                for line in lines:
                    if line.original_num == op.original_num:
                        if line.current_num is None:
                            self._add_error('E021', op, num=op.original_num)
                            return False
                        
                        insert_pos = lines.index(line)
                        line.current_num = None
                        
                        if op.content:
                            content_lines = op.content.split('\n')
                            for content in reversed(content_lines):
                                new_line = Line(None, content)
                                lines.insert(insert_pos, new_line)
                        
                        self._recalculate_numbers(lines)
                        return True
                
                self._add_error('E020', op, num=op.original_num, file=file_path)
                return False
        
        # --- ВСТАВКА ---
        elif op.action == '+':
            target_line = None
            for line in lines:
                if line.original_num == op.original_num:
                    if line.current_num is None:
                        self._add_error('E021', op, num=op.original_num)
                        return False
                    target_line = line
                    break
            
            if target_line is None:
                self._add_error('E020', op, num=op.original_num, file=file_path)
                return False
            
            insert_pos = lines.index(target_line)
            target_num = target_line.current_num
            
            self.shift_numbers_plus(lines, target_num)
            
            if op.content:
                content_lines = op.content.split('\n')
                for content in reversed(content_lines):
                    new_line = Line(None, content)
                    new_line.current_num = target_num
                    lines.insert(insert_pos, new_line)
            
            self._recalculate_numbers(lines)
            return True
        
        # --- ВСТАВКА В КОНЕЦ ---
        elif op.action == '>':
            insert_pos = 0
            for i, line in enumerate(lines):
                if line.content == "__END_OF_FILE__":
                    insert_pos = i
                    break
            
            if op.content:
                content_lines = op.content.split('\n')
                for content in reversed(content_lines):
                    new_line = Line(None, content)
                    lines.insert(insert_pos, new_line)
            
            self._recalculate_numbers(lines)
            return True
        
        return False
    
    def apply_patch(self, patch_data: Dict[str, List[PatchOperation]]) -> bool:
        success = True
        
        for file_path, operations in patch_data.items():
            if self.dry_run:
                print(f"\n🔍 Проверка: {file_path}")
            else:
                print(f"\n📄 Применение: {file_path}")
            
            lines = self.load_file(file_path)
            if not lines:
                success = False
                continue
            
            for i, op in enumerate(operations):
                if self.dry_run:
                    print(f"   Проверка операции {i+1}: {op.action} {op.original_num}")
                else:
                    print(f"   Выполнение: {op.action} {op.original_num}")
                
                if not self.apply_macro(file_path, lines, op):
                    success = False
                    break
            
            if not success:
                continue
            
            if not self.save_file(file_path, lines):
                success = False
                continue
            
            if not self.dry_run:
                print(f"   {Icons.SUCCESS} Файл сохранён")
        
        return success


# ============================================================================
# ПЛАГИН
# ============================================================================

class PatchPlugin(BasePlugin):
    """Плагин для применения патчей."""
    
    def __init__(self):
        super().__init__()
        self.name = "PatchPlugin"
        self.version = "1.0.0"
        self.description = "Применение патчей к файлам проекта"
        self.patches_dir = Path("patches")
    
    def get_menu_items(self):
        return [
            {
                'icon': '🔧',
                'name': 'Применить патч (выбрать файл)',
                'args': {'action': 'apply'}
            },
            {
                'icon': '🔧',
                'name': 'Применить все патчи',
                'args': {'action': 'apply-all'}
            }
        ]
    
    def get_info(self):
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "enabled": self.enabled
        }
    
    def _print_status(self, icon, text, status="info"):
        colors = {
            "success": Colors.GREEN,
            "error": Colors.RED,
            "warning": Colors.YELLOW,
            "info": Colors.BLUE,
            "process": Colors.CYAN,
        }
        print(f"{colors.get(status, Colors.RESET)}{icon} {text}{Colors.RESET}")
    
    def _print_separator(self, char="=", length=58):
        print(f"{Colors.DIM}{char * length}{Colors.RESET}")
    
    def _print_error(self, error: PatchError):
        print(f"   {error}")
        print()
    
    def find_patch_files(self) -> List[Path]:
        if not self.patches_dir.exists():
            return []
        patch_files = list(self.patches_dir.glob("*.patch"))
        patch_files.sort(key=lambda x: x.name)
        return patch_files
    
    def apply_patch_file(self, patch_file: Path) -> bool:
        if not patch_file.exists():
            self._print_status("❌", f"Файл патча не найден: {patch_file}", "error")
            return False
        
        self._print_status("🔧", f"Применение патча: {patch_file.name}", "process")
        self._print_separator()
        
        parser = PatchParser()
        patch_data = parser.parse(str(patch_file))
        
        if parser.errors:
            self._print_status("❌", "Ошибки парсинга:", "error")
            for error in parser.errors:
                self._print_error(error)
            return False
        
        if not patch_data:
            self._print_status("❌", "Не найдено операций в патче", "error")
            return False
        
        self._print_status("🔍", "Первый проход: проверка (без сохранения)...", "process")
        applier = PatchApplier(dry_run=True, patch_file=str(patch_file))
        dry_success = applier.apply_patch(patch_data)
        
        if not dry_success:
            self._print_status("❌", "Ошибки при проверке:", "error")
            for error in applier.errors:
                self._print_error(error)
            return False
        
        self._print_status("🚀", "Второй проход: применение с сохранением...", "process")
        applier = PatchApplier(dry_run=False, patch_file=str(patch_file))
        real_success = applier.apply_patch(patch_data)
        
        if not real_success:
            self._print_status("❌", "Ошибки при применении:", "error")
            for error in applier.errors:
                self._print_error(error)
            return False
        
        self._print_status("✅", f"Патч {patch_file.name} применён успешно", "success")
        return True
    
    def apply_all_patches(self) -> bool:
        patch_files = self.find_patch_files()
        
        if not patch_files:
            self._print_status("⚠️", "Не найдено файлов *.patch в папке patches/", "warning")
            return False
        
        self._print_status("🔧", f"Найдено патчей: {len(patch_files)}", "process")
        for patch in patch_files:
            print(f"   - {patch.name}")
        
        self._print_separator()
        
        success = True
        applied = 0
        
        for patch_file in patch_files:
            if self.apply_patch_file(patch_file):
                applied += 1
            else:
                success = False
        
        self._print_separator()
        self._print_status("📊", f"Применено: {applied}/{len(patch_files)} патчей", "info")
        return success
    
    def apply_interactive(self) -> bool:
        patch_files = self.find_patch_files()
        
        if not patch_files:
            self._print_status("⚠️", "Не найдено файлов *.patch в папке patches/", "warning")
            return False
        
        print("\n" + "=" * 60)
        print("📂 ВЫБОР ФАЙЛА ПАТЧА")
        print("=" * 60)
        
        for i, patch in enumerate(patch_files, 1):
            print(f"  {i}. {patch.name}")
        
        print(f"  0. Отмена")
        print()
        
        choice = input(f"{Colors.BOLD}{Icons.ARROW} Ваш выбор: {Colors.RESET}").strip()
        
        if choice == "0":
            print("ℹ️ Отменено")
            return False
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(patch_files):
                return self.apply_patch_file(patch_files[idx])
            else:
                self._print_status("❌", "Неверный выбор", "error")
                return False
        except ValueError:
            self._print_status("❌", "Введите число", "error")
            return False
    
    def apply_all_and_run(self) -> bool:
        self._print_status("🔧", "Применение патчей и запуск проекта", "process")
        self._print_separator()
        
        success = self.apply_all_patches()
        
        if success:
            self._print_separator()
            self._print_status("🚀", "Запуск проекта...", "process")
            self._print_separator()
            
            try:
                from plugins.run_plugin import RunPlugin
                run_plugin = RunPlugin()
                return run_plugin.execute()
            except ImportError:
                self._print_status("❌", "Плагин RunPlugin не найден", "error")
                return False        
            else:
                self._print_status("❌", "Применение патчей завершено с ошибками", "error")
                return False
        
    def execute(self, *args, **kwargs):
        action = kwargs.get('action', 'apply')
        
        if action == 'apply':
            return self.apply_interactive()
        elif action == 'apply-all':
            return self.apply_all_patches()
        elif action == 'apply-and-run':
            return self.apply_all_and_run()
        else:
            return self.apply_interactive()


# ============================================================================
# АВТОНОМНЫЙ РЕЖИМ
# ============================================================================

def main():
    """Автономный запуск плагина из командной строки."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Применение патчей')
    parser.add_argument('--apply', action='store_true', help='Применить патч (интерактивный выбор)')
    parser.add_argument('--apply-all', action='store_true', help='Применить все патчи')
    parser.add_argument('--file', type=str, help='Применить конкретный файл патча')
    
    args = parser.parse_args()
    
    plugin = PatchPlugin()
    
    if args.file:
        success = plugin.apply_patch_file(Path(args.file))
    elif args.apply_all:
        success = plugin.apply_all_patches()
    elif args.apply:
        success = plugin.apply_interactive()
    else:
        success = plugin.apply_interactive()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
