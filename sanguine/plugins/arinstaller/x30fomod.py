import xml.etree.ElementTree as ElementTree

from sanguine.common import *
from sanguine.helpers.archives import Archive, FileInArchive
from sanguine.helpers.arinstallers import ArInstallerPluginBase, ArInstaller, ExtraArchiveDataFactory
from sanguine.helpers.file_retriever import ArchiveFileRetriever
from sanguine.helpers.stable_json import from_stable_json, StableJsonFlags


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


# XML parsing

def _raise_unknown_tag(parent: ElementTree.Element | None, e: ElementTree.Element) -> None:
    raise SanguinicError('unknown tag in moduleconfig.xml: {} in {}'.format(
        e.tag, parent.tag if parent is not None else "''"))


def _raise_unknown_attr(e: ElementTree.Element, attrname: str) -> None:
    raise SanguinicError('unknown attribute in moduleconfig.xml: {} in {}'.format(
        attrname, e.tag))


def _raise_incomplete_tag(e: ElementTree.Element) -> None:
    raise SanguinicError('incomplete tag in moduleconfig.xml: {}'.format(e.tag))


def _check_no_attrs(n: ElementTree.Element) -> None:
    for an in n.attrib:
        _raise_unknown_attr(n, an)


def _check_no_children(n: ElementTree.Element) -> None:
    for child in n:
        _raise_unknown_tag(n, child)


class _SrcDst:
    priority: int
    src: str | None
    dst: str | None

    def __init__(self) -> None:
        self.src = None
        self.dst = None
        self.priority = -1


def _parse_src_dst(n: ElementTree.Element) -> _SrcDst:
    _check_no_children(n)
    out = _SrcDst()
    for an, av in n.attrib.items():
        if an == 'source':
            out.src = av
        elif an == 'destination':
            out.dst = av
        elif an == 'priority':
            out.priority = int(av)
        else:
            _raise_unknown_attr(n, an)
    if out.src is None or out.dst is None:
        _raise_incomplete_tag(n)
    return out


class _FilesAndFolders:
    files: list[_SrcDst]
    folders: list[_SrcDst]

    def __init__(self) -> None:
        self.files = []
        self.folders = []


def _parse_files_and_folders(n: ElementTree.Element) -> _FilesAndFolders:
    out = _FilesAndFolders()
    _check_no_attrs(n)
    for child in n:
        if child.tag == 'file':
            out.files.append(_parse_src_dst(child))
        elif child.tag == 'folder':
            out.folders.append(_parse_src_dst(child))
        else:
            _raise_unknown_tag(n, child)
    return out


class _Plugin:
    name: str
    description: str
    image: str
    files: _FilesAndFolders


def _parse_plugin(n: ElementTree.Element) -> _Plugin:
    out = _Plugin()
    for an, av in n.attrib.items():
        if an == 'name':
            out.name = av
        else:
            _raise_unknown_attr(n, an)
    for child in n:
        if child.tag == 'description':
            _check_no_attrs(child)
            _check_no_children(child)
            out.description = child.text
        elif child.tag == 'image':
            _check_no_children(child)
            for an, av in child.attrib.items():
                if an == 'path':
                    out.image = av
        elif child.tag == 'files':
            _check_no_attrs(child)
            out.files = _parse_files_and_folders(child)
        elif child.tag == 'typeDescriptor':
            pass  # TODO
        else:
            _raise_unknown_tag(n, child)
    return out


class _GroupSelect(Enum):
    SelectNotInitialized = 0
    SelectAny = 1
    SelectAll = 2
    SelectExactlyOne = 3
    SelectAtMostOne = 4
    SelectAtLeastOne = 5


class _Group:
    name: str | None
    select: _GroupSelect
    order: bool
    plugins: list[_Plugin]

    def __init__(self) -> None:
        self.name = None
        self.select = _GroupSelect.SelectNotInitialized
        self.order = False
        self.plugins = []


def _parse_group(e: ElementTree.Element) -> _Group:
    out = _Group()
    for an, av in e.attrib.items():
        if an == 'name':
            out.name = av
        elif an == 'type':
            match av:
                case 'SelectAny':
                    out.select = _GroupSelect.SelectAny
                case 'SelectAll':
                    out.select = _GroupSelect.SelectAll
                case 'SelectExactlyOne':
                    out.select = _GroupSelect.SelectExactlyOne
                case 'SelectAtMostOne':
                    out.select = _GroupSelect.SelectAtMostOne
                case 'SelectAtLeastOne':
                    out.select = _GroupSelect.SelectAtLeastOne
                case _:
                    _raise_unknown_attr(e, av)
        else:
            _raise_unknown_attr(e, an)
    for child in e:
        if child.tag == 'plugins':
            for an, av in child.attrib.items():
                if an == 'order':
                    match av:
                        case 'Explicit':
                            out.order = True
                        case _:
                            _raise_unknown_attr(e, av)
                else:
                    _raise_unknown_attr(e, an)

            for ch2 in child:
                if ch2.tag == 'plugin':
                    plg = _parse_plugin(ch2)
                    out.plugins.append(plg)
                else:
                    _raise_unknown_tag(child, ch2)
        else:
            _raise_unknown_tag(e, child)
    return out


class _InstallStep:
    name: str | None
    order: bool
    groups: list[_Group]

    def __init__(self) -> None:
        self.name = None
        self.order = False
        self.groups = []


def _parse_install_step(e: ElementTree.Element) -> _InstallStep:
    out = _InstallStep()
    for an, av in e.attrib.items():
        if an == 'name':
            out.name = av
        else:
            _raise_unknown_attr(e, an)
    for child in e:
        if child.tag == 'optionalFileGroups':
            for an, av in child.attrib.items():
                if an == 'order':
                    match av:
                        case 'Explicit':
                            out.order = True
                        case _:
                            _raise_unknown_attr(e, av)
                else:
                    _raise_unknown_attr(e, an)

            for ch2 in child:
                if ch2.tag == 'group':
                    plg = _parse_group(ch2)
                    out.groups.append(plg)
                else:
                    _raise_unknown_tag(child, ch2)
        else:
            _raise_unknown_tag(e, child)
    return out


class _FomodConfig:
    module_name: str | None
    required: _FilesAndFolders
    install_steps_order: bool
    install_steps: list[_InstallStep]

    def __init__(self) -> None:
        self.module_name = None
        self.required = _FilesAndFolders()
        self.install_steps_order = False
        self.install_steps = []


def _parse_xml_config(root: ElementTree.Element) -> _FomodConfig:
    out = _FomodConfig()
    if root.tag != 'config':
        _raise_unknown_tag(None, root)
    for child in root:
        if child.tag == 'moduleName':
            _check_no_attrs(child)
            _check_no_children(child)
            out.module_name = child.text
        elif child.tag == 'moduleImage':
            pass  # TODO
        elif child.tag == 'requiredInstallFiles':
            out.required = _parse_files_and_folders(child)
        elif child.tag == 'installSteps':
            for an, av in child.attrib.items():
                if an == 'order':
                    match av:
                        case 'Explicit':
                            out.order = True
                        case _:
                            _raise_unknown_attr(child, av)
                else:
                    _raise_unknown_attr(child, an)
            for ch2 in child:
                if ch2.tag == 'installStep':
                    istep = _parse_install_step(ch2)
                    out.install_steps.append(istep)
                else:
                    _raise_unknown_tag(child, ch2)
        else:
            _raise_unknown_tag(None, child)
    return out


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

    argv = sys.argv[1:]
    if len(sys.argv) == 2 and sys.argv[1] == 'test':
        tfname = os.path.split(os.path.abspath(__file__))[0] + '\\ModuleConfig.xml'
        tree = ElementTree.parse(tfname)
        modulecfg = _parse_xml_config(tree.getroot())
        asjson = as_json(modulecfg)
        info(asjson)
