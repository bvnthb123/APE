"""Desktop GUI for APE using PySide6."""

from __future__ import annotations

from datetime import date, datetime
import sys
from pathlib import Path
from typing import Iterable

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDateEdit,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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
from ape.gui.preferences import GuiPreferences
from ape.importers.excel_importer import ExcelDrawImporter
from ape.release.backup import BackupManager
from ape.reports.excel_exporter import ExcelReportExporter


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
QLineEdit, QDateEdit {
    background: white;
    border: 1px solid #B8CCE0;
    border-radius: 6px;
    padding: 6px 8px;
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


def application_root() -> Path:
    """Return the folder users should treat as the current application root."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def icon_path() -> Path:
    return application_root() / "assets" / "ape_icon.svg"


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


def filter_draws(
    draws: Iterable[Draw],
    start_date: date | None = None,
    end_date: date | None = None,
    query: str = "",
) -> list[Draw]:
    """Filter historical draws by date range and free-text query."""
    normalized_query = query.strip().lower()
    filtered: list[Draw] = []
    for draw in draws:
        if start_date and draw.draw_date < start_date:
            continue
        if end_date and draw.draw_date > end_date:
            continue
        if normalized_query:
            searchable = " ".join(draw_table_rows([draw])).lower()
            if normalized_query not in searchable:
                continue
        filtered.append(draw)
    return filtered


def import_report_summary(report) -> str:
    return (
        f"Sheet: {report.sheet_name}\n"
        f"Dòng đã đọc: {report.rows_read}\n"
        f"Hợp lệ: {report.valid_rows}\n"
        f"Không hợp lệ: {report.invalid_rows}\n"
        f"Ngày trùng trong file: {report.duplicate_dates_in_file}\n"
        f"Khoảng ngày: {report.first_date or '-'} đến {report.last_date or '-'}"
    )


def date_to_qdate(value: date) -> QDate:
    return QDate(value.year, value.month, value.day)


def qdate_to_date(value: QDate) -> date:
    return date(value.year(), value.month(), value.day())


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


class ChartCanvas(QWidget):
    """Reusable Matplotlib canvas for embedded GUI charts."""

    def __init__(self, title: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 12pt; font-weight: 700;")
        self.figure = Figure(figsize=(8, 3.2), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(title_label)
        layout.addWidget(self.canvas, 1)

    def clear(self, message: str = "Chưa có dữ liệu") -> None:
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        axis.text(0.5, 0.5, message, ha="center", va="center")
        axis.set_axis_off()
        self.canvas.draw_idle()

    def plot_bar(
        self,
        x_values,
        y_values,
        *,
        title: str,
        y_label: str,
        x_label: str = "Giá trị",
    ) -> None:
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        axis.bar(x_values, y_values)
        axis.set_title(title)
        axis.set_ylabel(y_label)
        axis.set_xlabel(x_label)
        axis.tick_params(axis="x", rotation=90)
        axis.grid(axis="y", alpha=0.25)
        self.canvas.draw_idle()

    def plot_line(
        self,
        x_values,
        y_values,
        *,
        title: str,
        y_label: str,
        x_label: str = "Giá trị",
    ) -> None:
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        axis.plot(x_values, y_values, marker="o", linewidth=1.5)
        axis.set_title(title)
        axis.set_ylabel(y_label)
        axis.set_xlabel(x_label)
        axis.tick_params(axis="x", rotation=90)
        axis.grid(alpha=0.25)
        self.canvas.draw_idle()


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
        self.exporter = ExcelReportExporter(self.database)
        self.backup_manager = BackupManager()
        self.preferences = GuiPreferences.load()
        self.current_draws: list[Draw] = []
        self.filtered_draws: list[Draw] = []
        self.current_report = None
        self.filter_bounds_ready = False

        self.setWindowTitle(f"{APP_NAME} v{VERSION}")
        current_icon = icon_path()
        if current_icon.exists():
            self.setWindowIcon(QIcon(str(current_icon)))
        self.resize(self.preferences.window_width, self.preferences.window_height)
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
        self.tabs.addTab(self._build_charts_tab(), "Biểu đồ")
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
        export_button = QPushButton("Xuất báo cáo Excel")
        export_button.clicked.connect(self.export_excel)
        refresh_button = QPushButton("Làm mới")
        refresh_button.setObjectName("SecondaryButton")
        refresh_button.clicked.connect(self.refresh_all)

        layout.addLayout(text_layout, 1)
        layout.addWidget(import_button)
        layout.addWidget(export_button)
        layout.addWidget(refresh_button)
        return header

    def _build_dashboard_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)

        cards = QGridLayout()
        self.total_card = StatCard("Tổng số kỳ")
        self.filtered_card = StatCard("Đang lọc")
        self.period_card = StatCard("Khoảng dữ liệu")
        self.health_card = StatCard("Database")
        self.quality_card = StatCard("Chất lượng dữ liệu")
        cards.addWidget(self.total_card, 0, 0)
        cards.addWidget(self.filtered_card, 0, 1)
        cards.addWidget(self.period_card, 0, 2)
        cards.addWidget(self.health_card, 0, 3)
        cards.addWidget(self.quality_card, 0, 4)
        layout.addLayout(cards)

        action_row = QHBoxLayout()
        open_data_button = QPushButton("Mở thư mục dữ liệu")
        open_data_button.setObjectName("SecondaryButton")
        open_data_button.clicked.connect(self.open_data_folder)
        open_reports_button = QPushButton("Mở thư mục báo cáo")
        open_reports_button.setObjectName("SecondaryButton")
        open_reports_button.clicked.connect(self.open_reports_folder)
        open_app_button = QPushButton("Mở thư mục ứng dụng")
        open_app_button.setObjectName("SecondaryButton")
        open_app_button.clicked.connect(self.open_app_folder)
        backup_button = QPushButton("Sao lưu DB")
        backup_button.clicked.connect(self.backup_database)
        restore_button = QPushButton("Khôi phục DB")
        restore_button.setObjectName("SecondaryButton")
        restore_button.clicked.connect(self.restore_database)
        about_button = QPushButton("Giới thiệu")
        about_button.setObjectName("SecondaryButton")
        about_button.clicked.connect(self.show_about)
        action_row.addWidget(open_data_button)
        action_row.addWidget(open_reports_button)
        action_row.addWidget(open_app_button)
        action_row.addWidget(backup_button)
        action_row.addWidget(restore_button)
        action_row.addWidget(about_button)
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

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Từ ngày"))
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.start_date_edit.setCalendarPopup(True)
        filter_row.addWidget(self.start_date_edit)

        filter_row.addWidget(QLabel("Đến ngày"))
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.end_date_edit.setCalendarPopup(True)
        filter_row.addWidget(self.end_date_edit)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Tìm ngày, thứ, bộ số, tổng hoặc tên file nguồn..."
        )
        self.search_input.returnPressed.connect(self.apply_data_filters)
        filter_row.addWidget(self.search_input, 1)

        apply_button = QPushButton("Lọc")
        apply_button.clicked.connect(self.apply_data_filters)
        reset_button = QPushButton("Xóa lọc")
        reset_button.setObjectName("SecondaryButton")
        reset_button.clicked.connect(self.reset_data_filters)
        filter_row.addWidget(apply_button)
        filter_row.addWidget(reset_button)
        layout.addLayout(filter_row)

        self.filter_status_label = QLabel("Đang hiển thị 0/0 kỳ")
        self.filter_status_label.setStyleSheet("color: #5E7184;")
        layout.addWidget(self.filter_status_label)

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

    def _build_charts_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        self.frequency_chart = ChartCanvas("Tần suất xuất hiện 01–45")
        self.gap_chart = ChartCanvas("Khoảng vắng hiện tại")
        self.total_sum_chart = ChartCanvas("Diễn biến tổng theo thời gian")
        self.odd_even_chart = ChartCanvas("Phân bố cấu trúc lẻ/chẵn")
        layout.addWidget(self.frequency_chart, 1)
        layout.addWidget(self.gap_chart, 1)
        layout.addWidget(self.total_sum_chart, 1)
        layout.addWidget(self.odd_even_chart, 1)
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

            total = len(self.current_draws)
            self.total_card.set_value(total)
            self.health_card.set_value(
                "Hoạt động" if self.database.health_check() else "Có lỗi"
            )

            if self.current_draws:
                first_date = self.current_draws[0].draw_date
                last_date = self.current_draws[-1].draw_date
                self.period_card.set_value(
                    f"{first_date.strftime('%d/%m/%Y')}\n→ "
                    f"{last_date.strftime('%d/%m/%Y')}"
                )
                self._sync_filter_bounds(first_date, last_date)
                self.apply_data_filters(show_message=False)
                self.current_report = self.analysis_service.generate(limit=10)
                self._populate_analysis()
                self._populate_charts()
            else:
                self.filtered_draws = []
                self.filtered_card.set_value("0/0")
                self.filter_status_label.setText("Đang hiển thị 0/0 kỳ")
                self.period_card.set_value("Chưa có dữ liệu")
                self.quality_card.set_value("-")
                self._fill_table(self.data_table, [])
                self._fill_table(self.recent_table, [])
                self.metric_table.setRowCount(0)
                self.groups_text.setPlainText(
                    "Hãy chọn “Nhập file Excel” để bắt đầu."
                )
                self.audit_text.clear()
                self.frequency_chart.clear()
                self.gap_chart.clear()
                self.total_sum_chart.clear()
                self.odd_even_chart.clear()

            self.statusBar().showMessage(f"Đã tải {total} kỳ dữ liệu", 5000)
        except Exception as exc:
            self._show_error("Không thể làm mới dữ liệu", exc)

    def _sync_filter_bounds(self, first_date: date, last_date: date) -> None:
        start_qdate = date_to_qdate(first_date)
        end_qdate = date_to_qdate(last_date)
        for editor in (self.start_date_edit, self.end_date_edit):
            editor.setDateRange(start_qdate, end_qdate)
        if not self.filter_bounds_ready:
            self.start_date_edit.setDate(start_qdate)
            self.end_date_edit.setDate(end_qdate)
            self.filter_bounds_ready = True

    def apply_data_filters(self, show_message: bool = True) -> None:
        if not self.current_draws:
            self.filtered_draws = []
            self._fill_table(self.data_table, [])
            self._fill_table(self.recent_table, [])
            return

        start = qdate_to_date(self.start_date_edit.date())
        end = qdate_to_date(self.end_date_edit.date())
        if start > end:
            QMessageBox.warning(
                self,
                "Khoảng ngày không hợp lệ",
                "Ngày bắt đầu không được lớn hơn ngày kết thúc.",
            )
            return
        self.filtered_draws = filter_draws(
            self.current_draws,
            start,
            end,
            self.search_input.text(),
        )
        rows = draw_table_rows(self.filtered_draws)
        self._fill_table(self.data_table, rows)
        self._fill_table(self.recent_table, list(reversed(rows[-8:])))
        summary = f"{len(self.filtered_draws)}/{len(self.current_draws)}"
        self.filtered_card.set_value(summary)
        self.filter_status_label.setText(f"Đang hiển thị {summary} kỳ")
        if show_message:
            self.statusBar().showMessage(f"Đã lọc {summary} kỳ", 4000)

    def reset_data_filters(self) -> None:
        if not self.current_draws:
            return
        self.start_date_edit.setDate(date_to_qdate(self.current_draws[0].draw_date))
        self.end_date_edit.setDate(date_to_qdate(self.current_draws[-1].draw_date))
        self.search_input.clear()
        self.apply_data_filters()

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

    def _populate_charts(self) -> None:
        report = self.current_report
        if report is None:
            return
        labels = [f"{item['event_id']:02d}" for item in report.event_metrics]
        counts = [item["count"] for item in report.event_metrics]
        gaps = [item["latest_distance"] for item in report.event_metrics]
        self.frequency_chart.plot_bar(
            labels,
            counts,
            title="Số lần xuất hiện trong toàn bộ lịch sử",
            y_label="Số lần",
        )
        self.gap_chart.plot_line(
            labels,
            gaps,
            title="Số kỳ chưa xuất hiện tính đến kỳ mới nhất",
            y_label="Số kỳ",
        )

        recent_draws = self.current_draws[-60:]
        self.total_sum_chart.plot_line(
            [draw.draw_date.strftime("%d/%m") for draw in recent_draws],
            [draw.total_sum for draw in recent_draws],
            title="Tổng bộ số trong 60 kỳ gần nhất",
            y_label="Tổng",
            x_label="Kỳ",
        )
        odd_even = report.structure.get("odd_even_patterns", {})
        self.odd_even_chart.plot_bar(
            list(odd_even.keys()),
            list(odd_even.values()),
            title="Phân bố số lượng lẻ/chẵn",
            y_label="Số kỳ",
            x_label="Mẫu lẻ-chẵn",
        )

    def import_excel(self) -> None:
        start_dir = self.preferences.last_excel_dir or str(Path.home())
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file dữ liệu Excel",
            start_dir,
            "Excel Workbook (*.xlsx *.xls)",
        )
        if not selected:
            return
        self.preferences.last_excel_dir = str(Path(selected).parent)
        self.preferences.save()

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
            self.filter_bounds_ready = False
            self.refresh_all()
        except Exception as exc:
            self._show_error("Không thể nhập file Excel", exc)

    def export_excel(self) -> None:
        if not self.current_draws:
            QMessageBox.information(
                self,
                "Chưa có dữ liệu",
                "Hãy nhập file Excel trước khi xuất báo cáo.",
            )
            return
        output_dir = Path(self.preferences.last_report_dir or SETTINGS.reports_dir)
        default_name = output_dir / (
            "ape_report_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".xlsx"
        )
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu báo cáo Excel",
            str(default_name),
            "Excel Workbook (*.xlsx)",
        )
        if not selected:
            return
        self.preferences.last_report_dir = str(Path(selected).parent)
        self.preferences.save()

        try:
            self.statusBar().showMessage("Đang xuất báo cáo Excel...")
            output_path = self.exporter.export(selected, limit=20)
            QMessageBox.information(
                self,
                "Xuất báo cáo thành công",
                f"Đã lưu báo cáo tại:\n{output_path}",
            )
            self.statusBar().showMessage("Xuất báo cáo thành công", 5000)
        except Exception as exc:
            self._show_error("Không thể xuất báo cáo Excel", exc)

    def backup_database(self) -> None:
        try:
            self.statusBar().showMessage("Đang sao lưu database...")
            result = self.backup_manager.backup()
            QMessageBox.information(
                self,
                "Sao lưu database thành công",
                (
                    "Đã tạo bản sao lưu:\n"
                    f"{result.target}\n\n"
                    f"Dung lượng: {result.bytes_copied:,} bytes"
                ),
            )
            self.statusBar().showMessage("Sao lưu database thành công", 5000)
        except Exception as exc:
            self._show_error("Không thể sao lưu database", exc)

    def restore_database(self) -> None:
        start_dir = str(self.backup_manager.backup_dir)
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file database sao lưu",
            start_dir,
            "SQLite Database (*.db *.sqlite *.backup)",
        )
        if not selected:
            return
        answer = QMessageBox.warning(
            self,
            "Xác nhận khôi phục database",
            (
                "Thao tác này sẽ thay thế database hiện tại bằng file sao lưu đã chọn.\n"
                "APE sẽ tự tạo một bản backup an toàn trước khi khôi phục.\n\n"
                "Tiếp tục khôi phục?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.statusBar().showMessage("Đang khôi phục database...")
            self.database.dispose()
            result = self.backup_manager.restore(selected)
            self.database.initialize()
            self.filter_bounds_ready = False
            self.refresh_all()
            QMessageBox.information(
                self,
                "Khôi phục database thành công",
                f"Đã khôi phục từ:\n{result.source}",
            )
            self.statusBar().showMessage("Khôi phục database thành công", 5000)
        except Exception as exc:
            try:
                self.database.initialize()
            except Exception:
                pass
            self._show_error("Không thể khôi phục database", exc)

    def open_data_folder(self) -> None:
        SETTINGS.data_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(SETTINGS.data_dir.resolve()))
        )

    def open_reports_folder(self) -> None:
        SETTINGS.reports_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(SETTINGS.reports_dir.resolve()))
        )

    def open_app_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(application_root())))

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "Giới thiệu APE",
            (
                f"<b>{APP_NAME}</b><br>"
                f"Phiên bản: {VERSION}<br>"
                f"Build: {BUILD_NAME}<br><br>"
                "APE là ứng dụng desktop hỗ trợ nhập, kiểm tra, thống kê "
                "và xuất báo cáo dữ liệu lịch sử.<br><br>"
                "Các thống kê chỉ mô tả dữ liệu quá khứ, không phải cam kết "
                "hay bảo đảm cho kết quả tương lai."
            ),
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

    def closeEvent(self, event: QCloseEvent) -> None:
        self.preferences.window_width = self.width()
        self.preferences.window_height = self.height()
        self.preferences.save()
        super().closeEvent(event)

    def _show_error(self, title: str, error: Exception) -> None:
        self.statusBar().showMessage("Có lỗi", 5000)
        QMessageBox.critical(self, title, str(error))


def run_gui() -> int:
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    application.setOrganizationName("APE")
    icon = icon_path()
    if icon.exists():
        application.setWindowIcon(QIcon(str(icon)))
    application.setStyleSheet(APP_STYLESHEET)

    window = MainWindow()
    window.show()
    return application.exec()


__all__ = [
    "APP_STYLESHEET",
    "ChartCanvas",
    "MainWindow",
    "StatCard",
    "analysis_metric_rows",
    "application_root",
    "draw_table_rows",
    "filter_draws",
    "format_numbers",
    "icon_path",
    "import_report_summary",
    "run_gui",
]
