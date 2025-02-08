import re

from sanguine.common import *
from sanguine.helpers.modtools import ModToolPluginBase, ModToolGuessParam, ModToolGuessDiff


class Script2SourceModToolData:
    SANGUINE_JSON: list[tuple[str, str]] = [('script2source', 'script2source'), ]
    script2source: bool


class Script2SourceModToolPlugin(ModToolPluginBase):
    def name(self) -> str:
        return 'SCRIPT2SOURCE'

    def supported_games(self) -> list[str]:
        return ['SKYRIM']

    def guess_applied(self, param: ModToolGuessParam) -> None | tuple[Any, ModToolGuessDiff]:
        g = Script2SourceModToolPlugin._guess_s2s_forward(param)
        return g

    # yes, s2s tool renames whole folder, so it is "all or nothing" tool
    @staticmethod
    def _guess_s2s_forward(param: ModToolGuessParam) -> None | tuple[Any, ModToolGuessDiff]:
        pattern = re.compile(r'source\\scripts\\([ 0-9a-z_-]*\.psc)')
        pattern2 = re.compile(r'scripts\\source\\([ 0-9a-z_-]*\.psc)')
        mv: list[tuple[str, str]] = []
        n2 = None
        for f, retr in param.remaining_after_install_from.items():
            fh = truncate_file_hash(retr[0].file_hash)
            m = pattern.match(f)
            if m:
                fname = m.group(1)
                lmv = len(mv)
                for ar in param.install_from:
                    if 'scripts\\source\\' + fname in ar[1].skip:
                        n2a = 0
                        for ff, fia in ar[0].all_desired_files():
                            if ff == 'scripts\\source\\' + fname:
                                assert len(fia.file_hash) == len(fh)
                                if fia.file_hash == fh:
                                    mv.append(('scripts\\source\\' + fname, 'source\\scripts\\' + fname))
                                else:
                                    return None  # all or nothing
                            if pattern2.match(ff):
                                n2a += 1

                        if n2 is None:
                            n2 = n2a
                        else:
                            assert n2 == n2a
                    else:
                        return None  # all or nothing
                assert len(mv) - lmv <= 1

        if len(mv) == 0:
            return None
        if n2 != len(mv):
            return None  # all or nothing
        out = ModToolGuessDiff()
        out.moved = mv
        data = Script2SourceModToolData()
        data.script2source = True
        return data, out
