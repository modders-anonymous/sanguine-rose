import os
import sys
import traceback

from sanguine.install.install_common import LinearUIImportance

sys.path.append(os.path.split(os.path.abspath(__file__))[0])

from sanguine.install.install_helpers import install_sanguine_prerequisites
from sanguine.install.install_ui import InstallUI
from sanguine.install.install_logging import info, critical, alert, add_file_logging

__version__ = '0.1.1'

ui = InstallUI()
try:
    add_file_logging(os.path.splitext(sys.argv[0])[0] + '.log.html')

    info('sanguine-install-dependencies.py version {}...'.format(__version__))

    for arg in sys.argv[1:]:
        if arg.lower() == '/silent':
            ui.set_silent_mode()
            info('Silent mode enabled')

    install_sanguine_prerequisites(ui)

    info('Dependencies installed successfully, you are ready to run sanguine-rose')
    ui.confirm_box('Press any key to exit {}'.format(sys.argv[0]))
except Exception as e:
    critical('Exception: {}'.format(e))
    alert(traceback.format_exc())
    ui.confirm_box('Press any key to exit {}'.format(sys.argv[0]), level=LinearUIImportance.VeryImportant)
