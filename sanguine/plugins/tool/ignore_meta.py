from sanguine.common import *
from sanguine.helpers.project_config import LocalProjectConfig
from sanguine.helpers.tools import ToolPluginBase, ResolvedVFS, CouldBeProducedByTool


class IgnoreMetaToolPlugin(ToolPluginBase):
    def name(self) -> str:
        return 'IgnoreMeta'

    def supported_games(self) -> list[str]:
        return ['SKYRIM']

    def extensions(self) -> list[str]:
        return ['.ini']

    def create_context(self, cfg: LocalProjectConfig, resolvedvfs: ResolvedVFS) -> Any:
        return None

    def could_be_produced(self, ctx: Any, srcpath: str, targetpath: str) -> CouldBeProducedByTool:
        assert ctx is None
        if targetpath == 'data\\meta.ini':
            return CouldBeProducedByTool.JustIgnore
        else:
            return CouldBeProducedByTool.NotFound
