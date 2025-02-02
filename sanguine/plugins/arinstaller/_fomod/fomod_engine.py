from sanguine.plugins.arinstaller._fomod.fomod_common import *


def _fomod_wizard_page_validator(wizardpage: LinearUIGroup) -> str | None:
    for ctrl in wizardpage.controls:
        assert isinstance(ctrl, LinearUIGroup)
        tag, istep = ctrl.extra_data
        assert tag == 0
        for c2 in ctrl.controls:
            assert isinstance(c2, LinearUIGroup)
            tag, grp = c2.extra_data
            assert tag == 1
            assert isinstance(grp, FomodGroup)
            sel = grp.select
            nsel = 0
            for c3 in c2.controls:
                tag, plugin = c3.extra_data
                assert tag == 2
                assert isinstance(plugin, FomodPlugin)
                assert isinstance(c3, LinearUICheckbox)
                if c3.value:
                    nsel += 1

            assert nsel >= 0
            match sel:
                case FomodGroupSelect.SelectAll:
                    assert nsel == len(c2.controls)
                case FomodGroupSelect.SelectAny:
                    pass
                case FomodGroupSelect.SelectExactlyOne:
                    assert nsel == 1
                case FomodGroupSelect.SelectAtMostOne:
                    if nsel > 1:
                        return 'Too many selections in group {}'.format(c2.name)
                case FomodGroupSelect.SelectAtLeastOne:
                    if nsel < 1:
                        return 'Too few selections in group {}'.format(c2.name)
    return None


class FomodEngine:
    module_config: FomodModuleConfig

    def __init__(self, modulecfg: FomodModuleConfig) -> None:
        self.module_config = modulecfg

    def run(self, ui: LinearUI) -> FomodFilesAndFolders:
        files = self.module_config.required.copy()  # copying just in case
        for istep in self.module_config.install_steps:
            wizpage = LinearUIGroup(istep.name, [])
            wizpage.extra_data = (0, istep)
            for grp in istep.groups:
                wizpagegrp = LinearUIGroup(grp.name, [])
                wizpagegrp.extra_data = (1, grp)
                wizpage.add_control(wizpagegrp)
                for plugin in grp.plugins:
                    match grp.select:
                        case (FomodGroupSelect.SelectAny, FomodGroupSelect.SelectAtMostOne,
                              FomodGroupSelect.SelectAtLeastOne):
                            wizpageplugin = LinearUICheckbox(plugin.name, False, False)
                        case FomodGroupSelect.SelectExactlyOne:
                            wizpageplugin = LinearUICheckbox(plugin.name, False, True)
                        case FomodGroupSelect.SelectAll:
                            wizpageplugin = LinearUICheckbox(plugin.name, True, False)
                            wizpageplugin.disabled = True
                        case _:
                            assert False
                    wizpageplugin.extra_data = (2, plugin)
                    wizpagegrp.add_control(wizpageplugin)
            ui.wizard_page(wizpage, _fomod_wizard_page_validator)
        return files
