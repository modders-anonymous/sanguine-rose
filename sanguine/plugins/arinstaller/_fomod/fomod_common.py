from sanguine.common import *
from sanguine.gitdata.stable_json import StableJsonFlags


class FomodSrcDstFlags(IntFlag):
    NoFlags = 0
    AlwaysInstall = 0x1
    InstallIfUsable = 0x2


class FomodSrcDst:
    SANGUINE_JSON: list[tuple] = [('src', 'src', ''), ('dst', 'dst', ''),
                                  ('priority', 'pri', -1), ('flags', 'flags', FomodSrcDstFlags.NoFlags)]
    src: str | None
    dst: str | None
    priority: int
    flags: FomodSrcDstFlags

    def __init__(self) -> None:
        self.src = None
        self.dst = None
        self.priority = -1
        self.flags = FomodSrcDstFlags.NoFlags

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "FomodSrcDst":
        out = cls()
        out.src = ''
        out.dst = ''
        return out


class FomodFilesAndFolders:
    SANGUINE_JSON: list[tuple] = [('files', 'files', FomodSrcDst, StableJsonFlags.Unsorted),
                                  ('folders', 'folders', FomodSrcDst, StableJsonFlags.Unsorted)]
    files: list[FomodSrcDst]
    folders: list[FomodSrcDst]

    def __init__(self) -> None:
        self.files = []
        self.folders = []

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "FomodFilesAndFolders":
        return cls()

    def is_for_load(self) -> bool:
        return self.files == [] and self.folders == []


class FomodFlagDependency:
    SANGUINE_JSON: list[tuple] = [('name', 'name'), ('value', 'value')]
    name: str | None
    value: str | None

    def __init__(self) -> None:
        self.name = None
        self.value = None

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "FomodFlagDependency":
        out = cls()
        out.name = ''
        out.value = ''
        return out

    def is_for_load(self) -> bool:
        return self.name == '' and self.value == ''


class FomodFileDependencyState(IntEnum):
    NotInitialized = 0
    Active = 1
    Inactive = 2
    Missing = 3


class FomodFileDependency:
    SANGUINE_JSON: list[tuple] = [('file', 'file'), ('state', 'state', FomodFileDependencyState.NotInitialized)]
    file: str | None
    state: FomodFileDependencyState

    def __init__(self) -> None:
        self.file = None
        self.state = FomodFileDependencyState.NotInitialized

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "FomodFileDependency":
        out = cls()
        out.file = ''
        return out

    def is_for_load(self) -> bool:
        return self.file == '' and self.state == FomodFileDependencyState.NotInitialized


class FomodGameDependency:
    SANGUINE_JSON: list[tuple] = [('version', 'version')]
    version: str | None

    def __init__(self) -> None:
        self.version = None

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "FomodGameDependency":
        out = cls()
        out.version = ''
        return out

    def is_for_load(self) -> bool:
        return self.version == ''


class FomodSomeDependency:
    SANGUINE_JSON: list[tuple] = [('file_dependency', 'filedep'), ('flag_dependency', 'flagdep'),
                                  ('game_dependency', 'gamedep'), ('dependencies', 'deps')
                                  ]
    file_dependency: FomodFileDependency | None
    flag_dependency: FomodFlagDependency | None
    game_dependency: FomodGameDependency | None
    dependencies: "_Dependencies | None"

    def __init__(self, dep: "FomodFlagDependency|FomodFileDependency|FomodGameDependency|FomodDependencies") -> None:
        self.flag_dependency = None
        self.file_dependency = None
        self.game_dependency = None
        self.dependencies = None
        if isinstance(dep, FomodFlagDependency):
            self.flag_dependency = dep
        elif isinstance(dep, FomodFileDependency):
            self.file_dependency = dep
        elif isinstance(dep, FomodGameDependency):
            self.game_dependency = dep
        else:
            assert isinstance(dep, FomodDependencies)
            self.dependencies = dep

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "FomodSomeDependency":
        out = cls(FomodFileDependency.for_sanguine_stable_json_load())
        out.flag_dependency = FomodFlagDependency.for_sanguine_stable_json_load()
        out.game_dependency = FomodGameDependency.for_sanguine_stable_json_load()
        out.dependencies = FomodDependencies.for_sanguine_stable_json_load()
        return out

    def sanguine_stable_json_make_canonical(self) -> None:
        if self.flag_dependency is not None and self.flag_dependency.is_for_load():
            self.flag_dependency = None
        if self.file_dependency is not None and self.file_dependency.is_for_load():
            self.file_dependency = None
        if self.game_dependency is not None and self.game_dependency.is_for_load():
            self.game_dependency = None
        if self.dependencies is not None and self.dependencies.is_for_load():
            self.dependencies = None


class FomodDependencies:
    SANGUINE_JSON: list[tuple] = [('oroperator', 'or', False),
                                  ('dependencies', 'deps', FomodSomeDependency, StableJsonFlags.Unsorted)]
    oroperator: bool
    dependencies: list[FomodSomeDependency]

    def __init__(self) -> None:
        self.oroperator = False
        self.dependencies = []

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "FomodDependencies":
        return cls()

    def is_for_load(self) -> bool:
        return self.dependencies == [] and self.oroperator is False


class FomodType(IntEnum):
    NotInitialized = 0
    NotUsable = 1
    CouldBeUsable = 2
    Optional = 3
    Recommended = 4
    Required = 5


class FomodPattern:
    SANGUINE_JSON: list[tuple] = [('dependencies', 'deps'), ('type', 'type', FomodType.NotInitialized),
                                  ('files', 'files')]
    dependencies: FomodDependencies | None
    type: FomodType
    files: FomodFilesAndFolders | None

    def __init__(self) -> None:
        self.dependencies = None
        self.type = FomodType.NotInitialized
        self.files = None

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "FomodPattern":
        out = cls()
        out.dependencies = FomodDependencies()
        out.files = FomodFilesAndFolders()
        return out

    def sanguine_stable_json_make_canonical(self) -> None:
        if self.files is not None and self.files.is_for_load():
            self.files = None


class FomodTypeDescriptor:
    SANGUINE_JSON: list[tuple] = [('type', 'type'),
                                  ('patterns', 'patterns', FomodPattern, StableJsonFlags.Unsorted)]
    type: FomodType
    patterns: list[FomodPattern]

    def __init__(self) -> None:
        self.type = FomodType.NotInitialized
        self.patterns = []

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "FomodTypeDescriptor":
        return cls()


class FomodPlugin:
    SANGUINE_JSON: list[tuple] = [('name', 'name'), ('description', 'descr'), ('image', 'img'),
                                  ('files', 'files'), ('type_descriptor', 'tdescr'),
                                  ('condition_flags', 'conditionflags', FomodFlagDependency)]
    name: str | None
    description: str | None
    image: str | None
    files: FomodFilesAndFolders | None
    type_descriptor: FomodTypeDescriptor | None
    condition_flags: list[FomodFlagDependency]

    def __init__(self) -> None:
        self.name = None
        self.description = None
        self.image = None
        self.files = None
        self.type_descriptor = None
        self.condition_flags = []

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "FomodPlugin":
        out = cls()
        out.name = ''
        out.description = ''
        out.image = ''
        out.files = FomodFilesAndFolders.for_sanguine_stable_json_load()
        out.type_descriptor = FomodTypeDescriptor()
        return out

    def sanguine_stable_json_make_canonical(self) -> None:
        if self.files is not None and self.files.is_for_load():
            self.files = None


class FomodGroupSelect(IntEnum):
    NotInitialized = 0
    SelectAny = 1
    SelectAll = 2
    SelectExactlyOne = 3
    SelectAtMostOne = 4
    SelectAtLeastOne = 5


class FomodOrder(IntEnum):
    Ascending = 0
    Explicit = 1
    Descending = 2


class FomodGroup:
    SANGUINE_JSON: list[tuple] = [('name', 'name'), ('select', 'sel', FomodGroupSelect.SelectAny),
                                  ('order', 'ord', FomodOrder.Ascending),
                                  ('plugins', 'plugins', FomodPlugin, StableJsonFlags.Unsorted)]
    name: str | None
    select: FomodGroupSelect
    plugins: list[FomodPlugin]

    def __init__(self) -> None:
        self.name = None
        self.select = FomodGroupSelect.NotInitialized
        self.order = FomodOrder.Ascending
        self.plugins = []

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "FomodGroup":
        out = cls()
        out.name = ''
        return out


class FomodInstallStep:
    SANGUINE_JSON: list[tuple] = [('name', 'name'), ('order', 'ord', FomodOrder.Explicit),
                                  ('groups', 'groups', FomodGroup, StableJsonFlags.Unsorted),
                                  ('visible', 'visible')]
    name: str | None
    order: FomodOrder
    groups: list[FomodGroup]
    visible: FomodDependencies | None

    def __init__(self) -> None:
        self.name = None
        self.order = FomodOrder.Ascending
        self.groups = []
        self.visible = FomodDependencies()

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "FomodInstallStep":
        out = cls()
        out.name = ''
        return out


class FomodModuleConfig:
    SANGUINE_JSON: list[tuple] = [('module_name', 'modulename'), ('eye_candy_attr', 'eyecandy', (str, str)),
                                  ('module_dependencies', 'deps', FomodFileDependency, StableJsonFlags.Unsorted),
                                  ('required', 'required'), ('install_steps_order', 'order', FomodOrder.Ascending),
                                  ('install_steps', 'isteps', FomodInstallStep, StableJsonFlags.Unsorted),
                                  ('conditional_file_installs', 'conditional', FomodPattern, StableJsonFlags.Unsorted)]
    module_name: str | None
    eye_candy_attr: dict[str, str]
    module_dependencies: list[FomodFileDependency]
    required: FomodFilesAndFolders
    install_steps_order: FomodOrder
    install_steps: list[FomodInstallStep]
    conditional_file_installs: list[FomodPattern]

    def __init__(self) -> None:
        self.module_name = None
        self.eye_candy_attr = {}
        self.module_dependencies = []
        self.required = FomodFilesAndFolders()
        self.install_steps_order = FomodOrder.Ascending
        self.install_steps = []
        self.conditional_file_installs = []

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "FomodModuleConfig":
        out = cls()
        out.module_name = ''
        return out
