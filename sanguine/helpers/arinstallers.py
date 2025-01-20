from sanguine.common import *
from sanguine.helpers.archives import Archive, FileInArchive
from sanguine.helpers.file_retriever import ArchiveFileRetriever
from sanguine.helpers.plugin_handler import load_plugins


class ArInstaller:
    archive: Archive

    def __init__(self, archive: Archive):
        self.archive = archive

    @abstractmethod
    def all_desired_files(self) -> list[tuple[str, FileInArchive]]:  # list[relpath]
        pass

    @abstractmethod
    def install_data(self) -> str:
        pass


class ArInstallerPluginBase(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def guess_arinstaller_from_vfs(self, archive: Archive, modname: str,
                                   modfiles: dict[str, list[ArchiveFileRetriever]]) -> ArInstaller | None:
        pass


_arinstaller_plugins: list[ArInstallerPluginBase] = []


def _found_arinstaller_plugin(plugin: ArInstallerPluginBase):
    global _arinstaller_plugins
    _arinstaller_plugins.append(plugin)


load_plugins('plugins/arinstaller/', ArInstallerPluginBase, lambda plugin: _found_arinstaller_plugin(plugin))


def all_arinstaller_plugins() -> list[ArInstallerPluginBase]:
    global _arinstaller_plugins
    return _arinstaller_plugins
