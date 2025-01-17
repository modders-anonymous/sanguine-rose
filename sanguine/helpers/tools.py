from sanguine.common import *
from sanguine.helpers.plugin_handler import load_plugins
from sanguine.helpers.project_config import LocalProjectConfig


class CouldBeProducedByTool(IntEnum):
    NotFound = 0,
    Maybe = 1,
    WithKnownConfig = 2,
    WithOldConfig = 3,
    WithCurrentConfig = 4

    def is_greater_or_eq(self, cbp: "CouldBeProducedByTool") -> bool:
        return int(self) >= int(cbp)


class ToolPluginBase(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def supported_games(self) -> list[str]:
        pass

    @abstractmethod
    def extensions(self) -> list[str]:
        pass

    @abstractmethod
    def create_context(self, cfg: LocalProjectConfig, resolvedvfs: ResolvedVFS) -> Any:
        pass

    @abstractmethod
    def could_be_produced(self, context: Any, srcpath: str, targetpath: str) -> CouldBeProducedByTool:
        pass


_tool_plugins: list[ToolPluginBase] = []


def _found_tool_plugin(plugin: ToolPluginBase):
    global _tool_plugins
    if __debug__:
        for universe in plugin.supported_games():
            assert universe.isupper()
    _tool_plugins.append(plugin)


load_plugins('plugins/tool/', ToolPluginBase, lambda plugin: _found_tool_plugin(plugin))


def all_tool_plugins(gameuniverse: str) -> list[ToolPluginBase]:
    global _tool_plugins
    return [t for t in _tool_plugins if gameuniverse.upper() in t.supported_games()]
