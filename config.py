"""
Compatibility config file.
"""
from ape.core.settings import SETTINGS
from ape.core.version import APP_NAME, APP_CODE, VERSION

ROOT_DIR = SETTINGS.root_dir
DATA_DIR = SETTINGS.data_dir
LOGS_DIR = SETTINGS.logs_dir
REPORTS_DIR = SETTINGS.reports_dir
DATABASE_FILE = SETTINGS.database_file
EXCEL_FILE = SETTINGS.default_excel_file
MIN_NUMBER = SETTINGS.min_number
MAX_NUMBER = SETTINGS.max_number
NUMBERS_PER_DRAW = SETTINGS.numbers_per_draw
TOP_N = SETTINGS.top_n
BACKTEST_START = SETTINGS.backtest_start
