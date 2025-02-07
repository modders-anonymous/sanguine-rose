import re

from sanguine.common import *
from sanguine.helpers.modtools import ModToolPluginBase, ModToolGuessParam, ModToolGuessDiff

class OptionalModToolData:
    SANGUINE_JSON: list[tuple[str, str]] = [('moved','mv',str)]
    moved: list[str]


class OptionalModToolPlugin(ModToolPluginBase):
    def name(self) -> str:
        return 'OPTIONAL'

    def supported_games(self) -> list[str]:
        return ['SKYRIM']

    def guess_applied(self,param:ModToolGuessParam) -> None | tuple[Any,ModToolGuessDiff]:
        pattern = re.compile(r'optional\\([ 0-9a-z_-]*\.es[plm])')
        mv: list[tuple[str,str]] = []
        data: list[str] = []
        for f,retr in param.remaining_after_install_from.items():
            fh = truncate_file_hash(retr[0].file_hash)
            m = pattern.match(f)
            if m:
                fname = m.group(1)
                lmv = len(mv)
                for ar in param.install_from:
                    if fname in ar[1].skip:
                        for ff,fia in ar[0].all_desired_files():
                            if ff == fname:
                                assert len(fia.file_hash) == len(fh)
                                if fia.file_hash == fh:
                                    mv.append((fname,'optional\\'+fname))
                                    data.append(fname)
                                break
                assert len(mv) - lmv <= 1
                assert len(data) == len(mv)

        if len(mv) == 0:
            return None
        out = ModToolGuessDiff()
        out.moved = mv
        data2 = OptionalModToolData()
        data2.moved = data
        return data2,out

