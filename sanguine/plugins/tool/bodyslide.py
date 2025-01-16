import re
import xml.etree.ElementTree as ElementTree

from sanguine.common import *
from sanguine.helpers.project_config import LocalProjectConfig
from sanguine.helpers.tools import ToolPluginBase, ResolvedVFS, CouldBeProducedByTool


class _BodySlideToolPluginContext:
    rel_output_files: dict[str, int]

    def __init__(self) -> None:
        self.rel_output_files = {}


def _parse_osp(fname: str) -> list[str]:
    try:
        tree = ElementTree.parse(fname)
        root = tree.getroot()
        if root.tag.lower() != 'slidersetinfo':
            warn('Unexpected root tag {} in {}'.format(root.tag, fname))
            return []
        out: list[str] = []
        for ch in root:
            if ch.tag.lower() == 'sliderset':
                slidersetname = ch.attrib.get('name', '?')
                outputfile = None
                outputpath = None
                for ch2 in ch:
                    if ch2.tag.lower() == 'outputfile':
                        if outputfile is not None:
                            warn('Duplicate <OutputFile> tag for {} in {}'.format(slidersetname, fname))
                        else:
                            outputfile = ch2.text.strip()
                    elif ch2.tag.lower() == 'outputpath':
                        if outputpath is not None:
                            warn('Duplicate <OutputPath> tag for {} in {}'.format(slidersetname, fname))
                        else:
                            outputpath = ch2.text.strip()

                if outputfile is None or outputpath is None:
                    warn('Missing <OutputFile> or <OutputPath> tag for {} in {}'.format(slidersetname, fname))
                else:
                    path = 'data\\' + outputpath + '\\' + outputfile
                    out.append(path.lower())
        return out
    except Exception as e:
        warn('Error parsing {}: {}={}'.format(fname, type(e), e))
        return []


class BodySlideToolPlugin(ToolPluginBase):
    def name(self) -> str:
        return 'BodySlide'

    def supported_games(self) -> list[str]:
        return ['SKYRIM']

    def extensions(self) -> list[str]:
        return ['.tri', '.nif']

    def create_context(self, cfg: LocalProjectConfig, resolvedvfs: ResolvedVFS) -> Any:
        ctx: _BodySlideToolPluginContext = _BodySlideToolPluginContext()
        osppattern = re.compile(r'data\\CalienteTools\\Bodyslide\\SliderSets\\.*\.osp$', re.IGNORECASE)
        for mf in resolvedvfs.all_target_files():
            relpath = cfg.modfile_to_target_vfs(mf)
            if osppattern.match(relpath):
                srcfiles = resolvedvfs.modfile_to_target_files(mf)
                assert len(srcfiles) > 0
                modified = _parse_osp(srcfiles[-1].file_path)
                ctx.rel_output_files |= {m: 1 for m in modified}
        return ctx

    def could_be_produced(self, ctx: Any, srcpath: str, targetpath: str) -> CouldBeProducedByTool:
        assert isinstance(ctx, _BodySlideToolPluginContext)
        f, ext = os.path.splitext(targetpath)
        assert ext in self.extensions()
        if ext == '.tri':
            return CouldBeProducedByTool.WithKnownConfig if f in ctx.rel_output_files else CouldBeProducedByTool.NotFound
        assert ext == '.nif'
        if f.endswith('_0') or f.endswith('_1'):
            return CouldBeProducedByTool.WithKnownConfig if f[
                                                            :-2] in ctx.rel_output_files else CouldBeProducedByTool.NotFound
        else:
            return CouldBeProducedByTool.NotFound
