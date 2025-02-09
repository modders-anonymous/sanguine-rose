from sanguine.common import *
from sanguine.gitdata.stable_json import StableJsonFlags
from sanguine.helpers.patches import PatchPluginBase


class _SortedJsonPluginPatchPath:
    SANGUINE_JSON: list[tuple] = [('path', None, str, StableJsonFlags.Unsorted)]
    path: list[str]

    def __init__(self, path: list[str]):
        self.path = path

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "_SortedJsonPluginPatchPath":
        return cls([])


class _SortedJsonPluginStringOverwrite:
    SANGUINE_JSON: list[tuple[str, str]] = [('path', 'path'), ('value', 's')]
    path: _SortedJsonPluginPatchPath
    value: str

    def __init__(self, path: list[str], val: str):
        self.path = _SortedJsonPluginPatchPath(path)
        self.value = val

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "_SortedJsonPluginStringOverwrite":
        return cls([], '')


class _SortedJsonPluginNumberOverwrite:
    SANGUINE_JSON: list[tuple[str, str]] = [('path', 'path'), ('value', 'n')]
    path: _SortedJsonPluginPatchPath
    value: float

    def __init__(self, path: list[str], val: float):
        self.path = _SortedJsonPluginPatchPath(path)
        self.value = val

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "_SortedJsonPluginNumberOverwrite":
        return cls([], 0.)

    def sanguine_stable_json_sort_key(self) -> str:
        return '|'.join(self.path.path)


class _SortedJsonPluginPatch:
    SANGUINE_JSON: list[tuple[str, str]] = [('string_overwrites', 'str', _SortedJsonPluginStringOverwrite),
                                            ('number_overwrites', 'float', _SortedJsonPluginNumberOverwrite)
                                            ]
    string_overwrites: list[_SortedJsonPluginStringOverwrite]
    number_overwrites: list[_SortedJsonPluginNumberOverwrite]

    def __init__(self):
        self.string_overwrites = []
        self.number_overwrites = []

    def add_string_overwrite(self, path: list[str], value: str) -> None:
        self.string_overwrites.append(_SortedJsonPluginStringOverwrite(path, value))

    def add_number_overwrite(self, path: list[str], value: float) -> None:
        self.number_overwrites.append(_SortedJsonPluginNumberOverwrite(path, value))


class SortedJsonPatchPlugin(PatchPluginBase):
    def name(self) -> str:
        return 'SORTEDJSON'

    def extensions(self) -> list[str]:
        return ['.json']

    def patch(self, srcfile: str, dstfile: str) -> Any:
        with open_3rdparty_txt_file_autodetect(srcfile) as fp:
            srcjson = json.load(fp)
        with open_3rdparty_txt_file_autodetect(dstfile) as fp:
            dstjson = json.load(fp)
        out = _SortedJsonPluginPatch()
        nmatch = Val(0)
        SortedJsonPatchPlugin._patch_json_object(nmatch, out, [], srcjson, dstjson)
        if nmatch.val == 0:
            return None
        return out

    @staticmethod
    def _patch_json_object(nmatch: Val, out: _SortedJsonPluginPatch, path: list[str], src: Any, dst: Any) -> None:
        if isinstance(src, str):
            raise_if_not(isinstance(dst, str))
            if dst == src:
                nmatch.val += 1
                pass
            out.add_string_overwrite(path, dst)
        elif isinstance(src, (int, float)):
            raise_if_not(isinstance(dst, (int, float)))
            if dst == src:
                nmatch.val += 1
                pass
            out.add_number_overwrite(path, dst)
        elif isinstance(src, dict):
            raise_if_not(isinstance(dst, dict))
            SortedJsonPatchPlugin._patch_json_dict(nmatch, out, path, src, dst)
        else:
            raise_if_not(False)

    @staticmethod
    def _patch_json_dict(nmatch: Val, out: _SortedJsonPluginPatch, path: list[str], src: dict, dst: dict) -> None:
        assert isinstance(src, dict)
        assert isinstance(dst, dict)
        for key, value in dst.items():
            assert isinstance(key, str)
            if key in src:
                path1 = path + [key]
                SortedJsonPatchPlugin._patch_json_object(nmatch, out, path1, src[key], dst[key])
