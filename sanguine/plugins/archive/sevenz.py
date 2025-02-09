# apparently, we cannot use py7zr module as it doesn't support BCJ2 coder
# we'll use 7z.exe which we install into tools folder instead
import os.path
import subprocess

from sanguine.common import *
from sanguine.helpers.archives import ArchivePluginBase


def _7z_exe() -> str:
    return os.path.abspath(os.path.split(__file__)[0] + '\\..\\..\\..\\tools\\7za.exe')


class SevenzArchivePlugin(ArchivePluginBase):
    def extensions(self) -> list[str]:
        return ['.7z']

    def extract(self, archive: str, listoffiles: list[str], targetpath: str) -> list[str | None]:
        info('Extracting from {}...'.format(archive))

        assert is_normalized_dir_path(targetpath)
        listfilename = targetpath + '__@#$sanguine$#@__.lst'
        with open(listfilename, 'wt') as listfile:
            for f in listoffiles:
                listfile.write(f + '\n')
        syscall = [_7z_exe(), 'x', '-o' + targetpath, archive, '@' + listfilename]
        info(' '.join(syscall))
        subprocess.check_call(syscall)

        out = ArchivePluginBase.unarchived_list_helper(archive, listoffiles, targetpath)
        info('Extraction done')
        return out

    def extract_all(self, archive: str, targetpath: str) -> None:
        info('Extracting all from {}...'.format(archive))

        syscall = [_7z_exe(), 'x', '-o' + targetpath, archive]
        # warn(repr(syscall))
        subprocess.check_call(syscall)
        info('Extraction done')
