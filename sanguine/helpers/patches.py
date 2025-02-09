from sanguine.common import *
from sanguine.helpers.plugin_handler import load_plugins


class PatchPluginBase(ABC):
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def extensions(self) -> list[str]:
        pass

    @abstractmethod
    def patch(self, srcfile: str, dstfile: str) -> Any:
        pass


_patch_plugins: dict[str, PatchPluginBase] = {}  # file_extension -> PatchPluginBase
_patch_plugins_per_ext: dict[str, list[PatchPluginBase]] = {}


def _found_patch_plugin(plugin: PatchPluginBase) -> None:
    global _patch_plugins
    global _patch_plugins_per_ext
    _patch_plugins[plugin.name()] = plugin
    for ext in plugin.extensions():
        if ext not in _patch_plugins_per_ext:
            _patch_plugins_per_ext[ext] = []
        _patch_plugins_per_ext[ext].append(plugin)


load_plugins('plugins/patch/', PatchPluginBase, lambda plugin: _found_patch_plugin(plugin))


def patch_plugins_for(path: str) -> list[PatchPluginBase] | None:
    global _patch_plugins_per_ext
    ext = os.path.splitext(path)[1].lower()
    return _patch_plugins_per_ext.get(ext)
