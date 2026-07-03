"""Desktop GUI for APE using PySide6."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ape.analytics.service import AnalysisService
from ape.core.settings import SETTINGS
from ape.core.version import APP_NAME, BUILD_NAME, VERSION
from ape.database.database import DATABASE, DatabaseManager
from ape.database.models import Draw
from ape.database.repositories import DrawRepository
from ape.importers.excel_importer import ExcelDrawImporter


APP_STYLESHEET = """
QMainWindow, QWidget {
    background: #F4F7FB;
    color: #16324F;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QFrame#HeaderFrame {
    background: #005BAC;
    border-radius: 12px;
}
QLabel#HeaderTitle {
    color: white;
    font-size: 22pt;
    font-weight: 700;
}
QLabel#HeaderSubtitle {
    color: #D9F2FF;
    font-size: 10pt;
}
QFrame#StatCard {
    background: white;
    border: 1px solid #D9E4F0;
    border-radius: 10px;
}
QLabel#StatTitle {
    color: #5E7184;
    font-size: 9pt;
}
QLabel#StatValue {
    color: #005BAC;
    font-size: 18pt;
    font-weight: 700;
}
QPushButton {
    background: #0076D6;
    color: white;
    border: none;
    border-radius: 7px;
    padding: 8px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background: #005BAC;
}
QPushButton#SecondaryButton {
    background: white;
    color: #005BAC;
    border: 1px solid #9DBFDF;
}
QTabWidget::pane {
    border: 1px solid #D9E4F0;
    background: white;
    border-radius: 8px;
}
QTabBar::tab {
    background: #EAF2FA;
    color: #294A68;
    padding: 10px 18px;
    margin-right: 3px;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
}
QTabBar::tab:selected {
    background: #005BAC;
    color: white;
}
QTableWidget {
    background: white;
    alternate-background-color: #F5F9FD;
    border: 1px solid #D9E4F0;
    gridline-color: #E3EBF4;
    selection-background-color: #CCE9FF;
    selection-color: #16324F;
}
QHeaderView::section {
    background: #EAF2FA;
    color: #234967;
    border: none;
    border-right: 1px solid #D9E4F0;
    padding: 7px;
    font-weight: 700;
}
QPlainTextEdit {
    background: white;
    border: 1px solid #D9E4F0;
    border-radius: 7px;
    padding: 8px;
}
QStatusBar {
    background: #EAF2FA;
    color: #294A68;
}
"""


def format_numbers(numbers: Iterable[int]) -> str:
    return " - ".join(f"{int(number):02d}" for number in numbers)


def draw_table_rows(draws: Iterable[Draw]) -> list[tuple[str, ...]]:
    return [
        (
            draw.draw_date.strftime("%d/%m/%Y"),
            draw.weekday_name,
            format_numbers(draw.numbers),
            str(draw.total_sum),
            f"{draw.odd_count}/{draw.even_count}",
            f"{draw.low_count}/{draw.high_count}",
            draw.source_file or "",
        )
        for draw in draws
    ]


def analysis_metric_rows(report) -> list[tuple[str, ...]]:
    return [
        (
            f"{item['event_id']:02d}",
            str(item["count"]),
            f"{item['rate'] * 100:.2f}%",
            str(item["latest_distance"]),
            f"{item['mean_distance']:.2f}",
            str(item["largest_distance"]),
            str(item["recent_count"]),
            f"{item['change_rate'] * 100:+.2f}%",
        )
        for item in report.event_metrics
    ]


def import_report_summary(report) -> str:
    return (
        f"Sheet: {report.sheet_name}\n"
        f"Dòng đã đọc: {report.rows_read}\n"
        f"Hợp lệ: {report.valid_rows}\n"
        f"Không hợp lệ: {report.invalid_rows}\n"
        f"Ngày trùng trong file: {report.duplicate_dates_in_file}\n"
        f"Khoảng ngày: {report.first_date or '-'} đến {report.last_date or '-'}"
    )


class StatCard(QFrame):
    def __init__(self, title: str, value: str = "-") -> None:
        super().__init__()
        self.setObjectName("StatCard")
        layout = QVBoxLayout(self)

        title_label = QLabel(title)
        title_label.setObjectName("StatTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatValue")
        self.value_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(self.value_label)
        layout.addStretch()

    def set_value(self, value: object) -> None:
        self.value_label.setText(str(value))


class MainWindow(QMainWindow):
    DRAW_COLUMNS = (
        "Ngày",
        "Thứ",
        "Bộ số",
        "Tổng",
        "Lẻ/Chẵn",
        "Thấp/Cao",
        "Nguồn",
    )
    METRIC_COLUMNS = (
        "Giá trị",
        "Số lần",
        "Tỷ lệ",
        "Khoảng vắng",
        "Gap TB",
        "Gap lớn nhất",
        "30 kỳ gần",
        "Xu hướng",
    )

    def __init__(self, database: DatabaseManager | None = None) -> None:
        super().__init__()
        self.database = database or DATABASE
        self.database.initialize()
        self.importer = ExcelDrawImporter(self.database)
        self.analysis_service = AnalysisService(self.database)
        self.current_draws: list[Draw] = []
        self.current_report = None

        self.setWindowTitle(f"{APP_NAME} v{VERSION}")
        self.resize(1240, 790)
        self.setMinimumSize(980, 650)
        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 12)
        root_layout.setSpacing(12)

        root_layout.addWidget(self._build_header())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_dashboard_tab(), "Tổng quan")
        self.tabs.addTab(self._build_data_tab(), "Dữ liệu lịch sử")
        self.tabs.addTab(self._build_analysis_tab(), "Thống kê & kiểm tra")
        root_layout.addWidget(self.tabs, 1)

        self.setCentralWidget(root)
        self.statusBar().showMessage("Sẵn sàng")

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("HeaderFrame")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(22, 16, 22, 16)

        text_layout = QVBoxLayout()
        title = QLabel("APE – Adaptive Prediction Engine")
        title.setObjectName("HeaderTitle")
        subtitle = QLabel(
            f"Phiên bản {VERSION} · {BUILD_NAME} · Phân tích dữ liệu lịch sử"
        )
        subtitle.setObjectName("HeaderSubtitle")
        text_layout.addWidget(title)
        text_layout.addWidget(subtitle)

        import_button = QPushButton("Nhập file Excel")
        import_button.clicked.connect(self.import_excel)
        refresh_button = QPushButton("Làm mới")
        refresh_button.setObjectName("SecondaryButton")
        refresh_button.clicked.connect(self.refresh_all)

        layout.addLayout(text_layout, 1)
        layout.addWidget(import_button)
        layout.addWidget(refresh_button)
        return header

    def _build_dashboard_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)

        cards = QGridLayout()
        self.total_card = StatCard("Tổng số kỳ")
        self.period_card = StatCard("Khoảng dữ liệu")
        self.health_card = StatCard("Database")
        self.quality_card = StatCard("Chất lượng dữ liệu")
        cards.addWidget(self.total_card, 0, 0)
        cards.addWidget(self.period_card, 0, 1)
        cards.addWidget(self.health_card, 0, 2)
        cards.addWidget(self.quality_card, 0, 3)
        layout.addLayout(cards)

        action_row = QHBoxLayout()
        open_data_button = QPushButton("Mở thư mục dữ liệu")
        open_data_button.setObjectName("SecondaryButton")
        open_data_button.clicked.connect(self.open_data_folder)
        action_row.addWidget(open_data_button)
        action_row.addStretch()
        layout.addLayout(action_row)

        recent_title = QLabel("Các kỳ gần nhất")
        recent_title.setStyleSheet("font-size: 12pt; font-weight: 700;")
        layout.addWidget(recent_title)

        self.recent_table = self._create_table(self.DRAW_COLUMNS)
        self.recent_table.setMaximumHeight(260)
        layout.addWidget(self.recent_table)
        return tab

    def _build_data_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        self.data_table = self._create_table(self.DRAW_COLUMNS)
        layout.addWidget(self.data_table)
        return tab

    def _build_analysis_tab(self) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)

        self.metric_table = self._create_table(self.METRIC_COLUMNS)
        layout.addWidget(self.metric_table, 3)

        side_layout = QVBoxLayout()
        pairs_title = QLabel("Cặp và bộ ba xuất hiện nhiều")
        pairs_title.setStyleSheet("font-size: 11pt; font-weight: 700;")
        self.groups_text = QPlainTextEdit()
        self.groups_text.setReadOnly(True)

        audit_title = QLabel("Kiểm tra chất lượng")
        audit_title.setStyleSheet("font-size: 11pt; font-weight: 700;")
        self.audit_text = QPlainTextEdit()
        self.audit_text.setReadOnly(True)

        side_layout.addWidget(pairs_title)
        side_layout.addWidget(self.groups_text, 1)
        side_layout.addWidget(audit_title)
        side_layout.addWidget(self.audit_text, 1)
        layout.addLayout(side_layout, 2)
        return tab

    @staticmethod
    def _create_table(columns: tuple[str, ...]) -> QTableWidget:
        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.verticalHeader().setVisible(False)

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        if len(columns) >= 3:
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        return table

    def refresh_all(self) -> None:
        try:
            self.statusBar().showMessage("Đang tải dữ liệu...")
            with self.database.session() as session:
                self.current_draws = DrawRepository(session).list_chronological()

            rows = draw_table_rows(self.current_draws)
            self._fill_table(self.data_table, rows)
            self._fill_table(self.recent_table, list(reversed(rows[-8:])))

            total = len(self.current_draws)
            self.total_card.set_value(total)
            self.health_card.set_value(
                "Hoạt động" if self.database.health_check() else "Có lỗi"
            )

            if self.current_draws:
                first_date = self.current_draws[0].draw_date.strftime("%d/%m/%Y")
                last_date = self.current_draws[-1].draw_date.strftime("%d/%m/%Y")
                self.period_card.set_value(f"{first_date}\n→ {last_date}")
                self.current_report = self.analysis_service.generate(limit=10)
                self._populate_analysis()
            else:
                self.period_card.set_value("Chưa có dữ liệu")
                self.quality_card.set_value("-")
                self.metric_table.setRowCount(0)
                self.groups_text.setPlainText(
                    "Hãy chọn “Nhập file Excel” để bắt đầu."
                )
                self.audit_text.clear()

            self.statusBar().showMessage(f"Đã tải {total} kỳ dữ liệu", 5000)
        except Exception as exc:
            self._show_error("Không thể làm mới dữ liệu", exc)

    def _populate_analysis(self) -> None:
        report = self.current_report
        if report is None:
            return

        self.quality_card.set_value(f"{report.audit['quality_score']}/100")
        self._fill_table(self.metric_table, analysis_metric_rows(report))

        pair_lines = [
            f"{index}. {item['values']} — {item['count']} lần"
            for index, item in enumerate(report.common_pairs, 1)
        ]
        triple_lines = [
            f"{index}. {item['values']} — {item['count']} lần"
            for index, item in enumerate(report.common_triples, 1)
        ]
        self.groups_text.setPlainText(
            "CẶP PHỔ BIẾN\n"
            + "\n".join(pair_lines)
            + "\n\nBỘ BA PHỔ BIẾN\n"
            + "\n".join(triple_lines)
        )

        audit = report.audit
        long_gaps = audit.get("long_date_gaps_over_14_days", [])
        long_gap_lines = [
            f"{item['from']} → {item['to']}: {item['days']} ngày"
            for item in long_gaps[:8]
        ]
        self.audit_text.setPlainText(
            f"Điểm chất lượng: {audit['quality_score']}/100\n"
            f"Dòng lỗi: {audit['invalid_row_count']}\n"
            f"Ngày trùng: {audit['duplicate_date_count']}\n"
            f"Sai thứ: {audit['weekday_mismatch_count']}\n"
            f"Thiếu thông tin nguồn: "
            f"{audit['missing_source_metadata_count']}\n\n"
            "Khoảng ngày dài trên 14 ngày:\n"
            + ("\n".join(long_gap_lines) if long_gap_lines else "Không có")
        )

    def import_excel(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file dữ liệu Excel",
            str(Path.home()),
            "Excel Workbook (*.xlsx *.xls)",
        )
        if not selected:
            return

        try:
            self.statusBar().showMessage("Đang kiểm tra file Excel...")
            validation = self.importer.validate_file(selected)
            summary = import_report_summary(validation)

            if validation.invalid_rows:
                details = "\n".join(
                    f"- Dòng {issue.row}: {issue.message}"
                    for issue in validation.errors[:10]
                )
                answer = QMessageBox.warning(
                    self,
                    "File có dòng không hợp lệ",
                    summary
                    + "\n\n"
                    + details
                    + "\n\nChỉ các dòng hợp lệ sẽ được nhập. Tiếp tục?",
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
            else:
                answer = QMessageBox.question(
                    self,
                    "Xác nhận nhập dữ liệu",
                    summary + "\n\nTiến hành nhập vào database?",
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )

            if answer != QMessageBox.StandardButton.Yes:
                self.statusBar().showMessage("Đã hủy nhập dữ liệu", 4000)
                return

            result = self.importer.import_file(selected)
            QMessageBox.information(
                self,
                "Nhập dữ liệu hoàn tất",
                (
                    f"Thêm mới: {result.inserted_rows}\n"
                    f"Cập nhật: {result.updated_rows}\n"
                    f"Bỏ qua: {result.skipped_rows}\n"
                    f"Dòng lỗi: {result.invalid_rows}"
                ),
            )
            self.refresh_all()
        except Exception as exc:
            self._show_error("Không thể nhập file Excel", exc)

    def open_data_folder(self) -> None:
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(SETTINGS.data_dir.resolve()))
        )

    @staticmethod
    def _fill_table(
        table: QTableWidget,
        rows: list[tuple[str, ...]],
    ) -> None:
        table.setUpdatesEnabled(False)
        try:
            table.setRowCount(len(rows))
            for row_index, values in enumerate(rows):
                for column_index, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    if column_index in {0, 1, 3, 4, 5}:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(row_index, column_index, item)
        finally:
            table.setUpdatesEnabled(True)

    def _show_error(self, title: str, error: Exception) -> None:
        self.statusBar().showMessage("Có lỗi", 5000)
        QMessageBox.critical(self, title, str(error))


def run_gui() -> int:
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    application.setOrganizationName("APE")
    application.setStyleSheet(APP_STYLESHEET)

    window = MainWindow()
    window.show()
    return application.exec()


__all__ = [
    "APP_STYLESHEET",
    "MainWindow",
    "StatCard",
    "analysis_metric_rows",
    "draw_table_rows",
    "format_numbers",
    "import_report_summary",
    "run_gui",
]
