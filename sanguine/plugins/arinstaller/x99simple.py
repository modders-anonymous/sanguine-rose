from sanguine.common import *
from sanguine.helpers.archives import Archive, FileInArchive
from sanguine.helpers.arinstallers import ArInstallerPluginBase, ArInstaller
from sanguine.helpers.file_retriever import ArchiveFileRetriever


class SimpleArInstaller(ArInstaller):
    install_from_root: str

    def __init__(self, archive: Archive):
        super().__init__(archive)

    def all_desired_files(self) -> Iterable[tuple[str, FileInArchive]]:  # list[relpath]
        out: list[tuple[str, FileInArchive]] = []
        lifr = len(self.install_from_root)
        for fia in self.archive.files:
            if fia.intra_path.startswith(self.install_from_root):
                out.append((fia.intra_path[lifr:], fia))
        return out

    def install_data(self) -> str:
        return as_json({'root': self.install_from_root})


def _assert_arfh_in_arfiles_by_hash(arfh: bytes, arintra: str,
                                    arfiles_by_hash: dict[bytes, list[FileInArchive]]) -> None:
    assert arfh in arfiles_by_hash
    arfs = arfiles_by_hash[arfh]
    ok = False
    for arf in arfs:
        if arf.intra_path == arintra:
            ok = True
            break
    assert ok


'''
def _best_unmatched_from_arfiles_by_hash(arfh: bytes, arintra: str,
                                         arfiles_by_hash: dict[bytes, list[FileInArchive]]) -> str:
    assert arfh in arfiles_by_hash
    arfs = arfiles_by_hash[arfh]
    return arfs[0].intra_path  # TODO! - best matching name?
'''


class SimpleArInstallerPlugin(ArInstallerPluginBase):
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
        out = SimpleArInstaller(archive)
        out.install_from_root = sorted(candidate_roots.items(), key=lambda x: x[1])[-1][0]

        return out
