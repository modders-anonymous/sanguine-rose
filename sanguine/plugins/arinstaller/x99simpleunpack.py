"""
SimpleUnpack archive installer. Simply unpacking archive, starting from root.
Very unusually for plugins, it is being relied on by another plugin: MO2DEFAULT one
"""

from sanguine.common import *
from sanguine.helpers.archives import Archive, FileInArchive
from sanguine.helpers.arinstallers import ArInstallerPluginBase, ArInstaller, ExtraArchiveDataFactory
from sanguine.helpers.file_retriever import ArchiveFileRetriever


class SimpleUnpackArInstallerInstallData:
    SANGUINE_JSON: list[tuple[str, str]] = [('install_from_root', 'root')]
    install_from_root: str

    def __init__(self, ifr: str) -> None:
        self.install_from_root = ifr

    @classmethod
    def for_sanguine_stable_json_load(cls):
        return cls('')


class SimpleUnpackArInstaller(ArInstaller):
    install_from_root: str | None

    def __init__(self, archive: Archive):
        super().__init__(archive)
        self.install_from_root = None

    def name(self) -> str:
        return 'SIMPLEUNPACK'

    def all_desired_files(self) -> Iterable[tuple[str, FileInArchive]]:  # list[relpath]
        out: list[tuple[str, FileInArchive]] = []
        lifr = len(self.install_from_root)
        for fia in self.archive.files:
            if fia.intra_path.startswith(self.install_from_root):
                out.append((fia.intra_path[lifr:], fia))
        return out

    def install_params(self) -> Any:
        return SimpleUnpackArInstallerInstallData(self.install_from_root)


class SimpleUnpackArInstallerPlugin(ArInstallerPluginBase):
    def name(self) -> str:
        return 'SIMPLEUNPACK'

    def guess_arinstaller_from_vfs(self, archive: Archive, modname: str,
                                   modfiles: dict[str, list[ArchiveFileRetriever]]) -> ArInstaller | None:
        candidate_roots: dict[str, int] = {}
        for modpath, rlist in modfiles.items():
            if __debug__:
                r0 = rlist[0]
                for r in rlist:
                    assert r.file_hash == r0.file_hash
            for r in rlist:
                assert isinstance(r, ArchiveFileRetriever)
                if r.archive_hash() == archive.archive_hash:
                    inarrpath = r.single_archive_retrievers[0].file_in_archive.intra_path
                    if inarrpath.endswith(modpath):
                        candidate_root = inarrpath[:-len(modpath)]
                        if candidate_root == '' or candidate_root.endswith('\\'):
                            if candidate_root not in candidate_roots:
                                candidate_roots[candidate_root] = 1
                            else:
                                candidate_roots[candidate_root] += 1

        if len(candidate_roots) == 0:
            return None
        out = SimpleUnpackArInstaller(archive)
        out.install_from_root = sorted(candidate_roots.items(), key=lambda x: x[1])[-1][0]

        return out

    def got_loaded_data(self, data: Any) -> None:
        assert False

    def data_for_saving(self) -> Any:
        assert False

    def extra_data_factory(self) -> ExtraArchiveDataFactory | None:
        return None

    def add_extra_data(self, arh: bytes, data: dict[str, Any]) -> None:
        assert False
