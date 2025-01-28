import xml.etree.ElementTree as ElementTree

from sanguine.common import *
from sanguine.helpers.stable_json import StableJsonFlags


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


class _SrcDstFlags(IntFlag):
    NoFlags = 0
    AlwaysInstall = 0x1
    InstallIfUsable = 0x2


class _SrcDst:
    SANGUINE_JSON: list[tuple] = [('src', 'src', ''), ('dst', 'dst', ''),
                                  ('priority', 'pri', -1), ('flags', 'flags', _SrcDstFlags.NoFlags)]
    src: str | None
    dst: str | None
    priority: int
    flags: _SrcDstFlags

    def __init__(self) -> None:
        self.src = None
        self.dst = None
        self.priority = -1
        self.flags = _SrcDstFlags.NoFlags

    @classmethod
    def for_stable_json_load(cls) -> "_SrcDst":
        out = cls()
        out.src = ''
        out.dst = ''
        return out


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
    SANGUINE_JSON: list[tuple] = [('files', 'files', _SrcDst, StableJsonFlags.Unsorted),
                                  ('folders', 'folders', _SrcDst, StableJsonFlags.Unsorted)]
    files: list[_SrcDst]
    folders: list[_SrcDst]

    def __init__(self) -> None:
        self.files = []
        self.folders = []

    @classmethod
    def for_stable_json_load(cls) -> "_FilesAndFolders":
        return cls()


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
    SANGUINE_JSON: list[tuple] = [('name', 'name'), ('value', 'value')]
    name: str | None
    value: str | None

    def __init__(self) -> None:
        self.name = None
        self.value = None

    @classmethod
    def for_stable_json_load(cls) -> "_FlagDependency":
        out = cls()
        out.name = ''
        out.value = ''
        return out


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
    SANGUINE_JSON: list[tuple] = [('file', 'file'), ('state', 'state', _FileDependencyState.NotInitialized)]
    file: str | None
    state: _FileDependencyState

    def __init__(self) -> None:
        self.file = None
        self.state = _FileDependencyState.NotInitialized

    @classmethod
    def for_stable_json_load(cls) -> "_FileDependency":
        out = cls()
        out.file = ''
        return out


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
    SANGUINE_JSON: list[tuple] = [('version', 'version')]
    version: str | None

    def __init__(self) -> None:
        self.version = None

    @classmethod
    def for_stable_json_load(cls) -> "_GameDependency":
        out = cls()
        out.version = ''
        return out


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


class _SomeDependency:
    SANGUINE_JSON: list[tuple] = [('file_dependency', 'filedep'), ('flag_dependency', 'flagdep'),
                                  ('game_dependency', 'gamedep'), ('dependencies', 'deps')
                                  ]
    file_dependency: _FileDependency | None
    flag_dependency: _FlagDependency | None
    game_dependency: _GameDependency | None
    dependencies: "_Dependencies | None"

    def __init__(self, dep: "_FlagDependency|_FileDependency|_GameDependency|_Dependencies") -> None:
        self.flag_dependency = None
        self.file_dependency = None
        self.game_dependency = None
        self.dependencies = None
        if isinstance(dep, _FlagDependency):
            self.flag_dependency = dep
        elif isinstance(dep, _FileDependency):
            self.file_dependency = dep
        elif isinstance(dep, _GameDependency):
            self.game_dependency = dep
        else:
            assert isinstance(dep, _Dependencies)
            self.dependencies = dep

    @classmethod
    def for_stable_json_load(cls) -> "_SomeDependency":
        out = cls(_FileDependency())
        out.flag_dependency = _FlagDependency()
        out.game_dependency = _GameDependency()
        out.dependencies = _Dependencies()
        return out


class _Dependencies:
    SANGUINE_JSON: list[tuple] = [('oroperator', 'or', False),
                                  ('dependencies', 'deps', _SomeDependency, StableJsonFlags.Unsorted)]
    oroperator: bool
    dependencies: list[_SomeDependency]

    def __init__(self) -> None:
        self.oroperator = False
        self.dependencies = []

    @classmethod
    def for_stable_json_load(cls) -> "_Dependencies":
        return cls()


def _parse_some_dependency(n: ElementTree.Element) -> _SomeDependency:
    match n.tag:
        case 'fileDependency':
            return _SomeDependency(_parse_file_dependency(n))
        case 'flagDependency':
            return _SomeDependency(_parse_flag_dependency(n))
        case 'gameDependency':
            return _SomeDependency(_parse_game_dependency(n))
        case 'dependencies':
            return _SomeDependency(_parse_dependencies(n))
        case _:
            _raise_unknown_tag(n, n)


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
        out.dependencies.append(_parse_some_dependency(child))
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
    SANGUINE_JSON: list[tuple] = [('dependencies', 'deps'), ('type', 'type', _FomodType.NotInitialized),
                                  ('files', 'files')]
    dependencies: _Dependencies | None
    type: _FomodType
    files: _FilesAndFolders | None

    def __init__(self) -> None:
        self.dependencies = None
        self.type = _FomodType.NotInitialized
        self.files = None

    @classmethod
    def for_stable_json_load(cls) -> "_Pattern":
        out = cls()
        out.dependencies = _Dependencies()
        out.files = _FilesAndFolders()
        return out


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
    SANGUINE_JSON: list[tuple] = [('type', 'type'),
                                  ('patterns', 'patterns', _Pattern, StableJsonFlags.Unsorted)]
    type: _FomodType
    patterns: list[_Pattern]

    def __init__(self) -> None:
        self.type = _FomodType.NotInitialized
        self.patterns = []

    @classmethod
    def for_stable_json_load(cls) -> "_TypeDescriptor":
        return cls()


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
    SANGUINE_JSON: list[tuple] = [('name', 'name'), ('description', 'descr'), ('image', 'img'),
                                  ('files', 'files'), ('type_descriptor', 'tdescr'),
                                  ('condition_flags', 'conditionflags', _FlagDependency)]
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

    @classmethod
    def for_stable_json_load(cls) -> "_Plugin":
        out = cls()
        out.name = ''
        out.description = ''
        out.image = ''
        out.files = _FilesAndFolders()
        out.type_descriptor = _TypeDescriptor()
        return out


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
    Ascending = 0
    Explicit = 1
    Descending = 2


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
    SANGUINE_JSON: list[tuple] = [('name', 'name'), ('select', 'sel', _GroupSelect.SelectAny),
                                  ('order', 'ord', _FomodOrder.Ascending),
                                  ('plugins', 'plugins', _Plugin, StableJsonFlags.Unsorted)]
    name: str | None
    select: _GroupSelect
    plugins: list[_Plugin]

    def __init__(self) -> None:
        self.name = None
        self.select = _GroupSelect.NotInitialized
        self.order = _FomodOrder.Ascending
        self.plugins = []

    @classmethod
    def for_stable_json_load(cls) -> "_Group":
        out = cls()
        out.name = ''
        return out


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
    SANGUINE_JSON: list[tuple] = [('name', 'name'), ('order', 'ord', _FomodOrder.Explicit),
                                  ('groups', 'groups', _Group, StableJsonFlags.Unsorted),
                                  ('visible', 'visible')]
    name: str | None
    order: _FomodOrder
    groups: list[_Group]
    visible: _Dependencies | None

    def __init__(self) -> None:
        self.name = None
        self.order = _FomodOrder.Ascending
        self.groups = []
        self.visible = _Dependencies()

    @classmethod
    def for_stable_json_load(cls) -> "_InstallStep":
        out = cls()
        out.name = ''
        return out


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
                    out.visible.dependencies.append(_parse_some_dependency(ch2))
            case _:
                _raise_unknown_tag(e, child)
    return out


class FomodModuleConfig:
    SANGUINE_JSON: list[tuple] = [('module_name', 'modulename'), ('eye_candy_attr', 'eyecandy', (str, str)),
                                  ('module_dependencies', 'deps', _FileDependency, StableJsonFlags.Unsorted),
                                  ('required', 'required'), ('install_steps_order', 'order', _FomodOrder.Ascending),
                                  ('install_steps', 'isteps', _InstallStep, StableJsonFlags.Unsorted),
                                  ('conditional_file_installs', 'conditional', _Pattern, StableJsonFlags.Unsorted)]
    module_name: str | None
    eye_candy_attr: dict[str, str]
    module_dependencies: list[_FileDependency]
    required: _FilesAndFolders
    install_steps_order: _FomodOrder
    install_steps: list[_InstallStep]
    conditional_file_installs: list[_Pattern]

    def __init__(self) -> None:
        self.module_name = None
        self.eye_candy_attr = {}
        self.module_dependencies = []
        self.required = _FilesAndFolders()
        self.install_steps_order = _FomodOrder.Ascending
        self.install_steps = []
        self.conditional_file_installs = []

    @classmethod
    def for_stable_json_load(cls) -> "FomodModuleConfig":
        out = cls()
        out.module_name = ''
        return out


def parse_fomod_moduleconfig(root: ElementTree.Element) -> FomodModuleConfig:
    out = FomodModuleConfig()
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
                        out.order = _parse_order_attr(child, av)
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
