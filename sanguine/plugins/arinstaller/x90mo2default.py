"""
MO2DEFAULT archive installer. Guess-only: we'll be trying to guess what MO2 did when installed,
but we won't install like this ourselves, preferring SIMPLEUNPACK.
Almost the same as SimpleUnpack installer, just copying non-data files to the root too.
Very unusually for plugins, relies on another plugin ('SIMPLEUNPACK' one).
"""
from sanguine.common import *
from sanguine.helpers.archives import Archive, FileInArchive
from sanguine.helpers.arinstallers import ArInstallerPluginBase, ArInstaller, ExtraArchiveDataFactory
from sanguine.helpers.file_retriever import ArchiveFileRetriever
from sanguine.plugins.arinstaller.x99simpleunpack import SimpleUnpackArInstaller, SimpleUnpackArInstallerPlugin


class Mo2DefaultArInstaller(SimpleUnpackArInstaller):
    def __init__(self, archive: Archive):
        super().__init__(archive)

    def name(self) -> str:
        return 'MO2DEFAULT'

    def all_desired_files(self) -> Iterable[tuple[str, FileInArchive]]:  # list[relpath]
        out: list[tuple[str, FileInArchive]] = list(super().all_desired_files())
        assert self.install_from_root.endswith('data\\')
        xtrapath = self.install_from_root[:-len('data\\')]
        lxtrapath = len(xtrapath)
        for fia in self.archive.files:
            if fia.intra_path.startswith(xtrapath) and not fia.intra_path.startswith(self.install_from_root):
                out.append((fia.intra_path[lxtrapath:], fia))
        return out

    def install_params(self) -> Any:
        return super().install_params()

    @classmethod
    def from_root(cls, archive: Archive, root: str) -> 'Mo2DefaultArInstaller':
        out = cls(archive)
        out.install_from_root = root
        return out


class Mo2DefaultArInstallerPlugin(ArInstallerPluginBase):
    def name(self) -> str:
        return 'MO2DEFAULT'

    def guess_arinstaller_from_vfs(self, archive: Archive, modname: str,
                                   modfiles: dict[str, list[ArchiveFileRetriever]]) -> ArInstaller | None:
        simple = SimpleUnpackArInstallerPlugin()
        simpleinst = simple.guess_arinstaller_from_vfs(archive, modname, modfiles)
        if simpleinst is None:
            return None
        assert isinstance(simpleinst, SimpleUnpackArInstaller)
        if not simpleinst.install_from_root.endswith('data\\'):
            return None

        candidate = Mo2DefaultArInstaller.from_root(archive, simpleinst.install_from_root)
        nsimple = sum(1 for _ in simpleinst.all_desired_files())
        ncandidate = sum(1 for _ in candidate.all_desired_files())
        return candidate if ncandidate > nsimple else None

    def got_loaded_data(self, data: Any) -> None:
        assert False

    def data_for_saving(self) -> Any:
        assert False

    def extra_data_factory(self) -> ExtraArchiveDataFactory | None:
        return None

    def add_extra_data(self, arh: bytes, data: dict[str, Any]) -> None:
        assert False
