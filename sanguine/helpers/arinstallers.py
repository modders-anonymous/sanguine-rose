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
    def name(self) -> str:
        pass

    @abstractmethod
    def install_params(self) -> Any:  # return must be stable_json-compatible
        pass


class ArInstallerDetails:
    ignored: set[str]
    skip: set[str]
    files: dict[str, FileInArchive]
    modified_since_install: set[str]

    def __init__(self) -> None:
        self.ignored = set()
        self.skip = set()
        self.files = {}
        self.modified_since_install = set()


class ExtraArchiveDataFactory:
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def extra_data(self, fullarchivedir: str) -> dict[str, Any] | None:  # returns stable_json data
        pass


class ArInstallerPluginBase(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def guess_arinstaller_from_vfs(self, archive: Archive, modname: str,
                                   modfiles: dict[str, list[ArchiveFileRetriever]]) -> ArInstaller | None:
        pass

    @abstractmethod
    def got_loaded_data(self, data: Any) -> None:
        pass

    @abstractmethod
    def data_for_saving(self) -> Any:  # return value must be stable_json-compatible
        pass

    @abstractmethod
    def extra_data_factory(self) -> ExtraArchiveDataFactory | None:
        pass

    @abstractmethod
    def add_extra_data(self, arh: bytes, data: Any | None | Exception) -> None:
        pass


_arinstaller_plugins: dict[str, ArInstallerPluginBase] = {}


def _found_arinstaller_plugin(plugin: ArInstallerPluginBase):
    global _arinstaller_plugins
    _arinstaller_plugins[plugin.name()] = plugin  # order is preserved since Python 3.6 or so


load_plugins('plugins/arinstaller/', ArInstallerPluginBase, lambda plugin: _found_arinstaller_plugin(plugin))


def all_arinstaller_plugins() -> Iterable[ArInstallerPluginBase]:
    global _arinstaller_plugins
    return _arinstaller_plugins.values()


def arinstaller_plugin_by_name(name: str) -> ArInstallerPluginBase:
    global _arinstaller_plugins
    return _arinstaller_plugins[name]


def arinstaller_plugin_add_extra_data(name: str, arh: bytes, data: Any) -> None:
    global _arinstaller_plugins
    _arinstaller_plugins[name].add_extra_data(arh, data)
