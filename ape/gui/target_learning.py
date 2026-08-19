"""Desktop target-learning window for one-row method fitting."""

from __future__ import annotations

import sys
from datetime import date

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
from ape.database.models import Draw
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
        self.pending_target_values: tuple[int, ...] | None = None
        self.pending_draw_date: date | None = None
        self.pending_draws_for_next: list[Draw] = []

        self.setWindowTitle(f"APE v{VERSION} - Học từ dãy số mới")
        self.resize(1240, 760)
        self.setStyleSheet(TARGET_LEARNING_STYLESHEET)
        self._build_ui()
        self.refresh_data_status()
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
            "Bước 1: bấm 'Tính thử / Tính lại' để APE thử nhiều phương pháp đơn lẻ và tổ hợp. "
            "Bước này chỉ tính thử, không ghi database. Khi thật sự hài lòng, bấm 'Lưu phương pháp & cập nhật dãy' để đưa dãy vừa nhập vào lịch sử. "
            "Bạn có thể tăng số phương pháp cần tìm để tool rà rộng hơn; số càng lớn thì thời gian chạy càng lâu."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #5E7184; font-style: italic;")
        layout.addWidget(note)

        self.data_status_label = QLabel()
        self.data_status_label.setWordWrap(True)
        self.data_status_label.setStyleSheet(
            "background: white; border: 1px solid #C9D8E8; border-radius: 8px; "
            "padding: 8px; font-weight: 700; color: #005BAC;"
        )
        layout.addWidget(self.data_status_label)

        input_row = QHBoxLayout()
        input_row.addWidget(QLabel("Dãy số kỳ mới"))
        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("Ví dụ: 03 11 18 24 36 42")
        input_row.addWidget(self.target_input, 1)

        input_row.addWidget(QLabel("Top"))
        self.top_spin = QSpinBox()
        self.top_spin.setRange(6, 20)
        self.top_spin.setValue(7)
        input_row.addWidget(self.top_spin)

        input_row.addWidget(QLabel("Lag tối đa"))
        self.lag_spin = QSpinBox()
        self.lag_spin.setRange(1, 30)
        self.lag_spin.setValue(12)
        input_row.addWidget(self.lag_spin)

        self.preview_button = QPushButton("Tính thử / Tính lại")
        self.preview_button.clicked.connect(self.preview_from_target)
        input_row.addWidget(self.preview_button)

        self.commit_button = QPushButton("Lưu phương pháp & cập nhật dãy")
        self.commit_button.clicked.connect(self.commit_pending_learning)
        self.commit_button.setEnabled(False)
        input_row.addWidget(self.commit_button)

        self.apply_button = QPushButton("Áp dụng phương pháp đã học")
        self.apply_button.setObjectName("SecondaryButton")
        self.apply_button.clicked.connect(self.apply_learned_methods)
        input_row.addWidget(self.apply_button)
        layout.addLayout(input_row)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Số phương pháp cần tìm/lưu"))
        self.method_count_spin = QSpinBox()
        self.method_count_spin.setRange(20, 300)
        self.method_count_spin.setSingleStep(10)
        self.method_count_spin.setValue(80)
        search_row.addWidget(self.method_count_spin)

        search_row.addWidget(QLabel("Tổ hợp từ top"))
        self.ensemble_pool_spin = QSpinBox()
        self.ensemble_pool_spin.setRange(5, 80)
        self.ensemble_pool_spin.setSingleStep(5)
        self.ensemble_pool_spin.setValue(30)
        search_row.addWidget(self.ensemble_pool_spin)

        search_row.addWidget(QLabel("Support rà đến"))
        self.support_max_spin = QSpinBox()
        self.support_max_spin.setRange(3, 10)
        self.support_max_spin.setValue(5)
        search_row.addWidget(self.support_max_spin)

        hint = QLabel("Gợi ý: 80/30/5 là cân bằng. 150/50/7 sẽ rà sâu hơn nhưng chậm hơn.")
        hint.setStyleSheet("color: #5E7184;")
        search_row.addWidget(hint, 1)
        layout.addLayout(search_row)

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
        self.result_text.setPlaceholderText("Kết quả tính thử và Top kỳ tiếp theo sẽ hiển thị tại đây.")
        layout.addWidget(self.result_text, 1)

    def load_draws(self) -> list[Draw]:
        with self.database.session() as session:
            return DrawRepository(session).list_chronological()

    def data_status(self, draws: list[Draw] | None = None) -> tuple[str, str, int, str]:
        current_draws = draws if draws is not None else self.load_draws()
        if not current_draws:
            return "Chưa có dữ liệu", "-", 0, "Chưa xác định"
        first = current_draws[0].draw_date.strftime("%d/%m/%Y")
        latest = current_draws[-1].draw_date.strftime("%d/%m/%Y")
        next_date = next_auto_draw_date(current_draws).strftime("%d/%m/%Y")
        return first, latest, len(current_draws), next_date

    def refresh_data_status(self) -> None:
        first, latest, total, next_date = self.data_status()
        if total <= 0:
            self.data_status_label.setText(
                "Dữ liệu hiện tại: chưa có kỳ nào. Hãy nhập dữ liệu lịch sử trước."
            )
            return
        self.data_status_label.setText(
            f"Dữ liệu hiện tại: {total} kỳ · từ {first} đến {latest} · "
            f"dãy mới bạn nhập sẽ được lưu là kỳ tiếp theo: {next_date}"
        )

    def preview_from_target(self) -> None:
        """Fit methods against the typed row without saving anything."""
        try:
            target_values = parse_target_numbers(self.target_input.text())
            draws_before = self.load_draws()
            if len(draws_before) < 30:
                QMessageBox.information(
                    self,
                    "Chưa đủ dữ liệu",
                    "Cần có ít nhất khoảng 30 kỳ lịch sử để học phương pháp.",
                )
                return

            self.preview_button.setEnabled(False)
            self.commit_button.setEnabled(False)
            self.result_text.setPlainText(
                "Đang tính thử nhiều cách và tổ hợp phương pháp...\n"
                "Bước này KHÔNG lưu dãy vào database.\n"
                f"Đang yêu cầu {self.method_count_spin.value()} phương pháp, "
                f"tổ hợp từ top {self.ensemble_pool_spin.value()}, "
                f"support 1→{self.support_max_spin.value()}."
            )
            QApplication.processEvents()

            auto_date = next_auto_draw_date(draws_before)
            hypothetical_draw = build_target_draw(auto_date, target_values)
            hypothetical_draws = list(draws_before) + [hypothetical_draw]

            self.learned_methods = self.engine.learn_methods(
                draws_before,
                target_values,
                top_k=self.top_spin.value(),
                max_lag=self.lag_spin.value(),
                support_values=tuple(range(1, self.support_max_spin.value() + 1)),
                strategy_mode="full",
                limit=self.method_count_spin.value(),
                ensemble_pool=self.ensemble_pool_spin.value(),
            )
            if not self.learned_methods:
                self.pending_target_values = None
                self.pending_draw_date = None
                self.pending_draws_for_next = []
                QMessageBox.information(
                    self,
                    "Chưa tìm được phương pháp",
                    "Không tìm được phương pháp đủ dữ liệu để hiển thị.",
                )
                return

            self.pending_target_values = target_values
            self.pending_draw_date = auto_date
            self.pending_draws_for_next = hypothetical_draws
            self.next_signal_values = self.engine.combined_signal_values(
                hypothetical_draws,
                self.learned_methods,
                top_k=self.top_spin.value(),
            )

            self.fill_table(hypothetical_draws)
            self.commit_button.setEnabled(True)
            first, latest, total, next_date_label = self.data_status(draws_before)
            self.result_text.setPlainText(
                self.format_preview_result(
                    target_values=target_values,
                    first_before=first,
                    latest_before=latest,
                    total_before=total,
                    pending_date=auto_date.strftime("%d/%m/%Y"),
                    next_after=next_auto_draw_date(hypothetical_draws).strftime("%d/%m/%Y"),
                )
            )
        except Exception as exc:
            QMessageBox.critical(self, "Không thể tính thử", str(exc))
        finally:
            self.preview_button.setEnabled(True)

    def commit_pending_learning(self) -> None:
        """Persist the previewed methods and save the target row only after confirmation."""
        if not self.learned_methods or self.pending_target_values is None or self.pending_draw_date is None:
            QMessageBox.information(
                self,
                "Chưa có kết quả tính thử",
                "Hãy bấm 'Tính thử / Tính lại' trước, sau đó mới lưu.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Xác nhận lưu",
            (
                "Bạn có chắc muốn lưu bộ phương pháp này và cập nhật dãy vừa nhập vào dữ liệu lịch sử không?\n\n"
                "Nếu chưa hài lòng, hãy bấm 'Tính thử / Tính lại' thay vì lưu."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            draws_before = self.load_draws()
            first_before, latest_before, total_before, _next_before = self.data_status(draws_before)
            target_values = self.pending_target_values
            stored_date = self.pending_draw_date

            already_latest = bool(draws_before) and tuple(draws_before[-1].numbers) == target_values
            saved_path = self.store.save(self.learned_methods)
            created = False

            if already_latest:
                draws_after = draws_before
                stored_date = draws_before[-1].draw_date
            else:
                draw = build_target_draw(stored_date, target_values)
                with self.database.session() as session:
                    _, created = DrawRepository(session).upsert(draw)
                draws_after = self.load_draws()

            _methods, self.next_signal_values = learned_method_signal_values(
                draws_after,
                store=self.store,
                engine=self.engine,
                top_k=self.top_spin.value(),
            )
            _first_after, latest_after, total_after, next_after = self.data_status(draws_after)
            self.fill_table(draws_after)
            self.refresh_data_status()
            self.refresh_saved_label()
            self.commit_button.setEnabled(False)
            self.result_text.setPlainText(
                self.format_saved_result(
                    target_values=target_values,
                    saved_path=str(saved_path),
                    first_before=first_before,
                    latest_before=latest_before,
                    total_before=total_before,
                    stored_date=stored_date.strftime("%d/%m/%Y"),
                    created=created,
                    already_latest=already_latest,
                    latest_after=latest_after,
                    total_after=total_after,
                    next_after=next_after,
                )
            )
            QMessageBox.information(
                self,
                "Hoàn tất",
                "Đã lưu phương pháp và cập nhật dữ liệu an toàn.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Không thể lưu", str(exc))

    def apply_learned_methods(self) -> None:
        try:
            draws = self.load_draws()
            self.learned_methods = list(self.store.load())
            if not self.learned_methods:
                QMessageBox.information(
                    self,
                    "Chưa có phương pháp",
                    "Hãy nhập dãy số mới để tool học phương pháp trước.",
                )
                return
            self.next_signal_values = self.engine.combined_signal_values(
                draws,
                self.learned_methods,
                top_k=self.top_spin.value(),
            )
            first, latest, total, next_date = self.data_status(draws)
            self.fill_table(draws)
            self.result_text.setPlainText(
                "ÁP DỤNG BỘ PHƯƠNG PHÁP ĐÃ HỌC\n"
                f"Dữ liệu đang dùng: {total} kỳ · từ {first} đến {latest}\n"
                f"Kỳ tiếp theo tham chiếu: {next_date}\n"
                f"Số phương pháp đang dùng: {len(self.learned_methods)}\n"
                f"Top tín hiệu tham chiếu kỳ tiếp theo:\n{self.format_values(self.next_signal_values)}\n\n"
                "Đây là tín hiệu thống kê từ lịch sử và các phương pháp đã fit dãy đã biết, không phải cam kết tương lai."
            )
        except Exception as exc:
            QMessageBox.critical(self, "Không thể áp dụng phương pháp đã học", str(exc))

    def fill_table(self, draws: list[Draw] | None = None) -> None:
        current_draws = draws if draws is not None else self.load_draws()
        self.table.setRowCount(len(self.learned_methods))
        for row_index, method in enumerate(self.learned_methods):
            next_values = self.engine.signal_values_from_method(
                current_draws,
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

    def format_preview_result(
        self,
        *,
        target_values: tuple[int, ...],
        first_before: str,
        latest_before: str,
        total_before: int,
        pending_date: str,
        next_after: str,
    ) -> str:
        best = self.learned_methods[0] if self.learned_methods else None
        lines = [
            "================ TÍNH THỬ - CHƯA LƯU ================",
            f"Dữ liệu hiện tại: {total_before} kỳ · từ {first_before} đến {latest_before}",
            f"Dãy số đang fit thử: {self.format_values(target_values)}",
            f"Số phương pháp đã tìm thấy: {len(self.learned_methods)}",
            f"Thiết lập rà: Top {self.top_spin.value()} · Lag tối đa {self.lag_spin.value()} · "
            f"Support 1→{self.support_max_spin.value()} · Tổ hợp từ top {self.ensemble_pool_spin.value()}",
            f"Nếu lưu, dãy này sẽ được ghi là kỳ: {pending_date}",
            f"Kỳ tiếp theo tham chiếu sau khi lưu sẽ là: {next_after}",
            "Trạng thái: CHƯA ghi database, CHƯA thay đổi dữ liệu lịch sử.",
            "",
        ]
        if best is not None:
            lines.extend(
                [
                    "PHƯƠNG PHÁP KHỚP TỐT NHẤT TRONG LẦN TÍNH THỬ",
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
                "TOP TÍN HIỆU THAM CHIẾU KỲ TIẾP THEO NẾU BẠN LƯU DÃY NÀY",
                self.format_values(self.next_signal_values),
                "",
                "Nếu chưa hài lòng, hãy tăng số phương pháp cần tìm, tăng tổ hợp từ top, tăng support/lag hoặc bấm lại 'Tính thử / Tính lại'. Chỉ bấm lưu khi bạn muốn đưa dãy này vào lịch sử.",
            ]
        )
        return "\n".join(lines)

    def format_saved_result(
        self,
        *,
        target_values: tuple[int, ...],
        saved_path: str,
        first_before: str,
        latest_before: str,
        total_before: int,
        stored_date: str,
        created: bool,
        already_latest: bool,
        latest_after: str,
        total_after: int,
        next_after: str,
    ) -> str:
        best = self.learned_methods[0] if self.learned_methods else None
        save_note = "không lưu lặp vì dãy này đã là kỳ mới nhất" if already_latest else ("thêm mới" if created else "cập nhật")
        lines = [
            "================ ĐÃ LƯU TARGET LEARNING ================",
            f"Dữ liệu trước khi lưu: {total_before} kỳ · từ {first_before} đến {latest_before}",
            f"Dãy số đã nhập: {self.format_values(target_values)}",
            f"Ngày lưu vào lịch sử: {stored_date} ({save_note})",
            f"Dữ liệu sau khi lưu: {total_after} kỳ · cập nhật đến {latest_after}",
            f"Kỳ tiếp theo tham chiếu: {next_after}",
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
