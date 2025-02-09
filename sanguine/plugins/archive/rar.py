# we'll use unrar.exe which we install into tools folder.
# python rarfile module expects some rar installed anyway
import subprocess

from sanguine.common import *
from sanguine.helpers.archives import ArchivePluginBase


def _unrar_exe() -> str:
    return os.path.abspath(os.path.split(__file__)[0] + '\\..\\..\\..\\tools\\UnRAR.exe')


class RarArchivePlugin(ArchivePluginBase):
    def extensions(self) -> list[str]:
        return ['.rar']

    def extract(self, archive: str, listoffiles: list[str], targetpath: str) -> list[str | None]:
        info('Extracting {} files from {}...'.format(len(listoffiles), archive))
        assert is_normalized_dir_path(targetpath)

        listfilename = targetpath + '__@#$sanguine$#@__.lst'
        with open(listfilename, 'wt') as listfile:
            for f in listoffiles:
                listfile.write(f + '\n')
        syscall = [_unrar_exe(), 'x', archive, '@' + listfilename, targetpath]
        info(' '.join(syscall))
        subprocess.check_call(syscall)

        out = ArchivePluginBase.unarchived_list_helper(archive, listoffiles, targetpath)
        info('Extraction done')
        return out

    def extract_all(self, archive: str, targetpath: str) -> None:
        info('Extracting all from {}...'.format(archive))

        syscall = [_unrar_exe(), 'x', archive, targetpath]
        # warn(repr(syscall))
        subprocess.check_call(syscall)
        info('Extraction done')
