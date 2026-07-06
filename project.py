#!/usr/bin/env python3
"""
Ядро административных инструментов проекта.

Режимы работы:
    python project.py              - интерактивный режим (полное меню)
    python project.py --quick      - быстрое меню (для разработки)
    python project.py --help       - показать справку
    python project.py --plugin     - запустить плагин (например: --plugin DeployPlugin --auto)
    python project.py --logs       - управление логами
    python project.py --status     - показать статус проекта
"""

import argparse
import os
import sys
import platform
import subprocess
import time
import json
import importlib.util
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any


# ========== ЦВЕТА ДЛЯ КРАСИВОГО ВЫВОДА ==========
class Colors:
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
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    ARROW = "👉"
    EXIT = "🚪"
    PLUGIN = "🔌"
    LOGS = "📝"
    STATUS = "📈"
    HELP = "❓"


# ========== УТИЛИТЫ ==========
def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_status(icon, text, status="info"):
    colors = {
        "success": Colors.GREEN,
        "error": Colors.RED,
        "warning": Colors.YELLOW,
        "info": Colors.BLUE,
        "process": Colors.CYAN,
        "highlight": Colors.MAGENTA,
    }
    print(f"{colors.get(status, Colors.RESET)}{icon} {text}{Colors.RESET}")


def print_info(text):
    print(f"{Colors.BLUE}{Icons.INFO}{Colors.RESET} {text}")


def print_separator(char="=", length=58):
    print(f"{Colors.DIM}{char * length}{Colors.RESET}")


def print_box(text, color=Colors.CYAN, padding=2):
    lines = text.split("\n")
    max_len = max(len(line) for line in lines)
    width = max_len + padding * 2
    print(f"{color}┌{'─' * width}┐{Colors.RESET}")
    for line in lines:
        print(f"{color}│{' ' * padding}{line}{' ' * (max_len - len(line))}{' ' * padding}│{Colors.RESET}")
    print(f"{color}└{'─' * width}┘{Colors.RESET}")


def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def copy_to_clipboard(text):
    try:
        if platform.system() == "Windows":
            subprocess.run(["clip"], input=text.encode("utf-8"), check=True)
        elif platform.system() == "Darwin":
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        else:
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), check=True)
        return True
    except:
        return False


# ========== СИСТЕМА ПЛАГИНОВ ==========
class PluginManager:
    def __init__(self):
        self.plugins = {}
        self.plugin_dir = Path("plugins")
        self.menu_items = []
    
    def load_plugins(self):
        if not self.plugin_dir.exists():
            return {}
        
        try:
            from plugins.base_plugin import BasePlugin
        except ImportError:
            sys.path.insert(0, str(self.plugin_dir.parent))
            try:
                from plugins.base_plugin import BasePlugin
            except ImportError:
                print_status(Icons.ERROR, "Не найден base_plugin.py", "error")
                return {}
        
        loaded = {}
        self.menu_items = []
        
        for file_path in self.plugin_dir.glob("*_plugin.py"):
            try:
                module_name = file_path.stem
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, BasePlugin) and 
                        attr != BasePlugin):
                        plugin = attr()
                        loaded[plugin.name] = plugin
                        
                        menu_items = plugin.get_menu_items()
                        if menu_items:
                            for item in menu_items:
                                self.menu_items.append({
                                    'key': self._generate_menu_key(),
                                    'icon': item.get('icon', '🔌'),
                                    'name': item.get('name', plugin.name),
                                    'plugin': plugin,
                                    'args': item.get('args', {})
                                })
                        
                        print_status(Icons.PLUGIN, f"Загружен плагин: {plugin.name}", "success")
                        break
                        
            except Exception as e:
                print_status(Icons.ERROR, f"Ошибка загрузки {file_path.name}: {e}", "error")
        
        self.menu_items.sort(key=lambda x: x['key'])
        self.plugins = loaded
        return loaded
    
    def _generate_menu_key(self):
        used_keys = set(item['key'] for item in self.menu_items)
        for i in range(1, 100):
            key = str(i)
            if key not in used_keys:
                return key
        return '99'
    
    def get_plugin(self, name):
        return self.plugins.get(name)
    
    def get_all_plugins(self):
        return self.plugins
    
    def get_menu_items(self):
        return self.menu_items
    
    def execute_plugin(self, plugin, **kwargs):
        if not plugin.is_enabled():
            print_status(Icons.WARNING, f"Плагин '{plugin.name}' отключен", "warning")
            return False
        
        print_status(Icons.PLUGIN, f"Выполнение: {plugin.name}", "process")
        try:
            result = plugin.execute(**kwargs)
            if result:
                print_status(Icons.SUCCESS, "Выполнено успешно", "success")
            else:
                print_status(Icons.ERROR, "Выполнено с ошибкой", "error")
            return result
        except Exception as e:
            print_status(Icons.ERROR, f"Ошибка: {e}", "error")
            return False


# ========== ЛОГИ ==========
def show_logs_menu():
    clear_screen()
    print(f"{Colors.CYAN}{'=' * 58}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}📝 УПРАВЛЕНИЕ ЛОГАМИ{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 58}{Colors.RESET}")
    print(f"\n{Colors.BOLD}Выберите действие:{Colors.RESET}")
    print(f"{Colors.CYAN}{'-' * 42}{Colors.RESET}")
    print(f"  {Colors.GREEN}1{Colors.RESET}. Показать последний запуск (last_run.log)")
    print(f"  {Colors.GREEN}2{Colors.RESET}. Показать полный лог (project.log)")
    print(f"  {Colors.GREEN}3{Colors.RESET}. Копировать последний запуск в буфер")
    print(f"  {Colors.GREEN}4{Colors.RESET}. Очистить логи")
    print(f"  {Colors.GREEN}0{Colors.RESET}. Назад")
    print(f"{Colors.CYAN}{'-' * 42}{Colors.RESET}")


def read_log_file(filepath, max_lines=None):
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if max_lines and len(lines) > max_lines:
                return lines[-max_lines:]
            return lines
    except:
        return None


def show_last_run_log():
    print()
    print_status(Icons.LOGS, "Чтение last_run.log...", "process")
    print_separator()
    
    lines = read_log_file("last_run.log")
    if lines is None:
        print_status(Icons.WARNING, "Файл last_run.log не найден", "warning")
        return
    
    if len(lines) > 100:
        print_status(Icons.WARNING, f"Лог содержит {len(lines)} строк", "warning")
        print(f"\n{Icons.ARROW} Показать все? [y/N]")
        choice = input().strip().lower()
        if choice not in ["y", "yes", "да"]:
            lines = lines[:100]
    
    print(f"\n{Colors.CYAN}{'=' * 58}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}📝 ПОСЛЕДНИЙ ЗАПУСК{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 58}{Colors.RESET}\n")
    for line in lines:
        print(line.rstrip())
    print(f"\n{Colors.CYAN}{'=' * 58}{Colors.RESET}")
    print_info(f"Всего строк: {len(lines)}")


def show_full_log():
    print()
    print_status(Icons.LOGS, "Чтение project.log...", "process")
    print_separator()
    
    lines = read_log_file("project.log")
    if lines is None:
        print_status(Icons.WARNING, "Файл project.log не найден", "warning")
        return
    
    if len(lines) > 200:
        print_status(Icons.WARNING, f"Лог содержит {len(lines)} строк", "warning")
        print(f"\n{Icons.ARROW} Показать все? [y/N]")
        choice = input().strip().lower()
        if choice not in ["y", "yes", "да"]:
            lines = lines[-200:]
    
    print(f"\n{Colors.CYAN}{'=' * 58}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}📝 ПОЛНЫЙ ЛОГ{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 58}{Colors.RESET}\n")
    for line in lines:
        print(line.rstrip())
    print(f"\n{Colors.CYAN}{'=' * 58}{Colors.RESET}")
    print_info(f"Всего строк: {len(lines)}")


def copy_last_run_to_clipboard():
    print()
    print_status(Icons.LOGS, "Копирование в буфер...", "process")
    if not os.path.exists("last_run.log"):
        print_status(Icons.WARNING, "Файл не найден", "warning")
        return
    try:
        with open("last_run.log", "r", encoding="utf-8") as f:
            content = f.read()
        if copy_to_clipboard(content):
            print_status(Icons.SUCCESS, "Скопировано!", "success")
        else:
            print_status(Icons.ERROR, "Ошибка копирования", "error")
    except Exception as e:
        print_status(Icons.ERROR, f"Ошибка: {e}", "error")


def clear_logs():
    print()
    print(f"\n{Icons.ARROW} Очистить логи? [y/N]")
    if not input().strip().lower() in ["y", "yes", "да"]:
        print_status(Icons.INFO, "Отменено", "info")
        return
    print_status(Icons.LOGS, "Очистка...", "process")
    for log_file in ["project.log", "last_run.log"]:
        try:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write("")
        except:
            pass
    print_status(Icons.SUCCESS, "Логи очищены", "success")


def logs_interactive():
    while True:
        show_logs_menu()
        choice = input(f"\n{Colors.BOLD}{Icons.ARROW} Выбор: {Colors.RESET}").strip()
        if choice == "1":
            show_last_run_log()
            print(f"\n{Icons.ARROW} Нажмите Enter...")
            input()
        elif choice == "2":
            show_full_log()
            print(f"\n{Icons.ARROW} Нажмите Enter...")
            input()
        elif choice == "3":
            copy_last_run_to_clipboard()
            print(f"\n{Icons.ARROW} Нажмите Enter...")
            input()
        elif choice == "4":
            clear_logs()
            print(f"\n{Icons.ARROW} Нажмите Enter...")
            input()
        elif choice == "0":
            break
        else:
            print_status(Icons.ERROR, "Неверный выбор", "error")
            print(f"\n{Icons.ARROW} Нажмите Enter...")
            input()


# ========== СТАТУС ==========
def run_status():
    print()
    print_box("📈 СТАТУС ПРОЕКТА", Colors.CYAN)
    print_separator()
    
    # Проверка venv
    venv_exists = os.path.exists("venv")
    print(f"🔧 Виртуальное окружение: {Colors.GREEN + '✅' if venv_exists else Colors.RED + '❌'}{Colors.RESET}")
    
    # Проверка .env
    env_exists = os.path.exists(".env")
    print(f"🔧 .env файл: {Colors.GREEN + '✅' if env_exists else Colors.RED + '❌'}{Colors.RESET}")
    
    # Проверка логов
    for log_file in ["project.log", "last_run.log"]:
        if os.path.exists(log_file):
            size = os.path.getsize(log_file)
            size_str = f"{size / 1024:.1f} KB" if size > 1024 else f"{size} B"
            print(f"{Icons.LOGS} {log_file}: {Colors.DIM}{size_str}{Colors.RESET}")
        else:
            print(f"{Icons.LOGS} {log_file}: {Colors.DIM}не найден{Colors.RESET}")
    
    # Проверка контекста
    if os.path.exists("context.txt"):
        size = os.path.getsize("context.txt")
        size_str = f"{size / 1024:.1f} KB" if size > 1024 else f"{size} B"
        print(f"📝 context.txt: {Colors.DIM}{size_str}{Colors.RESET}")
    else:
        print(f"📝 context.txt: {Colors.DIM}не найден{Colors.RESET}")
    
    # Проверка плагинов
    plugin_manager = PluginManager()
    plugins = plugin_manager.load_plugins()
    if plugins:
        print(f"{Icons.PLUGIN} Плагины: {Colors.GREEN}{len(plugins)} загружено{Colors.RESET}")
        for name, plugin in plugins.items():
            info = plugin.get_info()
            print(f"   {Colors.DIM}- {name} v{info.get('version', '1.0')}{Colors.RESET}")
    else:
        print(f"{Icons.PLUGIN} Плагины: {Colors.DIM}не найдены{Colors.RESET}")
    
    print_separator()


# ========== СПРАВКА ==========
HELP_TEXT = f"""
{Colors.CYAN}{"=" * 58}{Colors.RESET}
{Colors.BOLD}{Colors.MAGENTA}                    PROJECT.PY - СПРАВКА{Colors.RESET}
{Colors.CYAN}{"=" * 58}{Colors.RESET}

{Colors.BOLD}📋 ИНТЕРАКТИВНЫЙ РЕЖИМ{Colors.RESET}
    python project.py
    Открывает главное меню со всеми плагинами

{Colors.BOLD}⚡ БЫСТРОЕ МЕНЮ{Colors.RESET}
    python project.py --quick
    Быстрое меню с горячими клавишами

{Colors.BOLD}📝 УПРАВЛЕНИЕ ЛОГАМИ{Colors.RESET}
    python project.py --logs
    Открыть меню управления логами

{Colors.BOLD}📈 СТАТУС{Colors.RESET}
    python project.py --status
    Показать статус проекта

{Colors.BOLD}🔌 ПЛАГИНЫ{Colors.RESET}
    python project.py --plugin <имя_плагина> [args]
    Запустить плагин напрямую

{Colors.BOLD}❓ СПРАВКА{Colors.RESET}
    python project.py --help
    Показать эту справку

{Colors.CYAN}{"=" * 58}{Colors.RESET}
"""


# ========== МЕНЮ ==========
def print_full_menu(plugin_manager):
    clear_screen()
    print(f"{Colors.CYAN}{'=' * 58}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}🛠️  АДМИНИСТРАТИВНЫЕ ИНСТРУМЕНТЫ v3.0{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 58}{Colors.RESET}")
    print(f"\n{Colors.BOLD}Плагины:{Colors.RESET}")
    print(f"{Colors.CYAN}{'-' * 42}{Colors.RESET}")
    
    for item in plugin_manager.get_menu_items():
        print(f"  {Colors.GREEN}{item['key']}{Colors.RESET}. {item['icon']} {item['name']}")
    
    print(f"{Colors.CYAN}{'-' * 42}{Colors.RESET}")
    print(f"  {Colors.GREEN}L{Colors.RESET}. {Icons.LOGS} Управление логами")
    print(f"  {Colors.GREEN}S{Colors.RESET}. {Icons.STATUS} Статус проекта")
    print(f"  {Colors.GREEN}H{Colors.RESET}. {Icons.HELP} Справка")
    print(f"  {Colors.GREEN}0{Colors.RESET}. {Icons.EXIT} Выход")
    print(f"  {Colors.GREEN}Q{Colors.RESET}. ⚡ Быстрое меню")
    print(f"{Colors.CYAN}{'-' * 42}{Colors.RESET}")


def print_quick_menu():
    clear_screen()
    print(f"{Colors.CYAN}{'=' * 58}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}⚡ БЫСТРОЕ МЕНЮ{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 58}{Colors.RESET}")
    print(f"\n  {Colors.GREEN}1{Colors.RESET}. 🚀 Распаковать и запустить")
    print(f"  {Colors.GREEN}2{Colors.RESET}. 🔧 Применить патчи и запустить")
    print(f"  {Colors.GREEN}3{Colors.RESET}. 🚀 Только запустить")
    print(f"  {Colors.GREEN}4{Colors.RESET}. 📦 Упаковать проект")
    print(f"  {Colors.GREEN}5{Colors.RESET}. ⚙️ Установить проект")
    print(f"  {Colors.GREEN}6{Colors.RESET}. 📝 Новый контекст")
    print(f"\n  {Colors.GREEN}M{Colors.RESET}. 📋 Полное меню")
    print(f"  {Colors.GREEN}0{Colors.RESET}. {Icons.EXIT} Выход")
    print(f"{Colors.CYAN}{'-' * 58}{Colors.RESET}")
    print(f"\n{Colors.DIM}💡 Нажмите 1-6 - мгновенно | 0, M - с подтверждением{Colors.RESET}")


def get_key():
    if platform.system() == "Windows":
        import msvcrt
        return msvcrt.getch().decode("utf-8", errors="ignore").lower()
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1).lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def interactive_full_mode():
    plugin_manager = PluginManager()
    plugin_manager.load_plugins()
    
    while True:
        print_full_menu(plugin_manager)
        choice = input(f"\n{Colors.BOLD}{Icons.ARROW} Ваш выбор: {Colors.RESET}").strip().upper()
        
        if choice == "0":
            print_status(Icons.EXIT, "До свидания!", "success")
            print()
            break
        
        elif choice == "H":
            clear_screen()
            print(HELP_TEXT)
            print(f"\n{Icons.ARROW} Нажмите Enter...")
            input()
        
        elif choice == "L":
            logs_interactive()
        
        elif choice == "S":
            run_status()
            print(f"\n{Icons.ARROW} Нажмите Enter...")
            input()
        
        elif choice == "Q":
            interactive_quick_mode()
            break
        
        else:
            # Ищем плагин по ключу
            plugin_item = None
            for item in plugin_manager.get_menu_items():
                if item['key'] == choice:
                    plugin_item = item
                    break
            
            if plugin_item:
                print()
                print_separator()
                plugin_manager.execute_plugin(plugin_item['plugin'], **plugin_item['args'])
                print(f"\n{Icons.ARROW} Нажмите Enter...")
                input()
            else:
                print_status(Icons.ERROR, "Неверный выбор", "error")
                print(f"\n{Icons.ARROW} Нажмите Enter...")
                input()


def interactive_quick_mode():
    plugin_manager = PluginManager()
    plugin_manager.load_plugins()
    
    while True:
        print_quick_menu()
        key = get_key()
        
        if key == "1":
            print()
            deploy = plugin_manager.get_plugin("DeployPlugin")
            run = plugin_manager.get_plugin("RunPlugin")
            if deploy and run:
                plugin_manager.execute_plugin(deploy)
                plugin_manager.execute_plugin(run)
            else:
                print_status(Icons.ERROR, "Плагины не найдены", "error")
            print(f"\n{Icons.ARROW} Нажмите Enter...")
            input()
        
        elif key == "2":
            print()
            patch = plugin_manager.get_plugin("PatchPlugin")
            run = plugin_manager.get_plugin("RunPlugin")
            if patch and run:
                plugin_manager.execute_plugin(patch, action='apply-all')
                plugin_manager.execute_plugin(run)
            else:
                print_status(Icons.ERROR, "Плагины не найдены", "error")
            print(f"\n{Icons.ARROW} Нажмите Enter...")
            input()
        
        elif key == "3":
            print()
            run = plugin_manager.get_plugin("RunPlugin")
            if run:
                plugin_manager.execute_plugin(run)
            else:
                print_status(Icons.ERROR, "Плагин не найден", "error")
            print(f"\n{Icons.ARROW} Нажмите Enter...")
            input()
        
        elif key == "4":
            print()
            pack = plugin_manager.get_plugin("PackPlugin")
            if pack:
                plugin_manager.execute_plugin(pack)
            else:
                print_status(Icons.ERROR, "Плагин не найден", "error")
            print(f"\n{Icons.ARROW} Нажмите Enter...")
            input()
        
        elif key == "5":
            print()
            setup = plugin_manager.get_plugin("SetupPlugin")
            if setup:
                plugin_manager.execute_plugin(setup)
            else:
                print_status(Icons.ERROR, "Плагин не найден", "error")
            print(f"\n{Icons.ARROW} Нажмите Enter...")
            input()
        
        elif key == "6":
            print()
            context = plugin_manager.get_plugin("ContextPlugin")
            if context:
                plugin_manager.execute_plugin(context, action='new_context')
            else:
                print_status(Icons.ERROR, "Плагин ContextPlugin не найден", "error")
            print(f"\n{Icons.ARROW} Нажмите Enter...")
            input()
        
        elif key == "m":
            print()
            interactive_full_mode()
            break
        
        elif key == "0":
            print(f"\n{Colors.YELLOW}{Icons.WARNING} Выход? Нажмите Enter{Colors.RESET}")
            confirm = get_key()
            if confirm in ["\r", "\n"]:
                print_status(Icons.EXIT, "До свидания!", "success")
                print()
                break
            print_status(Icons.INFO, "Отменено", "info")
            print(f"\n{Icons.ARROW} Нажмите Enter...")
            input()
        elif key in ["\r", "\n", "\x03"]:
            continue


# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
def main():
    parser = argparse.ArgumentParser(description="Административные инструменты v3.0", add_help=False)
    parser.add_argument("--quick", action="store_true", help="Быстрое меню")
    parser.add_argument("--logs", action="store_true", help="Управление логами")
    parser.add_argument("--status", action="store_true", help="Статус проекта")
    parser.add_argument("--plugin", type=str, help="Запустить плагин")
    parser.add_argument("--help", "-h", action="store_true", help="Справка")
    
    args, unknown = parser.parse_known_args()
    
    if args.help:
        print(HELP_TEXT)
        return
    
    if args.logs:
        logs_interactive()
        return
    
    if args.status:
        run_status()
        return
    
    if args.plugin:
        plugin_manager = PluginManager()
        plugin_manager.load_plugins()
        plugin = plugin_manager.get_plugin(args.plugin)
        if plugin:
            kwargs = {}
            if unknown:
                for i in range(0, len(unknown), 2):
                    if i+1 < len(unknown):
                        key = unknown[i].lstrip('-')
                        value = unknown[i+1]
                        kwargs[key] = value
            sys.exit(0 if plugin_manager.execute_plugin(plugin, **kwargs) else 1)
        else:
            print_status(Icons.ERROR, f"Плагин '{args.plugin}' не найден", "error")
            sys.exit(1)
    
    if args.quick:
        interactive_quick_mode()
    else:
        interactive_full_mode()


if __name__ == "__main__":
    main()
