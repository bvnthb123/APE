"""
Application bootstrap.
"""
from ape.core.settings import SETTINGS
from ape.core.version import APP_NAME, APP_CODE, VERSION, BUILD_NAME
from ape.utils.logger import logger

class APEApplication:
    def __init__(self) -> None:
        self.settings = SETTINGS

    def start(self) -> None:
        logger.info("Starting %s %s - %s", APP_CODE, VERSION, BUILD_NAME)
        logger.info("Root directory: %s", self.settings.root_dir)
        logger.info("Data directory: %s", self.settings.data_dir)
        logger.info("Database file: %s", self.settings.database_file)
        logger.info("Core foundation initialized successfully.")

    def summary(self) -> dict:
        return {
            "app_name": APP_NAME,
            "app_code": APP_CODE,
            "version": VERSION,
            "build": BUILD_NAME,
            "root_dir": str(self.settings.root_dir),
            "database_file": str(self.settings.database_file),
            "number_range": f"{self.settings.min_number}-{self.settings.max_number}",
            "numbers_per_draw": self.settings.numbers_per_draw,
        }
