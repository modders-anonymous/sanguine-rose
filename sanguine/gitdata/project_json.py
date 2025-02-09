from sanguine.common import *
from sanguine.gitdata.stable_json import StableJsonFlags
from sanguine.helpers.file_retriever import GithubFileRetriever


class ProjectExtraArchiveFile:
    SANGUINE_JSON: list[tuple] = [('target_file_name', 't'), ('intra_path', 's', ''), ('intra_paths', 'sl', str)]
    target_file_name: str
    intra_path: str
    intra_paths: list[str]

    def __init__(self, targetfname: str, intra: list[str]) -> None:
        self.target_file_name = targetfname
        if len(intra) == 1:
            self.intra_path = intra[0]
            self.intra_paths = []
        else:
            self.intra_paths = intra
            self.intra_path = ''

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "ProjectExtraArchiveFile":
        return cls('', [''])


class ProjectExtraArchive:
    SANGUINE_JSON: list[tuple[str, str]] = [('archive_hash', 'arh'), ('archive_idx', 'ar'),
                                            ('extra_files', 'files', ProjectExtraArchiveFile)]
    archive_hash: bytes | None
    archive_idx: int | None
    extra_files: list[ProjectExtraArchiveFile]

    def __init__(self, aid: bytes | int) -> None:
        if isinstance(aid, bytes):
            self.archive_hash = aid
            self.archive_idx = None
        else:
            assert isinstance(aid, int)
            self.archive_hash = None
            self.archive_idx = aid
        self.extra_files = []

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "ProjectExtraArchive":
        out = cls(0)
        out.archive_idx = 0
        out.archive_hash = b''
        return out


class ProjectInstaller:
    SANGUINE_JSON: list[tuple[str, str]] = [('archive_hash', 'h'), ('installer_type', 'type'),
                                            ('installer_params', 'params'),
                                            ('skip', 'skip', str)]
    archive_hash: bytes
    installer_type: str
    installer_params: Any
    skip: list[str]

    def __init__(self, arhash: bytes, insttype: str, instparams: Any, skip: list[str]) -> None:
        self.archive_hash = arhash
        self.installer_type = insttype
        self.installer_params = instparams
        self.skip = skip

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "ProjectInstaller":
        return cls(b'', '', {}, [])


class ProjectModTool:
    SANGUINE_JSON: list[tuple[str, str]] = [('name', 'name'), ('param', 'param')]
    name: str
    param: Any

    def __init__(self, name: str, param: Any) -> None:
        self.name = name
        self.param = param

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "ProjectModTool":
        return cls('', '')


class ProjectModPatch:
    SANGUINE_JSON: list[tuple[str, str]] = [('file', 'f'), ('type', 't'), ('param', 'p')]
    file: str
    type: str
    param: Any

    def __init__(self, file: str, typ: str, param: Any) -> None:
        self.file = file
        self.type = typ
        self.param = param

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "ProjectModPatch":
        return cls('', '', None)


class ProjectMod:
    SANGUINE_JSON: list[tuple[str, str]] = [('mod_name', 'name'),
                                            ('zero_files', 'zero', str),
                                            ('github_files', 'github', (str, GithubFileRetriever)),
                                            ('installers', 'installers', ProjectInstaller, StableJsonFlags.Unsorted),
                                            ('remaining_archives', 'xarchives', ProjectExtraArchive),
                                            ('unknown_files_by_tools', 'unknownbytools', str),
                                            ('unknown_files', 'unknown', str),
                                            ('mod_tools', 'modtools', ProjectModTool),
                                            ('patches', 'patches', ProjectModPatch)]
    mod_name: str | None
    zero_files: list[str] | None
    github_files: dict[str, GithubFileRetriever] | None
    installers: list[ProjectInstaller] | None
    remaining_archives: list[ProjectExtraArchive] | None
    unknown_files: list[str] | None
    unknown_files_by_tools: list[str] | None
    mod_tools: list[ProjectModTool] | None
    patches: list[ProjectModPatch] | None

    def __init__(self) -> None:
        self.mod_name = None
        self.zero_files = None
        self.github_files = None
        self.installers = None
        self.remaining_archives = None
        self.unknown_files = None
        self.unknown_files_by_tools = None
        self.mod_tools = None
        self.patches = None

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "ProjectMod":
        out = cls()
        out.mod_name = ''
        out.zero_files = []
        out.github_files = {}
        out.installers = []
        out.remaining_archives = []
        out.unknown_files = []
        out.unknown_files_by_tools = []
        out.patches = []
        return out


class ProjectJson:
    SANGUINE_JSON: list[tuple[str, str]] = [('mods', 'mods', ProjectMod)]
    # intermediate_archives: list[bytes] | None
    mods: list[ProjectMod] | None

    def __init__(self) -> None:
        # self.intermediate_archives = None
        self.mods = None
