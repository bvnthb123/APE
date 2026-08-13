"""Small desktop window for manual historical-row entry and Top 7 recalculation."""

from __future__ import annotations

from datetime import date
import sys

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QApplication,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ape.core.version import BUILD_NAME, VERSION
from ape.database.database import DATABASE, DatabaseManager
from ape.manual_entry import ManualRecalculationResult, save_manual_draw_and_recalculate


MANUAL_STYLESHEET = """
QWidget {
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
    font-size: 18pt;
    font-weight: 700;
}
QLabel#HeaderSubtitle {
    color: #D9F2FF;
}
QLineEdit, QDateEdit, QPlainTextEdit {
    background: white;
    border: 1px solid #C9D8E8;
    border-radius: 8px;
    padding: 6px;
}
QPushButton {
    background: #005BAC;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background: #0076D6;
}
"""


class ManualEntryWindow(QWidget):
    """Two-input manual entry window: date and six-number sequence."""

    def __init__(self, database: DatabaseManager | None = None) -> None:
        super().__init__()
        self.database = database or DATABASE
        self.database.initialize()

        self.setWindowTitle(f"APE v{VERSION} - Nhập dữ liệu lịch sử")
        self.resize(820, 620)
        self.setStyleSheet(MANUAL_STYLESHEET)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = QFrame()
        header.setObjectName("HeaderFrame")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)
        title = QLabel("Nhập dữ liệu lịch sử & cập nhật Top 7")
        title.setObjectName("HeaderTitle")
        subtitle = QLabel(
            f"Phiên bản {VERSION} · {BUILD_NAME} · Top tín hiệu cố định = 7"
        )
        subtitle.setObjectName("HeaderSubtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addWidget(header)

        note = QLabel(
            "Nhập một kỳ đã có kết quả thật để APE cập nhật dữ liệu, audit lại lịch sử gần nhất "
            "và cập nhật 7 tín hiệu tham chiếu."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #5E7184; font-style: italic;")
        layout.addWidget(note)

        form_row = QHBoxLayout()
        form_row.addWidget(QLabel("Ngày"))
        self.date_edit = QDateEdit()
        today = date.today()
        self.date_edit.setDate(QDate(today.year, today.month, today.day))
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        form_row.addWidget(self.date_edit)

        form_row.addWidget(QLabel("Dãy số"))
        self.numbers_input = QLineEdit()
        self.numbers_input.setPlaceholderText("Ví dụ: 03 11 18 24 36 42")
        form_row.addWidget(self.numbers_input, 1)
        layout.addLayout(form_row)

        button_row = QHBoxLayout()
        self.save_button = QPushButton("Lưu dữ liệu và tính lại Top 7")
        self.save_button.clicked.connect(self.save_and_recalculate)
        button_row.addWidget(self.save_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.result_text = QPlainTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("Kết quả audit và Top 7 sẽ hiển thị tại đây.")
        layout.addWidget(self.result_text, 1)

    def save_and_recalculate(self) -> None:
        qdate = self.date_edit.date()
        draw_date = date(qdate.year(), qdate.month(), qdate.day())
        raw_numbers = self.numbers_input.text().strip()

        try:
            self.save_button.setEnabled(False)
            self.result_text.setPlainText("Đang lưu dữ liệu và tính lại Top 7...")
            QApplication.processEvents()
            result = save_manual_draw_and_recalculate(
                draw_date,
                raw_numbers,
                database=self.database,
                top_k=7,
            )
            self.result_text.setPlainText(self.format_result(result))
            QMessageBox.information(self, "Hoàn tất", result.saved_label)
        except Exception as exc:
            self.result_text.setPlainText("")
            QMessageBox.critical(self, "Không thể lưu và tính lại", str(exc))
        finally:
            self.save_button.setEnabled(True)

    @staticmethod
    def format_result(result: ManualRecalculationResult) -> str:
        lines = [
            "================ NHẬP DỮ LIỆU ================",
            f"Trạng thái      : {result.saved_label}",
            f"Ngày kỳ         : {result.draw_date.strftime('%d/%m/%Y')}",
            f"Dãy số đã nhập  : {result.numbers_label}",
            f"Top tín hiệu    : {result.top_k}",
            "",
            "================ TOP 7 TÍN HIỆU THAM CHIẾU ================",
            result.signals_label,
            "",
            "================ AUDIT NHANH ================",
        ]
        lines.extend(f"{name}: {value}" for name, value in result.audit_summary_rows)
        lines.extend(
            [
                "",
                "Lưu ý: Đây là tín hiệu thống kê từ dữ liệu lịch sử và audit ngược, không phải cam kết kết quả tương lai.",
            ]
        )
        return "\n".join(lines)



def run_manual_entry(database: DatabaseManager | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = ManualEntryWindow(database)
    window.show()
    return app.exec()
