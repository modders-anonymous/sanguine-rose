from sanguine.common import *
from sanguine.helpers.file_retriever import GithubFileRetriever


class ProjectExtraArchiveFile:
    sanguine_json: list[tuple[str, str]] = [('target_file_name', 't'), ('file_hash', 'h')]
    target_file_name: str
    file_hash: bytes

    def __init__(self, targetfname: str, h: bytes) -> None:
        self.target_file_name = targetfname
        self.file_hash = h


class ProjectExtraArchive:
    sanguine_json: list[tuple[str, str]] = [('archive_id', 'arid'), ('extra_files', 'files')]
    archive_id: bytes | int
    extra_files: list[ProjectExtraArchiveFile]

    def __init__(self, aid: bytes | int) -> None:
        self.archive_id = aid
        self.extra_files = []


class ProjectInstaller:
    sanguine_json: list[tuple[str, str]] = [('archive_hash', 'h'),
                                            ('installer_type', 'type'), ('installer_params', 'params'),
                                            ('skip', 'skip')]
    archive_hash: bytes
    installer_type: str
    installer_params: dict[str, Any]
    skip: list[str]

    def __init__(self, arhash: bytes, insttype: str, instparams: dict[str, Any], skip: list[str]) -> None:
        self.archive_hash = arhash
        self.installer_type = insttype
        self.installer_params = instparams
        self.skip = skip


class ProjectMod:
    sanguine_json: list[tuple[str, str]] = [('mod_name', 'name'), ('zero_files', 'zero'),
                                            ('github_files', 'github'), ('installers', 'installers'),
                                            ('remaining_archives', 'xarchives'),
                                            ('unknown_files_by_tools', 'unknownbytools'),
                                            ('unknown_files', 'unknown')]
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


class ProjectJson:
    sanguine_json: list[tuple[str, str]] = [('mods', 'mods')]
    # intermediate_archives: list[bytes] | None
    mods: list[ProjectMod] | None

    def __init__(self) -> None:
        # self.intermediate_archives = None
        self.mods = None
