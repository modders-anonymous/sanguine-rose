from sanguine.common import *
from sanguine.helpers.arinstallers import ArInstaller, ArInstallerDetails
from sanguine.helpers.file_retriever import ArchiveFileRetriever
from sanguine.helpers.plugin_handler import load_plugins


class ModToolGuessParam:
    install_from: list[tuple[ArInstaller, ArInstallerDetails]]
    remaining_after_install_from: dict[str, list[ArchiveFileRetriever]]


class ModToolGuessDiff:
    moved: list[tuple[str, str]]

    def __init__(self):
        self.moved = []


class ModToolPluginBase(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def supported_games(self) -> list[str]:
        pass

    @abstractmethod
    def guess_applied(self, param: ModToolGuessParam) -> None | tuple[Any, ModToolGuessDiff]:
        pass


_mod_tool_plugins: list[ModToolPluginBase] = []


def _found_mod_tool_plugin(plugin: ModToolPluginBase) -> None:
    global _mod_tool_plugins
    if __debug__:
        for universe in plugin.supported_games():
            assert universe.isupper()
    _mod_tool_plugins.append(plugin)


load_plugins('plugins/modtool/', ModToolPluginBase, lambda plugin: _found_mod_tool_plugin(plugin))


def all_mod_tool_plugins(gameuniverse: str) -> list[ModToolPluginBase]:
    global _mod_tool_plugins
    return [t for t in _mod_tool_plugins if gameuniverse.upper() in t.supported_games()]
