"""Desktop strategy-choice lab for comparing and saving calculation methods."""

from __future__ import annotations

from datetime import date
import sys

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ape.core.version import BUILD_NAME, VERSION
from ape.database.database import DATABASE, DatabaseManager
from ape.database.repositories import DrawRepository
from ape.patterns.strategy_choice import (
    SavedStrategyStore,
    StrategyChoice,
    StrategyChoiceEngine,
    format_values,
    saved_strategy_signal_values,
)


STRATEGY_LAB_STYLESHEET = """
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
QPushButton#SecondaryButton {
    background: white;
    color: #005BAC;
    border: 1px solid #9DBFDF;
}
QDateEdit, QSpinBox, QComboBox, QPlainTextEdit {
    background: white;
    border: 1px solid #C9D8E8;
    border-radius: 8px;
    padding: 6px;
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
"""


class StrategyLabWindow(QWidget):
    """Window for generating many strategies and saving the selected method."""

    COLUMNS = (
        "Hạng",
        "Cách tính",
        "Top 7",
        "≥1 số",
        "Khớp TB",
        "Miss 0",
        "Max",
        "Số kỳ",
        "Phân bố",
    )

    def __init__(self, database: DatabaseManager | None = None) -> None:
        super().__init__()
        self.database = database or DATABASE
        self.database.initialize()
        self.engine = StrategyChoiceEngine()
        self.store = SavedStrategyStore()
        self.choices: list[StrategyChoice] = []

        self.setWindowTitle(f"APE v{VERSION} - Chọn cách tính")
        self.resize(1180, 720)
        self.setStyleSheet(STRATEGY_LAB_STYLESHEET)
        self._build_ui()
        self.refresh_saved_label()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = QFrame()
        header.setObjectName("HeaderFrame")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)
        title = QLabel("Tính lại nhiều cách & lưu cách tính")
        title.setObjectName("HeaderTitle")
        subtitle = QLabel(
            f"Phiên bản {VERSION} · {BUILD_NAME} · So sánh nhiều phương án lịch sử"
        )
        subtitle.setObjectName("HeaderSubtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addWidget(header)

        note = QLabel(
            "Bấm 'Tính lại nhiều cách' để APE tạo nhiều phương án khác nhau. "
            "Chọn dòng bạn thấy phù hợp rồi bấm 'Lưu cách tính đang chọn' để áp dụng cho các lần sau."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #5E7184; font-style: italic;")
        layout.addWidget(note)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Đối chiếu từ"))
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.start_date_edit.setDate(QDate(2026, 3, 1))
        controls.addWidget(self.start_date_edit)

        controls.addWidget(QLabel("Top"))
        self.top_spin = QSpinBox()
        self.top_spin.setRange(5, 20)
        self.top_spin.setValue(7)
        controls.addWidget(self.top_spin)

        controls.addWidget(QLabel("Support"))
        self.support_spin = QSpinBox()
        self.support_spin.setRange(1, 20)
        self.support_spin.setValue(2)
        controls.addWidget(self.support_spin)

        controls.addWidget(QLabel("Mode"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["quick", "full"])
        controls.addWidget(self.mode_combo)

        self.recalculate_button = QPushButton("Tính lại nhiều cách")
        self.recalculate_button.clicked.connect(self.recalculate_many_methods)
        controls.addWidget(self.recalculate_button)

        self.save_button = QPushButton("Lưu cách tính đang chọn")
        self.save_button.clicked.connect(self.save_selected_method)
        controls.addWidget(self.save_button)

        self.apply_button = QPushButton("Áp dụng cách đã lưu")
        self.apply_button.setObjectName("SecondaryButton")
        self.apply_button.clicked.connect(self.apply_saved_method)
        controls.addWidget(self.apply_button)
        controls.addStretch()
        layout.addLayout(controls)

        self.saved_label = QLabel()
        self.saved_label.setStyleSheet("font-weight: 700; color: #005BAC;")
        layout.addWidget(self.saved_label)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 2)

        self.result_text = QPlainTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("Kết quả chi tiết sẽ hiển thị tại đây.")
        layout.addWidget(self.result_text, 1)

    def load_draws(self):
        with self.database.session() as session:
            return DrawRepository(session).list_chronological()

    def recalculate_many_methods(self) -> None:
        try:
            draws = self.load_draws()
            if not draws:
                QMessageBox.information(self, "Chưa có dữ liệu", "Hãy nhập dữ liệu lịch sử trước.")
                return

            self.recalculate_button.setEnabled(False)
            self.result_text.setPlainText("Đang tính lại nhiều cách, vui lòng chờ...")
            QApplication.processEvents()

            qdate = self.start_date_edit.date()
            start_date = date(qdate.year(), qdate.month(), qdate.day())
            self.choices = self.engine.generate_choices(
                draws,
                start_date=start_date,
                end_date=date.today(),
                lag_from=1,
                lag_to=3,
                top_k=self.top_spin.value(),
                base_min_support=self.support_spin.value(),
                min_training_rows=30,
                target_hits=1,
                strategy_mode=self.mode_combo.currentText(),
                limit=15,
            )
            self.fill_table()
            self.result_text.setPlainText(self.format_choices_summary())
        except Exception as exc:
            self.result_text.setPlainText("")
            QMessageBox.critical(self, "Không thể tính lại", str(exc))
        finally:
            self.recalculate_button.setEnabled(True)

    def fill_table(self) -> None:
        self.table.setRowCount(len(self.choices))
        for row_index, choice in enumerate(self.choices):
            for column_index, value in enumerate(choice.to_row(row_index + 1)):
                item = QTableWidgetItem(str(value))
                if column_index in {0, 3, 4, 5, 6, 7}:
                    item.setTextAlignment(int(0x0084))  # AlignCenter
                self.table.setItem(row_index, column_index, item)
        if self.choices:
            self.table.selectRow(0)

    def selected_choice(self) -> StrategyChoice | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        if row < 0 or row >= len(self.choices):
            return None
        return self.choices[row]

    def save_selected_method(self) -> None:
        choice = self.selected_choice()
        if choice is None:
            QMessageBox.information(self, "Chưa chọn cách tính", "Hãy chọn một dòng trong bảng trước.")
            return
        path = self.store.save(choice.to_saved_strategy())
        self.refresh_saved_label()
        QMessageBox.information(
            self,
            "Đã lưu cách tính",
            f"Cách tính đã được lưu tại:\n{path}\n\nAPE sẽ dùng cách này cho các lần áp dụng tiếp theo.",
        )
        self.result_text.setPlainText(
            "ĐÃ LƯU CÁCH TÍNH\n"
            f"Cách tính: {choice.config.detail_label}\n"
            f"Top {choice.top_k}: {choice.signal_label}\n"
            f"Tỷ lệ ≥1 số trong đối chiếu: {choice.one_plus_hit_rate * 100:.2f}%\n"
            f"Số khớp trung bình: {choice.average_hits:.3f}\n"
            f"Miss 0 số: {choice.zero_hit_rate * 100:.2f}%"
        )

    def apply_saved_method(self) -> None:
        try:
            draws = self.load_draws()
            strategy, signals = saved_strategy_signal_values(draws, store=self.store)
            if strategy is None:
                QMessageBox.information(self, "Chưa có cách tính đã lưu", "Hãy tính lại nhiều cách và lưu một cách tính trước.")
                return
            self.result_text.setPlainText(
                "CÁCH TÍNH ĐÃ LƯU ĐANG ĐƯỢC ÁP DỤNG\n"
                f"Lưu lúc: {strategy.saved_at or '-'}\n"
                f"Cách tính: {strategy.label}\n"
                f"Top {strategy.top_k} tín hiệu tham chiếu hiện tại:\n"
                f"{format_values(signals)}\n\n"
                "Lưu ý: Đây là tín hiệu thống kê từ dữ liệu lịch sử, không phải cam kết kết quả tương lai."
            )
        except Exception as exc:
            QMessageBox.critical(self, "Không thể áp dụng cách đã lưu", str(exc))

    def refresh_saved_label(self) -> None:
        saved = self.store.load()
        if saved is None:
            self.saved_label.setText("Chưa lưu cách tính nào.")
        else:
            self.saved_label.setText(
                f"Cách tính đã lưu: {saved.label} · Top {saved.top_k} · lưu lúc {saved.saved_at or '-'}"
            )

    def format_choices_summary(self) -> str:
        if not self.choices:
            return "Chưa tìm được phương án đủ dữ liệu trong khoảng đối chiếu."
        lines = [
            "================ KẾT QUẢ TÍNH LẠI NHIỀU CÁCH ================",
            f"Số phương án hiển thị: {len(self.choices)}",
            "Phương án số 1 đang được xếp cao nhất theo đối chiếu lịch sử.",
            "",
        ]
        for index, choice in enumerate(self.choices[:5], 1):
            lines.append(
                f"{index}. {choice.config.detail_label}\n"
                f"   Top {choice.top_k}: {choice.signal_label}\n"
                f"   ≥1 số: {choice.one_plus_hit_rate * 100:.2f}% | "
                f"TB: {choice.average_hits:.3f} | Miss 0: {choice.zero_hit_rate * 100:.2f}%"
            )
        lines.append("")
        lines.append("Chọn dòng bạn hài lòng trong bảng rồi bấm 'Lưu cách tính đang chọn'.")
        return "\n".join(lines)



def run_strategy_lab(database: DatabaseManager | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = StrategyLabWindow(database)
    window.show()
    return app.exec()
