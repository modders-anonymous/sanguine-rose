from sanguine.common import *
from sanguine.helpers.archives import Archive, FileInArchive
from sanguine.helpers.arinstallers import ArInstallerPluginBase, ArInstaller, ExtraArchiveDataFactory
from sanguine.helpers.file_retriever import ArchiveFileRetriever
from sanguine.helpers.stable_json import from_stable_json, StableJsonFlags, to_stable_json
from sanguine.plugins.arinstaller._fomod.fomod_parser import parse_fomod_moduleconfig


class FomodArInstaller(ArInstaller):
    def __init__(self, archive: Archive):
        super().__init__(archive)

    def name(self) -> str:
        return 'FOMOD'

    def all_desired_files(self) -> Iterable[tuple[str, FileInArchive]]:  # list[relpath]
        assert False

    def install_params(self) -> Any:
        assert False


class _FomodArInstallerPluginExtraData:
    SANGUINE_JSON: list[tuple] = [('module_config', 'moduleconfig', str, StableJsonFlags.Unsorted)
                                  ]
    module_config: list[str]

    def __init__(self, mconfig: list[str]) -> None:
        self.module_config = mconfig

    @classmethod
    def for_stable_json_load(cls) -> "_FomodArInstallerPluginExtraData":
        return cls([])


class FomodExtraArchiveDataFactory(ExtraArchiveDataFactory):
    def name(self) -> str:
        return 'FOMOD'

    @abstractmethod
    def extra_data(self, fullarchivedir: str) -> _FomodArInstallerPluginExtraData | None:  # returns stable_json data
        assert is_normalized_dir_path(fullarchivedir)
        fname = fullarchivedir + 'fomod\\moduleconfig.xml'
        if os.path.isfile(fname):
            moduleconfig: list[str] = []
            with open_3rdparty_txt_file_autodetect(fname) as f:
                for ln in f:
                    moduleconfig.append(ln)
            return _FomodArInstallerPluginExtraData(moduleconfig)
        return None


class _FomodArInstallerPluginInstallData:
    SANGUINE_JSON: list[tuple] = [('extra_data', None, (bytes, _FomodArInstallerPluginExtraData))]
    extra_data: dict[bytes, _FomodArInstallerPluginExtraData]

    def __init__(self, extradata: dict[bytes, _FomodArInstallerPluginExtraData]) -> None:
        self.extra_data = extradata

    # @classmethod
    # def for_stable_json_load(cls) -> "_FomodArInstallerPluginInstallData":
    #    return cls({})


class FomodArInstallerPlugin(ArInstallerPluginBase):
    extra_data: dict[bytes, _FomodArInstallerPluginExtraData] | None

    def __init__(self):
        super().__init__()
        self.extra_data = None

    def name(self) -> str:
        return 'FOMOD'

    def guess_arinstaller_from_vfs(self, archive: Archive, modname: str,
                                   modfiles: dict[str, list[ArchiveFileRetriever]]) -> ArInstaller | None:
        return None

    def got_loaded_data(self, data: dict[str, Any]) -> None:
        target = _FomodArInstallerPluginInstallData({})
        from_stable_json(target, data)
        self.extra_data = target.extra_data

    def data_for_saving(self) -> Any:
        return _FomodArInstallerPluginInstallData(self.extra_data)

    def extra_data_factory(self) -> ExtraArchiveDataFactory | None:
        return FomodExtraArchiveDataFactory()

    def add_extra_data(self, arh: bytes, data: _FomodArInstallerPluginExtraData) -> None:
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
        with open(tfname, 'rt') as tf:
            known_json = json.load(tf)
        for h, v in known_json.items():
            mc = v['moduleconfig']
            xml = ''
            for tln in mc:
                xml += tln
            tree = ElementTree.fromstring(xml)
            modulecfg = parse_fomod_moduleconfig(tree)

            # asjson = as_json(modulecfg)
            # info(asjson)
            stable = to_stable_json(modulecfg)
            info(stable)
