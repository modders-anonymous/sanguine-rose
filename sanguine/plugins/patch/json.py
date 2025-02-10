from sanguine.common import *
from sanguine.gitdata.stable_json import StableJsonFlags
from sanguine.helpers.patches import PatchPluginBase


class _JsonPluginPatchPath:
    SANGUINE_JSON: list[tuple] = [('path', None, str, StableJsonFlags.Unsorted)]
    path: list[str]

    def __init__(self, path: list[str]):
        self.path = path

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "_JsonPluginPatchPath":
        return cls([])


class _JsonPluginStringOverwrite:
    SANGUINE_JSON: list[tuple[str, str]] = [('path', 'path'), ('value', 's')]
    path: _JsonPluginPatchPath
    value: str

    def __init__(self, path: list[str], val: str):
        self.path = _JsonPluginPatchPath(path)
        self.value = val

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "_JsonPluginStringOverwrite":
        return cls([], '')


class _JsonPluginNumberOverwrite:
    SANGUINE_JSON: list[tuple[str, str]] = [('path', 'path'), ('value', 'n')]
    path: _JsonPluginPatchPath
    value: float

    def __init__(self, path: list[str], val: float):
        self.path = _JsonPluginPatchPath(path)
        self.value = val

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "_JsonPluginNumberOverwrite":
        return cls([], 0.)

    def sanguine_stable_json_sort_key(self) -> str:
        return '|'.join(self.path.path)


class _JsonPluginPatch:
    SANGUINE_JSON: list[tuple[str, str]] = [('string_overwrites', 'str', _JsonPluginStringOverwrite),
                                            ('number_overwrites', 'float', _JsonPluginNumberOverwrite),
                                            ('deletes', 'del', _JsonPluginPatchPath),
                                            ]
    string_overwrites: list[_JsonPluginStringOverwrite]
    number_overwrites: list[_JsonPluginNumberOverwrite]
    deletes: list[_JsonPluginPatchPath]

    def __init__(self):
        self.string_overwrites = []
        self.number_overwrites = []
        self.deletes = []

    def add_string_overwrite(self, path: list[str], value: str) -> None:
        self.string_overwrites.append(_JsonPluginStringOverwrite(path, value))

    def add_number_overwrite(self, path: list[str], value: float) -> None:
        self.number_overwrites.append(_JsonPluginNumberOverwrite(path, value))

    def add_delete(self, path: list[str]) -> None:
        self.deletes.append(_JsonPluginPatchPath(path))


class JsonPatchPlugin(PatchPluginBase):
    def name(self) -> str:
        return 'SORTEDJSON'

    def extensions(self) -> list[str]:
        return ['.json']

    def patch(self, srcfile: str, dstfile: str) -> Any:
        with open_3rdparty_txt_file_autodetect(srcfile) as fp:
            srcjson = json.load(fp)
        with open_3rdparty_txt_file_autodetect(dstfile) as fp:
            dstjson = json.load(fp)
        out = _JsonPluginPatch()
        nmatch = Val(0)
        JsonPatchPlugin._patch_json_object(nmatch, out, [], srcjson, dstjson)
        if nmatch.val == 0:
            return None
        return out

    @staticmethod
    def _patch_json_object(nmatch: Val, out: _JsonPluginPatch, path: list[str], src: Any, dst: Any) -> None:
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
            JsonPatchPlugin._patch_json_dict(nmatch, out, path, src, dst)
        else:
            raise_if_not(False)

    @staticmethod
    def _patch_json_dict(nmatch: Val, out: _JsonPluginPatch, path: list[str], src: dict, dst: dict) -> None:
        assert isinstance(src, dict)
        assert isinstance(dst, dict)
        for key, value in dst.items():
            assert isinstance(key, str)
            path1 = path + [key]
            if key in src:
                JsonPatchPlugin._patch_json_object(nmatch, out, path1, src[key], dst[key])
            else:
                JsonPatchPlugin._add_json_object(out, path1, dst[key])

        for key in src:
            assert isinstance(key, str)
            if not key in dst:
                path1 = path + [key]
                out.add_delete(path1)

    @staticmethod
    def _add_json_object(out: _JsonPluginPatch, path: list[str], dst: dict) -> None:
        if isinstance(dst, (str, int, float)):
            out.add_string_overwrite(path, dst)
        elif isinstance(dst, dict):
            for key, value in dst.items():
                assert isinstance(key, str)
                path1 = path + [key]
                JsonPatchPlugin._add_json_object(out, path1, value)
        else:
            raise_if_not(False)
