import configparser

from sanguine.common import *
from sanguine.helpers.patches import PatchPluginBase


class _IniPatchPluginOverwrite:
    SANGUINE_JSON: list[tuple[str, str]] = [('section', 'sect'), ('name', 'name'), ('value', 'value')]
    section: str
    name: str
    value: str

    def __init__(self, section: str, name: str, val: str):
        self.section = section
        self.name = name
        self.value = val

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "_IniPatchPluginOverwrite":
        return cls('', '', '')


class _IniPatchPluginDel:
    SANGUINE_JSON: list[tuple[str, str]] = [('section', 'sect'), ('name', 'name')]
    section: str
    name: str

    def __init__(self, section: str, name: str):
        self.section = section
        self.name = name

    @classmethod
    def for_sanguine_stable_json_load(cls) -> "_IniPatchPluginDel":
        return cls('', '')


class _IniPluginPatch:
    SANGUINE_JSON: list[tuple[str, str]] = [('overwrites', 'over', _IniPatchPluginOverwrite),
                                            ('deletes', 'del', _IniPatchPluginDel)]
    overwrites: list[_IniPatchPluginOverwrite]
    deletes: list[_IniPatchPluginDel]

    def __init__(self):
        self.overwrites = []
        self.deletes = []

    def add_overwrite(self, section: str, name: str, value: str) -> None:
        self.overwrites.append(_IniPatchPluginOverwrite(section, name, value))

    def add_delete(self, section: str, name: str) -> None:
        self.deletes.append(_IniPatchPluginDel(section, name))


class IniPatchPlugin(PatchPluginBase):
    def name(self) -> str:
        return 'INI'

    def extensions(self) -> list[str]:
        return ['.ini']

    def patch(self, srcfile: str, dstfile: str) -> Any:
        srcini = configparser.ConfigParser(allow_unnamed_section=True)
        srcini.optionxform = str  # making key names case-sensitive
        with open_3rdparty_txt_file_autodetect(srcfile) as fp:
            srcini.read_file(fp)
        dstini = configparser.ConfigParser(allow_unnamed_section=True)
        dstini.optionxform = str  # making key names case-sensitive
        with open_3rdparty_txt_file_autodetect(dstfile) as fp:
            dstini.read_file(fp)

        nmatch = 0
        out = _IniPluginPatch()
        for section in dstini.sections():
            for name, value in dstini[section].items():
                assert isinstance(name, str)
                assert isinstance(value, str)
                override = True
                if section in srcini.sections():
                    if name in srcini[section]:
                        if srcini[section][name] == value:
                            override = False
                            nmatch += 1
                if override:
                    sec = '__@#$SANGUINE_UNNAMED_SECTION$#@__' if section == configparser.UNNAMED_SECTION else section
                    out.add_overwrite(sec, name, value)

        for section in srcini.sections():
            for name, value in srcini[section].items():
                assert isinstance(name, str)
                assert isinstance(value, str)
                if section not in dstini.sections() or name not in dstini[section]:
                    out.add_delete(section, name)

        if nmatch == 0:
            return None
        return out
