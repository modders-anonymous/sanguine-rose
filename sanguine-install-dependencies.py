import logging
import os
import sys
import traceback

sys.path.append(os.path.split(os.path.abspath(__file__))[0])

from sanguine.install.install_helpers import install_sanguine_prerequisites
from sanguine.install.install_ui import confirm_box, set_silent_mode
from sanguine.install.install_logging import info, critical, alert, add_file_logging

try:
    add_file_logging(os.path.splitext(sys.argv[0])[0] + '.log.html')

    for arg in sys.argv[1:]:
        if arg.lower() == '/silent':
            set_silent_mode()
            info('Silent mode enabled')

    install_sanguine_prerequisites()

    info('Dependencies installed successfully, you are ready to run sanguine-rose')
    confirm_box('Press any key to exit {}'.format(sys.argv[0]), level=logging.INFO)
except Exception as e:
    critical('Exception: {}'.format(e))
    alert(traceback.format_exc())
    confirm_box('Press any key to exit {}'.format(sys.argv[0]), level=logging.ERROR)
