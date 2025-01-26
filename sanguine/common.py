import base64
import codecs
import hashlib
import json
import pickle
from bisect import bisect_right
from stat import S_ISREG, S_ISLNK

import chardet

# noinspection PyUnresolvedReferences
from sanguine.install.install_checks import check_sanguine_prerequisites
from sanguine.install.install_common import *


### inter-file interfaces

class FileOnDisk:
    file_hash: bytes
    file_path: str
    file_modified: float
    file_size: int

    def __init__(self, file_hash: bytes, file_modified: float, file_path: str, file_size: int):
        assert file_path is not None
        self.file_hash = file_hash
        self.file_modified = file_modified
        self.file_path = file_path
        self.file_size = file_size


class FolderToCache:
    folder: str
    exdirs: list[str]

    @staticmethod
    def ok_to_construct(folder: str, exdirs: list[str]) -> bool:
        if __debug__:
            assert is_normalized_dir_path(folder)
            for x in exdirs:
                assert is_normalized_dir_path(x)
        for x in exdirs:
            if folder.startswith(x):
                return False
        return True

    def __init__(self, folder: str, exdirs: list[str] = None) -> None:
        assert FolderToCache.ok_to_construct(folder, exdirs)
        self.folder = folder
        self.exdirs = [] if exdirs is None else [x for x in exdirs if x.startswith(self.folder)]

    @staticmethod
    def filter_ex_dirs(exdirs: list[str], path: str) -> list[str]:
        return [x for x in exdirs if x.startswith(path)]

    @staticmethod
    def _is_path_included(path: str, root: str, exdirs: list[str]) -> bool:
        if not path.startswith(root):
            return False
        for x in exdirs:
            if path.startswith(x):
                return False
        return True

    def is_file_path_included(self, fpath: str) -> bool:
        assert is_normalized_file_path(fpath)
        return FolderToCache._is_path_included(fpath, self.folder, self.exdirs)

    @staticmethod
    def static_is_file_path_included(fpath: str, root: str, exdirs: list[str]) -> bool:
        assert is_normalized_file_path(fpath)
        return FolderToCache._is_path_included(fpath, root, exdirs)

    '''
    def is_dir_path_included(self,dpath: str) -> bool:
        assert is_normalized_dir_path(dpath)
        return self._is_path_included(dpath)
    '''


class FolderListToCache:
    folders: list[FolderToCache]

    def __init__(self, folders: list[FolderToCache]) -> None:
        self.folders = folders

    def is_file_path_included(self, fpath: str) -> bool:
        assert is_normalized_file_path(fpath)
        for f in self.folders:
            if f.is_file_path_included(fpath):
                return True
        return False

    def append(self, folder: FolderToCache) -> None:
        self.folders.append(folder)

    def __getitem__(self, item: int) -> FolderToCache:
        return self.folders[item]

    def __len__(self) -> int:
        return len(self.folders)


class ModFile:
    mod: str | None
    intramod: str

    def __init__(self, mod: str | None, intramod: str) -> None:
        self.mod = mod
        self.intramod = intramod

    def __hash__(self) -> int:
        return hash((hash(self.mod), self.intramod))

    def __eq__(self, other) -> bool:
        return self.mod == other.mod and self.intramod == other.intramod


class ResolvedVFS:
    _source_to_target: dict[str, str]  # full path to relpath
    _target_files: dict[str, list[FileOnDisk]]  # relpath to list of files

    def __init__(self, sourcetotarget: dict[str, str], targetfiles: dict[str, list[FileOnDisk]]) -> None:
        self._source_to_target = sourcetotarget
        self._target_files = targetfiles

    def all_source_files(self) -> Iterable[str]:
        return self._source_to_target.keys()

    def all_target_files(self) -> Iterable[str]:
        return self._target_files.keys()

    def source_to_target(self, path: str) -> str:
        return self._source_to_target[path]

    def files_for_target(self, relpath: str) -> list[FileOnDisk]:
        return self._target_files[relpath]


### Hashing

class ExtraHash(ABC):
    @abstractmethod
    def update(self, data: bytes) -> None:
        pass

    @abstractmethod
    def digest(self) -> bytes:
        pass


type ExtraHashFactory = Callable[[], ExtraHash]


def calculate_file_hash_ex(fpath: str, extrahashfactories: list[ExtraHashFactory]) -> tuple[int, bytes, list[bytes]]:
    """
    As our native hash, we are using SHA-256, the fastest crypto-hash because of hardware instruction.
    Other hashes may be requested by fileorigin plugins.
    """
    st = os.lstat(fpath)
    assert S_ISREG(st.st_mode) and not S_ISLNK(st.st_mode)
    h = hashlib.sha256()
    xh = [xf() for xf in extrahashfactories]
    blocksize = 1048576
    fsize = 0
    with open(fpath, 'rb') as f:
        while True:
            bb = f.read(blocksize)
            if not bb:
                break
            h.update(bb)
            for x in xh:
                x.update(bb)
            lbb = len(bb)
            assert lbb <= blocksize
            fsize += lbb

    # were there any changes while we were working?
    assert st.st_size == fsize
    st2 = os.lstat(fpath)
    assert st2.st_size == st.st_size
    assert st2.st_mtime == st.st_mtime
    return fsize, h.digest(), [x.digest() for x in xh]


def calculate_file_hash(fpath: str) -> tuple[int, bytes]:
    """
    As our native hash, we are using SHA-256, the fastest crypto-hash because of hardware instruction.
    """
    (fsize, h, x) = calculate_file_hash_ex(fpath, [])
    assert len(x) == 0
    return fsize, h


def truncate_file_hash(h: bytes) -> bytes:
    assert len(h) == 32
    return h[:9]


### generic helpers

class Val:
    val: Any

    def __init__(self, initval: Any) -> None:
        self.val = initval

    def __str__(self) -> str:
        return str(self.val)


def add_to_dict_of_lists(dicttolook: dict[Any, list[Any]], key: Any, val: Any) -> None:
    if key not in dicttolook:
        dicttolook[key] = [val]
    else:
        dicttolook[key].append(val)


class FastSearchOverPartialStrings:
    _strings: list[tuple[str, int, Any]]

    def __init__(self, src: list[tuple[str, Any]]) -> None:
        self._strings = []
        for s in src:
            assert isinstance(s, tuple)
            self._strings.append((s[0], -1, s[1]))
        self._strings.sort(key=lambda x2: x2[0])

        # filling previdx
        prevrefs: list[int] = []
        for i in range(len(self._strings)):
            (p, _, val) = self._strings[i]
            if len(prevrefs) == 0:
                self._strings[i] = (p, -1, val)
                prevrefs.append(i)
            elif p.startswith(self._strings[prevrefs[-1]][0]):
                self._strings[i] = (p, prevrefs[-1], val)
                prevrefs.append(i)
            else:
                while True:
                    if p.startswith(self._strings[prevrefs[-1]][0]):
                        self._strings[i] = (p, prevrefs[-1], val)
                        prevrefs.append(i)
                        break
                    prevrefs = prevrefs[:-1]
                    if len(prevrefs) == 0:
                        self._strings[i] = (p, -1, val)
                        prevrefs.append(i)
                        break

    def find_val_for_str(self, s: str) -> tuple[str, Any] | None:
        # k = (s, -1, None)
        idx = bisect_right(self._strings, s, key=lambda x2: x2[0])
        if idx == 0:
            return None
        prev = self._strings[idx - 1]
        if s.startswith(prev[0]):
            return prev[0], prev[2]

        while True:
            if prev[1] < 0:
                return None
            prev = self._strings[prev[1]]
            if s.startswith(prev[0]):
                return prev[0], prev[2]


def unused_config_warning(where: str, cfg: ConfigData, known: list[str]) -> None:
    known2 = {key: 1 for key in known}
    errstr = ''
    for k in cfg.keys():
        if k not in known2:
            if errstr != '':
                errstr += ','
            errstr += k
    if errstr != '':
        alert('Unused config keys in {}: {}'.format(where, errstr))


### JSON-related

def open_git_data_file_for_writing(fpath: str) -> typing.TextIO:
    return open(fpath, 'wt', encoding='utf-8', newline='\n')


def open_git_data_file_for_reading(fpath: str) -> typing.TextIO:
    return open(fpath, 'rt', encoding='utf-8')


def open_3rdparty_txt_file_autodetect(fname: str) -> typing.TextIO:
    n = min(32, os.path.getsize(fname))
    with open(fname, 'rb') as fb:
        raw = fb.read(n)

    if raw.startswith(codecs.BOM_UTF8):
        enc = 'utf-8-sig'
    else:
        enc = chardet.detect(raw)['encoding']
    return open(fname, 'rt', encoding=enc, errors='replace')


def to_json_hash(h: bytes) -> str:
    b64 = base64.b64encode(h).decode('ascii')
    # print(b64)
    s = b64.rstrip('=')
    # assert from_json_hash(s) == h
    return s


def from_json_hash(s: str) -> bytes:
    ntopad = (3 - (len(s) % 3)) % 3
    s += '=='[:ntopad]
    b = base64.b64decode(s)
    return b


class SanguineJsonEncoder(json.JSONEncoder):
    def encode(self, o: Any) -> Any:
        return json.JSONEncoder.encode(self, self.default(o))

    def default(self, o: Any) -> Any:
        if isinstance(o, bytes):
            return base64.b64encode(o).decode('ascii')
        elif isinstance(o, Callable):
            return o.__name__
        elif isinstance(o, dict):
            return self._adjust_dict(o)
        elif o is None or isinstance(o, str) or isinstance(o, tuple) or isinstance(o, list):
            return o
        elif isinstance(o, object):
            return o.__dict__
        else:
            return o

    def _adjust_dict(self, d: dict[Any, Any]) -> dict[Any, Any]:
        out = {}
        for k, v in d.items():
            if isinstance(k, bytes):
                k = base64.b64encode(k).decode('ascii')
            out[k] = self.default(v)
        return out


def as_json(data: Any) -> str:
    return SanguineJsonEncoder().encode(data)


### file-related helpers

def read_dict_from_pickled_file(fpath: str) -> dict[Any, Any]:
    try:
        with open(fpath, 'rb') as rfile:
            return pickle.load(rfile)
    except Exception as e:
        warn('error loading ' + fpath + ': ' + str(e) + '. Will continue without it')
        return {}


##### esx stuff

def is_esl_flagged(filename: str) -> bool:
    with open(filename, 'rb') as f:
        buf = f.read(10)
        return (buf[0x9] & 0x02) == 0x02


def is_esx(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext == '.esl' or ext == '.esp' or ext == '.esm'
