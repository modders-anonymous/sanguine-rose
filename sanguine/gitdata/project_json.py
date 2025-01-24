from sanguine.common import *
from sanguine.helpers.file_retriever import GithubFileRetriever, ArchiveFileRetriever


class ProjectArchiveRemaining:
    sanguine_json: list[tuple[str, str]] = [('file_name', 'f'), ('file_hash', 'h'), ('archive_hash', 'arh'),
                                            ('archive_num', 'from')]
    file_name: str
    archive_hash: bytes | None
    archive_num: int | None
    file_hash: bytes

    def __init__(self, fname: str, r: ArchiveFileRetriever, installerarchives: list[bytes]) -> None:
        self.file_name = fname
        self.file_hash = truncate_file_hash(r.file_hash)
        arh = r.archive_hash()
        if arh in installerarchives:
            self.archive_num = installerarchives.index(arh)
            self.archive_hash = None
        else:
            self.archive_hash = arh
            self.archive_num = None


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
                                            ('remaining_archive_files', 'arfiles'),
                                            ('unknown_files', 'unknown')]
    mod_name: str | None
    zero_files: list[str] | None
    github_files: dict[str, GithubFileRetriever] | None
    installers: list[ProjectInstaller] | None
    remaining_archive_files: list[ProjectArchiveRemaining] | None
    unknown_files: list[str] | None

    def __init__(self) -> None:
        self.mod_name = None
        self.zero_files = None
        self.github_files = None
        self.installers = None
        self.remaining_archive_files = None
        self.unknown_files = None


class ProjectJson:
    sanguine_json: list[tuple[str, str]] = [('mods', 'mods')]
    # intermediate_archives: list[bytes] | None
    mods: list[ProjectMod] | None

    def __init__(self) -> None:
        # self.intermediate_archives = None
        self.mods = None
