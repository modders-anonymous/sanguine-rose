from sanguine.common import *
from sanguine.gitdata.git_data_file import open_git_data_file_for_writing
from sanguine.helpers.file_retriever import GithubFileRetriever


def _stable_json_sort_list(data: list[Any]) -> list[Any]:
    if len(data) == 0:
        return []
    d0 = data[0]
    if isinstance(d0, str):
        if __debug__:
            for i in data:
                assert isinstance(i, str)
        return sorted(data)

    assert hasattr(d0, 'sanguine_json')
    if __debug__:
        for i in data:
            assert d0.sanguine_json == i.sanguine_json
    firstfield = d0.sanguine_json[0][1]
    data2 = [to_stable_json(d) for d in data]
    return sorted(data2, key=lambda x: x[firstfield])


def to_stable_json(data: Any) -> dict[str, Any] | list[Any] | str:
    if hasattr(data, 'sanguine_json'):
        out: dict[str, Any] = {}
        di = data.__dict__
        for field, jfield in data.sanguine_json:
            v = to_stable_json(di[field])
            if isinstance(v, list) and len(v) == 0:
                pass
            elif isinstance(v, dict) and len(v) == 0:
                pass
            else:
                out[jfield] = v
        return out
    if isinstance(data, list):
        return _stable_json_sort_list(data)
    if isinstance(data, dict):
        if __debug__:
            for k in data:
                assert isinstance(k, str)
        return {k: to_stable_json(v) for k, v in sorted(data.items(), key=lambda x: x[0])}
    if isinstance(data, str):
        return data
    if isinstance(data, bytes):
        return to_json_hash(data)
    assert False


def write_stable_json(fname: str, data: dict[str, Any]) -> None:
    with open_git_data_file_for_writing(fname) as f:
        # noinspection PyTypeChecker
        json.dump(data, f, indent=1)


class ProjectArchive:
    sanguine_json: list[tuple[str, str]] = [('archive_hash', 'h'), ('skip', 'skip')]
    archive_hash: bytes | None
    skip: list[str] | None

    def __init__(self) -> None:
        self.archive_hash = None
        self.skip = None


class ProjectMod:
    sanguine_json: list[tuple[str, str]] = [('mod_name', 'name'), ('zero_files', 'zero'),
                                            ('github_files', 'github'), ('archives', 'archives'),
                                            ('unknown_files', 'unknown')]
    mod_name: str | None
    zero_files: list[str] | None
    github_files: dict[str, GithubFileRetriever] | None
    archives: list[ProjectArchive] | None
    unknown_files: list[str] | None

    def __init__(self) -> None:
        self.mod_name = None
        self.zero_files = None
        self.github_files = None
        self.archives = None
        self.unknown_files = None


class ProjectJson:
    sanguine_json: list[tuple[str, str]] = [('mods', 'mods')]
    # intermediate_archives: list[bytes] | None
    mods: list[ProjectMod] | None

    def __init__(self) -> None:
        # self.intermediate_archives = None
        self.mods = None
