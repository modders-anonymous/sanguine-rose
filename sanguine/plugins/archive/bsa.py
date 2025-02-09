from bethesda_structs.archive import BSAArchive

from sanguine.common import *
from sanguine.helpers.archives import ArchivePluginBase


class BsaArchivePlugin(ArchivePluginBase):
    def extensions(self) -> list[str]:
        return ['.bsa']

    def extract(self, archive: str, listoffiles: list[str], targetpath: str) -> list[str | None]:
        info('Extracting {} file(s) from {}...'.format(len(listoffiles), archive))
        bsa = BSAArchive.parse_file(archive)
        # names = bsa.container.file_names
        # print(names)
        # cannot extract partially, have to extract the whole thing
        bsa.extract(targetpath)
        out = ArchivePluginBase.unarchived_list_helper(archive, listoffiles, targetpath)
        info('Extraction done')
        return out

    def extract_all(self, archive: str, targetpath: str) -> None:
        info('Extracting all from {}...'.format(archive))
        bsa = BSAArchive.parse_file(archive)
        bsa.extract(targetpath)
        info('Extraction done')
