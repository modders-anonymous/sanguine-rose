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


def _check_no_text(e: ElementTree.Element) -> None:
    if e.text is not None and e.text.strip() != '':
        raise SanguinicError('unexpected text in moduleconfig.xml: {}'.format(e.tag))


def _check_no_attrs(n: ElementTree.Element) -> None:
    for an in n.attrib:
        _raise_unknown_attr(n, an)


def _check_no_children(n: ElementTree.Element) -> None:
    for child in n:
        _raise_unknown_tag(n, child)


def _text(e: ElementTree.Element) -> str:
    return e.text.strip() if e.text is not None else ''


class _SrcDstFlags(Flag):
    NoFlags = 0
    AlwaysInstall = 0x1
    InstallIfUsable = 0x2


class _SrcDst:
    priority: int
    src: str | None
    dst: str | None
    flags: _SrcDstFlags

    def __init__(self) -> None:
        self.src = None
        self.dst = None
        self.priority = -1
        self.flags = _SrcDstFlags.NoFlags


def _parse_src_dst(n: ElementTree.Element) -> _SrcDst:
    _check_no_text(n)
    _check_no_children(n)
    out = _SrcDst()
    for an, av in n.attrib.items():
        match an:
            case 'source':
                out.src = av
            case 'destination':
                out.dst = av
            case 'priority':
                out.priority = int(av)
            case 'alwaysInstall':
                out.flags |= _SrcDstFlags.AlwaysInstall
            case 'installIfUsable':
                out.flags |= _SrcDstFlags.InstallIfUsable
            case _:
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
    _check_no_text(n)
    _check_no_attrs(n)
    for child in n:
        match child.tag:
            case 'file':
                out.files.append(_parse_src_dst(child))
            case 'folder':
                out.folders.append(_parse_src_dst(child))
            case _:
                _raise_unknown_tag(n, child)
    return out


class _FlagDependency:
    name: str | None
    value: str | None

    def __init__(self) -> None:
        self.name = None
        self.value = None


def _parse_flag_dependency(n: ElementTree.Element) -> _FlagDependency:
    out = _FlagDependency()
    _check_no_text(n)
    _check_no_children(n)
    for an, av in n.attrib.items():
        match an:
            case 'flag':
                out.name = av
            case 'value':
                out.value = av
            case _:
                _raise_unknown_attr(n, an)
    return out


def _parse_flag(n: ElementTree.Element) -> _FlagDependency:
    out = _FlagDependency()
    _check_no_children(n)
    for an, av in n.attrib.items():
        if an == 'name':
            out.name = av
        else:
            _raise_unknown_attr(n, av)
    out.value = _text(n)
    return out


class _FileDependencyState(IntEnum):
    NotInitialized = 0
    Active = 1
    Inactive = 2
    Missing = 3


class _FileDependency:
    file: str | None
    state: _FileDependencyState

    def __init__(self) -> None:
        self.file = None
        self.state = _FileDependencyState.NotInitialized


def _parse_file_dependency(n: ElementTree.Element) -> _FileDependency:
    out = _FileDependency()
    _check_no_text(n)
    _check_no_children(n)
    for an, av in n.attrib.items():
        match an:
            case 'file':
                out.file = av
            case 'state':
                match av:
                    case 'Active':
                        out.state = _FileDependencyState.Active
                    case 'Inactive':
                        out.state = _FileDependencyState.Inactive
                    case 'Missing':
                        out.state = _FileDependencyState.Missing
                    case _:
                        _raise_unknown_attr(n, av)
            case _:
                _raise_unknown_attr(n, an)
    return out


class _GameDependency:
    version: str | None

    def __init__(self) -> None:
        self.version = None


def _parse_game_dependency(n: ElementTree.Element) -> _GameDependency:
    out = _GameDependency()
    _check_no_text(n)
    _check_no_children(n)
    for an, av in n.attrib.items():
        if an == 'version':
            out.version = av
        else:
            _raise_unknown_attr(n, av)
    return out


class _Dependencies:
    oroperator: bool
    dependencies: "list[_FileDependency|_FlagDependency|_GameDependency|_Dependencies]"

    def __init__(self) -> None:
        self.oroperator = False
        self.dependencies = []


def _parse_dependencies(n: ElementTree.Element) -> _Dependencies:
    out = _Dependencies()
    out.oroperator = False
    for an, av in n.attrib.items():
        if an == 'operator':
            match av:
                case 'Or':
                    out.oroperator = True
                case 'And':
                    out.oroperator = False
                case _:
                    _raise_unknown_attr(n, av)
    for child in n:
        match child.tag:
            case 'fileDependency':
                out.dependencies.append(_parse_file_dependency(child))
            case 'flagDependency':
                out.dependencies.append(_parse_flag_dependency(child))
            case 'gameDependency':
                out.dependencies.append(_parse_game_dependency(child))
            case 'dependencies':
                out.dependencies.append(_parse_dependencies(child))
            case _:
                _raise_unknown_tag(n, child)
    return out


class _FomodType(IntEnum):
    NotInitialized = 0
    NotUsable = 1
    CouldBeUsable = 2
    Optional = 3
    Recommended = 4
    Required = 5


def _parse_fomod_type(n: ElementTree.Element) -> _FomodType:
    _check_no_text(n)
    _check_no_children(n)
    for an, av in n.attrib.items():
        if an == 'name':
            match av:
                case 'Recommended':
                    return _FomodType.Recommended
                case 'Optional':
                    return _FomodType.Optional
                case 'Required':
                    return _FomodType.Required
                case 'NotUsable':
                    return _FomodType.NotUsable
                case 'CouldBeUsable':
                    return _FomodType.CouldBeUsable
                case _:
                    _raise_unknown_attr(n, av)
    _raise_incomplete_tag(n)


class _Pattern:
    dependencies: _Dependencies | None
    type: _FomodType
    files: _FilesAndFolders | None

    def __init__(self) -> None:
        self.dependencies = None
        self.type = _FomodType.NotInitialized
        self.files = None


def _parse_pattern(n: ElementTree.Element) -> _Pattern:
    out = _Pattern()
    _check_no_text(n)
    _check_no_attrs(n)
    for child in n:
        match child.tag:
            case 'dependencies':
                out.dependencies = _parse_dependencies(child)
            case 'type':
                out.type = _parse_fomod_type(child)
            case 'files':
                out.files = _parse_files_and_folders(child)
            case _:
                _raise_unknown_tag(n, child)
    return out


def _parse_patterns(n: ElementTree.Element) -> list[_Pattern]:
    out = []
    _check_no_text(n)
    _check_no_attrs(n)
    for child in n:
        if child.tag == 'pattern':
            out.append(_parse_pattern(child))
        else:
            _raise_unknown_tag(n, child)
    return out


class _TypeDescriptor:
    type: _FomodType
    patterns: list[_Pattern]

    def __init__(self) -> None:
        self.type = _FomodType.NotInitialized
        self.patterns = []


def _parse_type_descriptor(n: ElementTree.Element) -> _TypeDescriptor:
    out = _TypeDescriptor()
    _check_no_text(n)
    _check_no_attrs(n)
    for child in n:
        match child.tag:
            case 'type':
                out.type = _parse_fomod_type(child)
            case 'dependencyType':
                for ch2 in child:
                    match ch2.tag:
                        case 'defaultType':
                            out.type = _parse_fomod_type(ch2)
                        case 'patterns':
                            out.patterns = _parse_patterns(ch2)
                        case _:
                            _raise_unknown_tag(child, ch2)
    return out


class _Plugin:
    name: str | None
    description: str | None
    image: str | None
    files: _FilesAndFolders | None
    type_descriptor: _TypeDescriptor | None
    condition_flags: list[_FlagDependency]

    def __init__(self) -> None:
        self.name = None
        self.description = None
        self.image = None
        self.files = None
        self.type_descriptor = None
        self.condition_flags = []


def _parse_plugin(n: ElementTree.Element) -> _Plugin:
    out = _Plugin()
    for an, av in n.attrib.items():
        match an:
            case 'name':
                out.name = av
            case _:
                _raise_unknown_attr(n, an)
    for child in n:
        match child.tag:
            case 'description':
                _check_no_attrs(child)
                _check_no_children(child)
                out.description = _text(child)
            case 'image':
                _check_no_text(child)
                _check_no_children(child)
                for an, av in child.attrib.items():
                    if an == 'path':
                        out.image = av
            case 'files':
                _check_no_text(child)
                _check_no_attrs(child)
                out.files = _parse_files_and_folders(child)
            case 'typeDescriptor':
                out.type_descriptor = _parse_type_descriptor(child)
            case 'conditionFlags':
                _check_no_text(child)
                _check_no_attrs(child)
                for ch2 in child:
                    if ch2.tag == 'flag':
                        out.condition_flags.append(_parse_flag(ch2))
                    else:
                        _raise_unknown_tag(child, ch2)
            case _:
                _raise_unknown_tag(n, child)
    return out


class _GroupSelect(IntEnum):
    NotInitialized = 0
    SelectAny = 1
    SelectAll = 2
    SelectExactlyOne = 3
    SelectAtMostOne = 4
    SelectAtLeastOne = 5


class _FomodOrder(IntEnum):
    NotPresent = 0
    Explicit = 1
    Descending = 2
    Ascending = 3


def _parse_order_attr(e, av: str) -> _FomodOrder:
    match av:
        case 'Explicit':
            return _FomodOrder.Explicit
        case 'Descending':
            return _FomodOrder.Descending
        case 'Ascending':
            return _FomodOrder.Descending
        case _:
            _raise_unknown_attr(e, av)


class _Group:
    name: str | None
    select: _GroupSelect
    order: _FomodOrder
    plugins: list[_Plugin]

    def __init__(self) -> None:
        self.name = None
        self.select = _GroupSelect.NotInitialized
        self.order = _FomodOrder.NotPresent
        self.plugins = []


def _parse_group(e: ElementTree.Element) -> _Group:
    out = _Group()
    for an, av in e.attrib.items():
        match an:
            case 'name':
                out.name = av
            case 'type':
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
            case _:
                _raise_unknown_attr(e, an)
    for child in e:
        if child.tag == 'plugins':
            for an, av in child.attrib.items():
                if an == 'order':
                    out.order = _parse_order_attr(child, av)
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
    order: _FomodOrder
    groups: list[_Group]
    visible: _Dependencies | None

    def __init__(self) -> None:
        self.name = None
        self.order = _FomodOrder.NotPresent
        self.groups = []
        self.visible = _Dependencies()


def _parse_install_step(e: ElementTree.Element) -> _InstallStep:
    out = _InstallStep()
    for an, av in e.attrib.items():
        if an == 'name':
            out.name = av
        else:
            _raise_unknown_attr(e, an)
    for child in e:
        match child.tag:
            case 'optionalFileGroups':
                for an, av in child.attrib.items():
                    if an == 'order':
                        out.order = _parse_order_attr(child, av)
                    else:
                        _raise_unknown_attr(e, an)

                for ch2 in child:
                    if ch2.tag == 'group':
                        plg = _parse_group(ch2)
                        out.groups.append(plg)
                    else:
                        _raise_unknown_tag(child, ch2)
            case 'visible':
                _check_no_text(child)
                _check_no_attrs(child)
                for ch2 in child:
                    if ch2.tag == 'flagDependency':
                        out.visible.dependencies.append(_parse_flag_dependency(ch2))
                    if ch2.tag == 'dependencies':
                        deps = _parse_dependencies(ch2)
                        out.visible.dependencies.append(deps)
            case _:
                _raise_unknown_tag(e, child)
    return out


class _FomodConfig:
    module_name: str | None
    eye_candy_attr: dict[str, str]
    module_dependencies: list[_FileDependency]
    required: _FilesAndFolders
    install_steps_order: bool
    install_steps: list[_InstallStep]
    conditional_file_installs: list[_Pattern]

    def __init__(self) -> None:
        self.module_name = None
        self.eye_candy_attr = {}
        self.module_dependencies = []
        self.required = _FilesAndFolders()
        self.install_steps_order = False
        self.install_steps = []
        self.conditional_file_installs = []


def _parse_xml_config(root: ElementTree.Element) -> _FomodConfig:
    out = _FomodConfig()
    if root.tag != 'config':
        _raise_unknown_tag(None, root)
    for child in root:
        match child.tag:
            case 'moduleName':
                for an, av in child.attrib.items():
                    match an:
                        case 'colour':
                            out.eye_candy_attr['colour'] = av
                        case 'position':
                            out.eye_candy_attr['position'] = av
                        case _:
                            _raise_unknown_attr(child, an)
                _check_no_children(child)
                out.module_name = _text(child)
            case 'moduleImage':
                _check_no_text(child)
                _check_no_children(child)
                for an, av in child.attrib.items():
                    match an:
                        case 'path':
                            out.eye_candy_attr['image.path'] = av
                        case 'showImage':
                            out.eye_candy_attr['image.show'] = av
                        case 'height':
                            out.eye_candy_attr['image.height'] = av
                        case 'showFade':
                            out.eye_candy_attr['image.showfade'] = av
                        case _:
                            _raise_unknown_attr(child, av)
            case 'requiredInstallFiles':
                out.required = _parse_files_and_folders(child)
            case 'installSteps':
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
            case 'conditionalFileInstalls':
                _check_no_text(child)
                _check_no_attrs(child)
                for ch2 in child:
                    if ch2.tag == 'patterns':
                        _check_no_text(ch2)
                        _check_no_attrs(ch2)
                        out.conditional_file_installs = _parse_patterns(ch2)
                    else:
                        _raise_unknown_tag(child, ch2)
            case 'moduleDependencies':
                _check_no_text(child)
                _check_no_attrs(child)
                for ch2 in child:
                    if ch2.tag == 'fileDependency':
                        out.module_dependencies.append(_parse_file_dependency(ch2))
                    else:
                        _raise_unknown_tag(child, ch2)
            case _:
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
        '''
        tfname = os.path.split(os.path.abspath(__file__))[0] + '\\ModuleConfig.xml'
        tree = ElementTree.parse(tfname)
        modulecfg = _parse_xml_config(tree.getroot())
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
            modulecfg = _parse_xml_config(tree)
            asjson = as_json(modulecfg)
            info(asjson)
