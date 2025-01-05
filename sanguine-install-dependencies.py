import os
import sys
import logging

sys.path.append(os.path.split(os.path.abspath(__file__))[0])

from sanguine.install.install_helpers import install_sanguine_prerequisites, confirm_box
from sanguine.install.install_logging import info

install_sanguine_prerequisites()

info('Dependencies installed successfully, you are ready to run sanguine-rose')
confirm_box('Press any key to exit {}'.format(sys.argv[0]),level=logging.INFO)