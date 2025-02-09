import zipfile

from sanguine.common import *
from sanguine.helpers.archives import ArchivePluginBase


class ZipArchivePlugin(ArchivePluginBase):
    def extensions(self) -> list[str]:
        return ['.zip']

    def extract(self, archive: str, listoffiles: list[str], targetpath: str) -> list[str | None]:
        info('Extracting {} file(s) from {}...'.format(len(listoffiles), archive))
        z = zipfile.ZipFile(archive)
        names = z.namelist()
        lof_normalized = []
        for f in listoffiles:
            normf = f.replace('\\', '/')
            lof_normalized.append(normf)
            assert normf in names
        out = []
        for f in lof_normalized:
            z.extract(f, path=targetpath)
            if os.path.isfile(targetpath + f):
                out.append(targetpath + f)
            else:
                warn('{} NOT EXTRACTED from {}'.format(f, archive))
                out.append(None)
        z.close()
        print('Extraction done')
        return out

    def extract_all(self, archive: str, targetpath: str) -> None:
        info('Extracting all from {}...'.format(archive))
        z = zipfile.ZipFile(archive)
        z.extractall(targetpath)
        z.close()
        info('Extraction done')
