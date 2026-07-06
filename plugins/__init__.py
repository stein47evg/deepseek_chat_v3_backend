"""
Пакет для плагинов проекта
"""

from plugins.base_plugin import BasePlugin
from plugins.deploy_plugin import DeployPlugin
from plugins.pack_plugin import PackPlugin
from plugins.run_plugin import RunPlugin
from plugins.setup_plugin import SetupPlugin
from plugins.test_plugin import TestPlugin
from plugins.context_plugin import ContextPlugin
from plugins.patch_plugin import PatchPlugin

__all__ = [
    'BasePlugin',
    'ExamplePlugin',
    'DeployPlugin',
    'PackPlugin',
    'RunPlugin',
    'SetupPlugin',
    'TestPlugin',
    'ContextPlugin',
    'PatchPlugin'
]
