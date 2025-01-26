import re

from sanguine.common import *
from sanguine.helpers.archives import Archive, FileInArchive
from sanguine.helpers.arinstallers import ArInstallerPluginBase, ArInstaller
from sanguine.helpers.file_retriever import ArchiveFileRetriever


class BainArInstaller(ArInstaller):
    bain_folders: list[str]

    def __init__(self, archive: Archive):
        super().__init__(archive)

    def name(self) -> str:
        return 'BAIN'

    def all_desired_files(self) -> Iterable[tuple[str, FileInArchive]]:  # list[relpath]
        if self.bain_folders[0].startswith('04'):
            pass

        out: list[tuple[str, FileInArchive]] = []
        returned: dict[str, bytes] = {}  # detect and remove duplicates: we must never return duplicate path

        srch = FastSearchOverPartialStrings([(bf, True) for bf in self.bain_folders])
        for fia in self.archive.files:
            found = srch.find_val_for_str(fia.intra_path)
            if found is not None and found[1]:
                assert fia.intra_path.startswith(found[0])
                rpath = fia.intra_path[len(found[0]):]
                if rpath in returned:
                    if returned[rpath] != fia.file_hash:
                        # overwriting
                        for i in range(len(out)):
                            if out[i][0] == rpath:
                                out[i] = (rpath, fia)
                                break
                    pass  # do nothing; this target file is already installed with the same hash
                else:
                    out.append((rpath, fia))
                    returned[rpath] = fia.file_hash
        return out

    def install_params(self) -> dict[str, Any]:
        return {'bain': self.bain_folders}


class BainArInstallerPlugin(ArInstallerPluginBase):
    def guess_arinstaller_from_vfs(self, archive: Archive, modname: str,
                                   modfiles: dict[str, list[ArchiveFileRetriever]]) -> ArInstaller | None:
        bainfolders: dict[str, int] = {}
        ntotal = 0
        nbain = 0
        bainpattern = re.compile(r'([0-9][0-9]+ [^\\]*\\)')
        for f in archive.files:
            ntotal += 1
            m = bainpattern.match(f.intra_path)
            if m:
                m1 = m.group(1)
                if m1 not in bainfolders:
                    bainfolders[m1] = 0
                nbain += 1

        if len(bainfolders) == 0:
            return None

        bfsorted = sorted([bf for bf in bainfolders])
        if not bfsorted[0].startswith('00 ') and not bfsorted[0].startswith('000 '):
            return None

        srch = FastSearchOverPartialStrings([(bf, True) for bf in bainfolders])
        for modpath, rlist in modfiles.items():
            if __debug__:
                r0 = rlist[0]
                for r in rlist:
                    assert r.file_hash == r0.file_hash

            unique_folder = None
            for r in rlist:
                assert isinstance(r, ArchiveFileRetriever)
                if r.archive_hash() == archive.archive_hash:
                    inarrpath = r.single_archive_retrievers[0].file_in_archive.intra_path
                    found = srch.find_val_for_str(inarrpath)
                    if found is not None and found[1]:
                        assert inarrpath.startswith(found[0])
                        if unique_folder is None:
                            unique_folder = found[0]
                        else:
                            unique_folder = False
                            break

            if unique_folder is not None and unique_folder is not False:
                assert isinstance(unique_folder, str)
                bainfolders[unique_folder] += 1

        out = BainArInstaller(archive)
        out.bain_folders = sorted([bf for bf in bainfolders if bainfolders[bf] > 0])
        # TODO: check that overwrites are correct
        return out
