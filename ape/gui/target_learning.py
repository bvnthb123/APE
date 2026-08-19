"""Desktop target-learning window for one-row method fitting."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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
from ape.patterns.target_learning import (
    LearnedMethod,
    LearnedMethodStore,
    TargetLearningEngine,
    build_target_draw,
    learned_method_signal_values,
    next_auto_draw_date,
    parse_target_numbers,
)


TARGET_LEARNING_STYLESHEET = """
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
QLineEdit, QSpinBox, QPlainTextEdit {
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
QPushButton#SecondaryButton {
    background: white;
    color: #005BAC;
    border: 1px solid #9DBFDF;
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


class TargetLearningWindow(QWidget):
    """One-input window that fits methods to a newly known row."""

    COLUMNS = (
        "Hạng",
        "Loại",
        "Phương pháp",
        "Top fit dãy vừa nhập",
        "Khớp",
        "Số trùng",
        "Điểm fit",
        "Top kỳ tiếp theo",
    )

    def __init__(self, database: DatabaseManager | None = None) -> None:
        super().__init__()
        self.database = database or DATABASE
        self.database.initialize()
        self.engine = TargetLearningEngine()
        self.store = LearnedMethodStore()
        self.learned_methods: list[LearnedMethod] = []
        self.next_signal_values: tuple[int, ...] = ()

        self.setWindowTitle(f"APE v{VERSION} - Học từ dãy số mới")
        self.resize(1180, 720)
        self.setStyleSheet(TARGET_LEARNING_STYLESHEET)
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
        title = QLabel("Học từ dãy số mới & tính kỳ tiếp theo")
        title.setObjectName("HeaderTitle")
        subtitle = QLabel(
            f"Phiên bản {VERSION} · {BUILD_NAME} · Nhập 1 dãy số để tool fit phương pháp"
        )
        subtitle.setObjectName("HeaderSubtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addWidget(header)

        note = QLabel(
            "Nhập dãy số đã có kết quả thật. APE sẽ thử nhiều phương pháp đơn lẻ và tổ hợp để "
            "khớp lại dãy đó, lưu các phương pháp tốt nhất, đưa dãy vào dữ liệu lịch sử, rồi tính "
            "Top tín hiệu tham chiếu cho kỳ tiếp theo bằng các phương pháp đã học."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #5E7184; font-style: italic;")
        layout.addWidget(note)

        row = QHBoxLayout()
        row.addWidget(QLabel("Dãy số kỳ mới"))
        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("Ví dụ: 03 11 18 24 36 42")
        row.addWidget(self.target_input, 1)

        row.addWidget(QLabel("Top"))
        self.top_spin = QSpinBox()
        self.top_spin.setRange(6, 20)
        self.top_spin.setValue(7)
        row.addWidget(self.top_spin)

        row.addWidget(QLabel("Lag tối đa"))
        self.lag_spin = QSpinBox()
        self.lag_spin.setRange(1, 20)
        self.lag_spin.setValue(10)
        row.addWidget(self.lag_spin)

        self.learn_button = QPushButton("Học từ dãy này và tính kỳ tiếp theo")
        self.learn_button.clicked.connect(self.learn_from_target)
        row.addWidget(self.learn_button)

        self.apply_button = QPushButton("Áp dụng phương pháp đã học")
        self.apply_button.setObjectName("SecondaryButton")
        self.apply_button.clicked.connect(self.apply_learned_methods)
        row.addWidget(self.apply_button)
        layout.addLayout(row)

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
        header_table = self.table.horizontalHeader()
        header_table.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header_table.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header_table.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header_table.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 2)

        self.result_text = QPlainTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("Kết quả học và Top kỳ tiếp theo sẽ hiển thị tại đây.")
        layout.addWidget(self.result_text, 1)

    def load_draws(self):
        with self.database.session() as session:
            return DrawRepository(session).list_chronological()

    def learn_from_target(self) -> None:
        try:
            target_values = parse_target_numbers(self.target_input.text())
            draws_before = self.load_draws()
            if len(draws_before) < 30:
                QMessageBox.information(self, "Chưa đủ dữ liệu", "Cần có ít nhất khoảng 30 kỳ lịch sử để học phương pháp.")
                return

            self.learn_button.setEnabled(False)
            self.result_text.setPlainText("Đang thử nhiều cách tính và tổ hợp phương pháp...")
            QApplication.processEvents()

            self.learned_methods = self.engine.learn_methods(
                draws_before,
                target_values,
                top_k=self.top_spin.value(),
                max_lag=self.lag_spin.value(),
                support_values=(1, 2, 3),
                strategy_mode="full",
                limit=20,
                ensemble_pool=14,
            )
            if not self.learned_methods:
                QMessageBox.information(self, "Chưa tìm được phương pháp", "Không tìm được phương pháp đủ dữ liệu để lưu.")
                return

            saved_path = self.store.save(self.learned_methods)
            auto_date = next_auto_draw_date(draws_before)
            draw = build_target_draw(auto_date, target_values)
            with self.database.session() as session:
                _, created = DrawRepository(session).upsert(draw)

            draws_after = self.load_draws()
            _methods, self.next_signal_values = learned_method_signal_values(
                draws_after,
                store=self.store,
                engine=self.engine,
                top_k=self.top_spin.value(),
            )
            self.fill_table()
            self.refresh_saved_label()
            self.result_text.setPlainText(
                self.format_result(
                    target_values=target_values,
                    saved_path=str(saved_path),
                    stored_date=auto_date.strftime("%d/%m/%Y"),
                    created=created,
                )
            )
            QMessageBox.information(self, "Hoàn tất", "Đã học phương pháp, lưu lại và tính kỳ tiếp theo.")
        except Exception as exc:
            QMessageBox.critical(self, "Không thể học từ dãy số", str(exc))
        finally:
            self.learn_button.setEnabled(True)

    def apply_learned_methods(self) -> None:
        try:
            draws = self.load_draws()
            self.learned_methods = list(self.store.load())
            if not self.learned_methods:
                QMessageBox.information(self, "Chưa có phương pháp", "Hãy nhập dãy số mới để tool học phương pháp trước.")
                return
            self.next_signal_values = self.engine.combined_signal_values(
                draws,
                self.learned_methods,
                top_k=self.top_spin.value(),
            )
            self.fill_table()
            self.result_text.setPlainText(
                "ÁP DỤNG BỘ PHƯƠNG PHÁP ĐÃ HỌC\n"
                f"Số phương pháp đang dùng: {len(self.learned_methods)}\n"
                f"Top tín hiệu tham chiếu kỳ tiếp theo:\n{self.format_values(self.next_signal_values)}\n\n"
                "Đây là tín hiệu thống kê từ lịch sử và các phương pháp đã fit dãy đã biết, không phải cam kết tương lai."
            )
        except Exception as exc:
            QMessageBox.critical(self, "Không thể áp dụng phương pháp đã học", str(exc))

    def fill_table(self) -> None:
        self.table.setRowCount(len(self.learned_methods))
        for row_index, method in enumerate(self.learned_methods):
            next_values = self.engine.signal_values_from_method(
                self.load_draws(),
                method,
                top_k=self.top_spin.value(),
            )
            for column_index, value in enumerate(method.to_row(row_index + 1, next_values)):
                item = QTableWidgetItem(str(value))
                if column_index in {0, 1, 4, 6}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, column_index, item)
        if self.learned_methods:
            self.table.selectRow(0)

    def refresh_saved_label(self) -> None:
        methods = self.store.load()
        if not methods:
            self.saved_label.setText("Chưa có bộ phương pháp đã học.")
        else:
            best = methods[0]
            self.saved_label.setText(
                f"Đang lưu {len(methods)} phương pháp · Khớp tốt nhất: {best.fit_match_count}/6 · "
                f"lưu lúc {best.saved_at or '-'}"
            )

    def format_result(
        self,
        *,
        target_values: tuple[int, ...],
        saved_path: str,
        stored_date: str,
        created: bool,
    ) -> str:
        best = self.learned_methods[0] if self.learned_methods else None
        lines = [
            "================ TARGET LEARNING LAB ================",
            f"Dãy số đã nhập: {self.format_values(target_values)}",
            f"Ngày tự lưu vào lịch sử: {stored_date} ({'thêm mới' if created else 'cập nhật'})",
            f"Số phương pháp đã lưu: {len(self.learned_methods)}",
            f"File lưu phương pháp: {saved_path}",
            "",
        ]
        if best is not None:
            lines.extend(
                [
                    "PHƯƠNG PHÁP KHỚP TỐT NHẤT",
                    f"Loại: {'Tổ hợp' if best.method_type == 'ensemble' else 'Đơn lẻ'}",
                    f"Cách tính: {best.label}",
                    f"Top fit dãy vừa nhập: {best.fit_signal_label}",
                    f"Số trùng: {best.fit_match_count}/6",
                    f"Các số trùng: {best.fit_match_label}",
                    "",
                ]
            )
        lines.extend(
            [
                "TOP TÍN HIỆU THAM CHIẾU KỲ TIẾP THEO",
                self.format_values(self.next_signal_values),
                "",
                "Lưu ý: Tool đang học từ dãy đã biết để chọn và lưu phương pháp. Kết quả kỳ tiếp theo vẫn là tín hiệu thống kê, không phải cam kết đúng tuyệt đối.",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def format_values(values) -> str:
        return " - ".join(f"{int(value):02d}" for value in values) if values else "Chưa đủ dữ liệu"



def run_target_learning(database: DatabaseManager | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = TargetLearningWindow(database)
    window.show()
    return app.exec()
