# noinspection PyUnresolvedReferences
import xml.etree.ElementTree as ElementTree

from sanguine.common import *
from sanguine.gitdata.stable_json import from_stable_json, to_stable_json
from sanguine.helpers.archives import Archive
from sanguine.helpers.arinstallers import ArInstallerPluginBase, ArInstaller, ExtraArchiveDataFactory
from sanguine.helpers.file_retriever import ArchiveFileRetriever
# noinspection PyProtectedMember
from sanguine.plugins.arinstaller._fomod.fomod_common import FomodModuleConfig
# noinspection PyProtectedMember
from sanguine.plugins.arinstaller._fomod.fomod_guess import fomod_guess
# noinspection PyProtectedMember
from sanguine.plugins.arinstaller._fomod.fomod_parser import parse_fomod_moduleconfig


class _FomodArInstallerPluginExtraData:
    SANGUINE_JSON: list[tuple] = [('module_config', None)]
    module_config: FomodModuleConfig

    def __init__(self, mconfig: FomodModuleConfig) -> None:
        self.module_config = mconfig

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "_FomodArInstallerPluginExtraData":
        return cls(FomodModuleConfig.for_sanguine_stable_json_load())


class FomodExtraArchiveDataFactory(ExtraArchiveDataFactory):
    def name(self) -> str:
        return 'FOMOD'

    def extra_data(self, fullarchivedir: str) -> _FomodArInstallerPluginExtraData | None:  # returns stable_json data
        assert is_normalized_dir_path(fullarchivedir)
        fname = fullarchivedir + 'fomod\\moduleconfig.xml'
        if os.path.isfile(fname):
            with open_3rdparty_txt_file_autodetect(fname) as f:
                xml = ''
                for ln in f:
                    xml += ln
                root = ElementTree.fromstring(xml)
                modulecfg = parse_fomod_moduleconfig(root)
            return _FomodArInstallerPluginExtraData(modulecfg)
        return None


class _FomodArInstallerPluginInstallData:
    SANGUINE_JSON: list[tuple] = [('extra_data', 'data', (bytes, _FomodArInstallerPluginExtraData)),
                                  ('no_extra_data', 'empty', bytes),
                                  ('exceptions', 'exceptions', (bytes, str))]
    extra_data: dict[bytes, _FomodArInstallerPluginExtraData]
    no_extra_data: list[bytes]
    exceptions: dict[bytes, str]

    def __init__(self, extradata: dict[bytes, _FomodArInstallerPluginExtraData], noextradata: list[bytes],
                 exceptions: dict[bytes, str]) -> None:
        self.extra_data = extradata
        self.no_extra_data = noextradata
        self.exceptions = exceptions

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "_FomodArInstallerPluginInstallData":
        return cls({}, [], {})


class FomodArInstallerPlugin(ArInstallerPluginBase):
    extra_data: dict[bytes, _FomodArInstallerPluginExtraData] | None
    no_extra_data: list[bytes]
    exceptions: dict[bytes, str]

    def __init__(self):
        super().__init__()
        self.extra_data = None
        self.no_extra_data = []
        self.exceptions = {}

    def name(self) -> str:
        return 'FOMOD'

    def guess_arinstaller_from_vfs(self, archive: Archive, modname: str,
                                   modfiles: dict[str, list[ArchiveFileRetriever]]) -> ArInstaller | None:
        if archive.archive_hash not in self.extra_data:
            return None
        instdata: _FomodArInstallerPluginExtraData = self.extra_data[archive.archive_hash]
        return fomod_guess(instdata.module_config, archive, modfiles)

    def got_loaded_data(self, data: dict[str, Any]) -> None:
        target = _FomodArInstallerPluginInstallData.for_sanguine_stable_json_load()
        from_stable_json(target, data)
        self.extra_data = target.extra_data
        self.no_extra_data = target.no_extra_data
        self.exceptions = target.exceptions

    def data_for_saving(self) -> Any:
        return _FomodArInstallerPluginInstallData(self.extra_data, self.no_extra_data, self.exceptions)

    def extra_data_factory(self) -> ExtraArchiveDataFactory | None:
        return FomodExtraArchiveDataFactory()

    def add_extra_data(self, arh: bytes, data: _FomodArInstallerPluginExtraData | None | Exception) -> None:
        if data is None:
            self.no_extra_data.append(truncate_file_hash(arh))
            return
        if isinstance(data, Exception):
            self.exceptions[arh] = repr(data)
            return
        assert isinstance(data, _FomodArInstallerPluginExtraData)
        assert arh not in self.extra_data
        self.extra_data[arh] = data


if __name__ == '__main__':
    import sys
    import xml.etree.ElementTree as ElementTree

    argv = sys.argv[1:]
    if len(sys.argv) == 2 and sys.argv[1] == 'test':
        '''
        tfname = os.path.split(os.path.abspath(__file__))[0] + '\\ModuleConfig.xml'
        tree = ElementTree.parse(tfname)
        modulecfg = parse_fomod_moduleconfig(tree.getroot())
        asjson = as_json(modulecfg)
        info(asjson)
        '''
        tfname = os.path.split(os.path.abspath(__file__))[
                     0] + '\\..\\..\\..\\..\\sanguine-skyrim-root\\known-arinstaller-fomod-data.json'

        xdata = _FomodArInstallerPluginInstallData.for_sanguine_stable_json_load()

        with open(tfname, 'rt') as tf:
            known_json = json.load(tf)
            from_stable_json(xdata, known_json)

        new_json = to_stable_json(xdata)
        with open(tfname, 'wt') as tf:
            # noinspection PyTypeChecker
            json.dump(new_json, tf, indent=1)
