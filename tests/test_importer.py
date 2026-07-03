from datetime import date

import pandas as pd

from ape.database.database import DatabaseManager
from ape.database.repositories import DrawRepository
from ape.importers.excel_importer import ExcelDrawImporter


def test_importer_imports_and_upserts(tmp_path):
    excel_file = tmp_path / "history.xlsx"
    pd.DataFrame(
        {
            "STT": [1, 2],
            "Ngày": ["03/01/2024", "05/01/2024"],
            "Thứ": ["Thứ Tư", "Thứ Sáu"],
            "Bộ Số": [
                "12 - 13 - 20 - 27 - 31 - 38",
                "16 - 17 - 23 - 32 - 35 - 41",
            ],
        }
    ).to_excel(excel_file, index=False)

    database = DatabaseManager(tmp_path / "ape.db")
    database.initialize()
    importer = ExcelDrawImporter(database)

    first = importer.import_file(excel_file)
    assert first.inserted_rows == 2
    assert first.invalid_rows == 0

    second = importer.import_file(excel_file)
    assert second.updated_rows == 2
    assert second.inserted_rows == 0

    with database.session() as session:
        repository = DrawRepository(session)
        assert repository.count() == 2
        stored = repository.get_by_date(date(2024, 1, 3))
        assert stored is not None
        assert stored.numbers == [12, 13, 20, 27, 31, 38]

    database.dispose()


def test_duplicate_date_in_same_file_is_reported(tmp_path):
    excel_file = tmp_path / "duplicate.xlsx"
    pd.DataFrame(
        {
            "Ngày": ["03/01/2024", "03/01/2024"],
            "Bộ Số": [
                "01-02-03-04-05-06",
                "07-08-09-10-11-12",
            ],
        }
    ).to_excel(excel_file, index=False)

    report = ExcelDrawImporter(
        DatabaseManager(tmp_path / "ape.db")
    ).validate_file(excel_file)

    assert report.valid_rows == 1
    assert report.invalid_rows == 1
    assert report.duplicate_dates_in_file == 1
