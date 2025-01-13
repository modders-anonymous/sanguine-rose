from sanguine.helpers.tools import ToolPluginBase, ResolvedVFS


class IgnoreMetaToolPlugin(ToolPluginBase):
    def name(self) -> str:
        return 'IgnoreMeta'

    def supported_games(self) -> list[str]:
        return ['SKYRIM']

    def extensions(self) -> list[str]:
        return ['.ini']

    def create_context(self, resolvedvfs: ResolvedVFS) -> any:
        return None

    def could_be_produced(self, ctx: any, srcpath: str, targetpath: str) -> bool:
        assert ctx is None
        if targetpath == 'data\\meta.ini':
            return True
