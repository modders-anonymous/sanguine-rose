import zipfile

from sanguine.common import *
from sanguine.helpers.archives import ArchivePluginBase


class ZipArchivePlugin(ArchivePluginBase):
    def extensions(self) -> list[str]:
        return ['.zip']

    def extract(self, archive: str, listoffiles: list[str], targetpath: str) -> list[str | None]:
        info('Extracting {} file(s) from {}...'.format(len(listoffiles), archive))
        z = zipfile.ZipFile(archive)
        names = {n.lower(): n for n in z.namelist()}
        lof_normalized = []
        for f in listoffiles:
            normf = f.replace('\\', '/')
            if __debug__ and normf not in names:
                assert False
            lof_normalized.append(names[normf])
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
