from sanguine.common import *
from sanguine.helpers.archives import Archive, FileInArchive
from sanguine.helpers.arinstallers import ArInstallerPluginBase, ArInstaller, ExtraArchiveDataFactory
from sanguine.helpers.file_retriever import ArchiveFileRetriever


class FomodArInstaller(ArInstaller):
    def __init__(self, archive: Archive):
        super().__init__(archive)

    def name(self) -> str:
        return 'FOMOD'

    def all_desired_files(self) -> Iterable[tuple[str, FileInArchive]]:  # list[relpath]
        assert False

    def install_params(self) -> dict[str, Any]:
        assert False

class FomodExtraArchiveDataFactory(ExtraArchiveDataFactory):
    def name(self) -> str:
        return 'FOMOD'

    @abstractmethod
    def extra_data(self, fullarchivedir: str) -> dict[str, Any] | None:  # returns stable_json data
        assert is_normalized_dir_path(fullarchivedir)
        if os.path.isfile(fullarchivedir+'fomod\\moduleconfig.xml'):
            moduleconfig: list[str] = []
            with open_3rdparty_txt_file('fomod\\moduleconfig.xml') as f:
                for ln in f:
                    moduleconfig.append(ln)
            return {'moduleconfig': moduleconfig}
        return None


class FomodArInstallerPlugin(ArInstallerPluginBase):
    def name(self) -> str:
        return 'FOMOD'

    def guess_arinstaller_from_vfs(self, archive: Archive, modname: str,
                                   modfiles: dict[str, list[ArchiveFileRetriever]]) -> ArInstaller | None:
        return None

    def got_loaded_data(self, data: Any) -> None:
        pass

    def data_for_saving(self) -> Any:
        return None

    def extra_data_factory(self) -> ExtraArchiveDataFactory | None:
        return FomodExtraArchiveDataFactory()

    def add_extra_data(self, arh: bytes, data: dict[str, Any]) -> None:
        assert False
