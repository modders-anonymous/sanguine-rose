import re
import xml.etree.ElementTree as ElementTree

from sanguine.common import *
from sanguine.helpers.project_config import LocalProjectConfig
from sanguine.helpers.globaltools import GlobalToolPluginBase, ResolvedVFS, CouldBeProducedByGlobalTool


class _BodySlideToolPluginContext:
    rel_output_files: dict[str, int]
    target_files: set[str]

    def __init__(self) -> None:
        self.rel_output_files = {}
        self.target_files = set()


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


class BodySlideGlobalToolPlugin(GlobalToolPluginBase):
    def name(self) -> str:
        return 'BodySlide'

    def supported_games(self) -> list[str]:
        return ['SKYRIM']

    def extensions(self) -> list[str]:
        return ['.tri', '.nif']

    def create_context(self, cfg: LocalProjectConfig, resolvedvfs: ResolvedVFS) -> Any:
        ctx: _BodySlideToolPluginContext = _BodySlideToolPluginContext()
        osppattern = re.compile(r'data\\CalienteTools\\Bodyslide\\SliderSets\\.*\.osp$', re.IGNORECASE)
        for relpath in resolvedvfs.all_target_files():
            assert relpath not in ctx.target_files
            ext = os.path.splitext(relpath)[1]
            if ext in ['.tri', '.nif']:
                ctx.target_files.add(relpath)
            if osppattern.match(relpath):
                srcfiles = resolvedvfs.files_for_target(relpath)
                assert len(srcfiles) > 0
                modified = _parse_osp(srcfiles[-1].file_path)
                ctx.rel_output_files |= {m: 1 for m in modified}
        return ctx

    def could_be_produced(self, ctx: Any, srcpath: str, targetpath: str) -> CouldBeProducedByGlobalTool:
        assert isinstance(ctx, _BodySlideToolPluginContext)
        f, ext = os.path.splitext(targetpath)
        assert ext in self.extensions()
        if ext == '.tri':
            if f in ctx.rel_output_files:
                return CouldBeProducedByGlobalTool.WithCurrentConfig
            f0 = f + '_0.nif'
            f1 = f + '_1.nif'
            if f0 in ctx.target_files and f1 in ctx.target_files:
                return CouldBeProducedByGlobalTool.Maybe

            fnif = f + '.nif'
            if fnif in ctx.target_files:
                return CouldBeProducedByGlobalTool.Maybe
            return CouldBeProducedByGlobalTool.NotFound

        assert ext == '.nif'
        if f.endswith('_0') or f.endswith('_1'):
            if f[:-2] in ctx.rel_output_files:
                return CouldBeProducedByGlobalTool.WithCurrentConfig
            f0 = f[:-2] + '_0.nif'
            f1 = f[:-2] + '_1.nif'
            ftri = f[:-2] + '.tri'
            if f0 in ctx.target_files and f1 in ctx.target_files and ftri in ctx.target_files:
                return CouldBeProducedByGlobalTool.Maybe
            return CouldBeProducedByGlobalTool.NotFound
        else:
            if f in ctx.rel_output_files:
                return CouldBeProducedByGlobalTool.WithCurrentConfig
            ftri = f + '.tri'
            if ftri in ctx.target_files:
                return CouldBeProducedByGlobalTool.Maybe
            return CouldBeProducedByGlobalTool.NotFound
