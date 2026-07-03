"""Application bootstrap and core service initialization."""

from ape.core.settings import SETTINGS
from ape.core.version import APP_CODE, APP_NAME, BUILD_NAME, VERSION
from ape.database.database import DATABASE, DatabaseManager
from ape.utils.logger import logger


class APEApplication:
    """Bootstrap the APE core services."""

    def __init__(self, database: DatabaseManager | None = None) -> None:
        self.settings = SETTINGS
        self.database = database or DATABASE

    def start(self) -> None:
        """Initialize required services and verify their health."""
        logger.info("Starting %s %s - %s", APP_CODE, VERSION, BUILD_NAME)
        logger.info("Root directory: %s", self.settings.root_dir)
        logger.info("Data directory: %s", self.settings.data_dir)
        logger.info("Database file: %s", self.settings.database_file)

        self.database.initialize()
        if not self.database.health_check():
            raise RuntimeError("Database health check failed.")

        logger.info(
            "Database layer initialized with %s tables.",
            len(self.database.table_names()),
        )

    def summary(self) -> dict[str, object]:
        """Return application and database status information."""
        table_names = self.database.table_names() if self.database.health_check() else []
        return {
            "app_name": APP_NAME,
            "app_code": APP_CODE,
            "version": VERSION,
            "build": BUILD_NAME,
            "root_dir": str(self.settings.root_dir),
            "database_file": str(self.settings.database_file),
            "database_healthy": self.database.health_check(),
            "database_tables": table_names,
            "number_range": f"{self.settings.min_number}-{self.settings.max_number}",
            "numbers_per_draw": self.settings.numbers_per_draw,
        }
