from sanguine.cache.whole_cache import ResolvedVFS
from sanguine.common import *
from sanguine.helpers.plugin_handler import load_plugins


class ToolPluginBase(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def extensions(self) -> list[str]:
        pass

    @abstractmethod
    def create_context(self, resolvedvfs: ResolvedVFS) -> any:
        pass

    @abstractmethod
    def could_be_produced(self, context: any, srcpath: str, targetpath: str) -> bool:
        pass


_tool_plugins: list[ToolPluginBase] = []


def _found_tool_plugin(plugin: ToolPluginBase):
    global _tool_plugins
    _tool_plugins.append(plugin)


load_plugins('plugins/tool/', ToolPluginBase, lambda plugin: _found_tool_plugin(plugin))


def all_tool_plugins() -> list[ToolPluginBase]:
    global _tool_plugins
    return _tool_plugins
