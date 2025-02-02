from sanguine.plugins.arinstaller._fomod.fomod_common import *


class FomodEngine:
    module_config: FomodModuleConfig

    def __init__(self, modulecfg: FomodModuleConfig) -> None:
        self.module_config = modulecfg

    def run(self, ui: LinearUI) -> FomodFilesAndFolders:
        files = self.module_config.required.copy()  # copying just in case
        for istep in self.module_config.install_steps:
            wizpage = LinearUIGroup(istep.name,[])
            for grp in istep.groups:
                wizpagegrp = LinearUIGroup(grp.name,[])
                wizpage.add_control(wizpagegrp)
                for plugin in grp.plugins:
                    match grp.select:
                        case FomodGroupSelect.SelectAny, FomodGroupSelect.SelectAtMostOne, FomodGroupSelect.SelectAtLeastOne:
                            wizpageplugin = LinearUICheckbox(plugin.name,False, False)
                        case FomodGroupSelect.SelectExactlyOne:
                            wizpageplugin = LinearUICheckbox(plugin.name, False, True)
                        case FomodGroupSelect.SelectAll:
                            wizpageplugin = LinearUICheckbox(plugin.name, True, False)
                            wizpageplugin.disabled = True
                        case _:
                            assert False
                    wizpagegrp.add_control(wizpageplugin)
            ui.wizard_page(wizpage)
        return files
