from sanguine.common import *
from sanguine.gitdata.stable_json import StableJsonFlags
from sanguine.helpers.file_retriever import GithubFileRetriever


class ProjectExtraArchiveFile:
    SANGUINE_JSON: list[tuple] = [('target_file_name', 't'), ('file_hash', 'h')]
    target_file_name: str
    file_hash: bytes

    def __init__(self, targetfname: str, h: bytes) -> None:
        self.target_file_name = targetfname
        self.file_hash = h

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "ProjectExtraArchiveFile":
        return cls('', b'')


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


class ProjectMod:
    SANGUINE_JSON: list[tuple[str, str]] = [('mod_name', 'name'),
                                            ('zero_files', 'zero', str),
                                            ('github_files', 'github', (str, GithubFileRetriever)),
                                            ('installers', 'installers', ProjectInstaller, StableJsonFlags.Unsorted),
                                            ('remaining_archives', 'xarchives', ProjectExtraArchive),
                                            ('unknown_files_by_tools', 'unknownbytools', str),
                                            ('unknown_files', 'unknown', str)]
    mod_name: str | None
    zero_files: list[str] | None
    github_files: dict[str, GithubFileRetriever] | None
    installers: list[ProjectInstaller] | None
    remaining_archives: list[ProjectExtraArchive] | None
    unknown_files: list[str] | None
    unknown_files_by_tools: list[str] | None

    def __init__(self) -> None:
        self.mod_name = None
        self.zero_files = None
        self.github_files = None
        self.installers = None
        self.remaining_archives = None
        self.unknown_files = None
        self.unknown_files_by_tools = None

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
        return out


class ProjectJson:
    SANGUINE_JSON: list[tuple[str, str]] = [('mods', 'mods', ProjectMod)]
    # intermediate_archives: list[bytes] | None
    mods: list[ProjectMod] | None

    def __init__(self) -> None:
        # self.intermediate_archives = None
        self.mods = None
