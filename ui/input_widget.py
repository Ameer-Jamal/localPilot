from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFontMetricsF, QTextOption
from PySide6.QtWidgets import QTextEdit, QSizePolicy


class AutoResizingTextEdit(QTextEdit):
    """Plain-text multi-line input that grows/shrinks between min/max lines.
       Enter → newline; Cmd/Ctrl+Enter → send."""
    sendRequested = Signal()

    def __init__(self, parent=None, min_lines: int = 1, max_lines: int = 8):
        super().__init__(parent)
        self._min_lines = int(min_lines)
        self._max_lines = int(max_lines)
        self._pad = 8

        self.setAcceptRichText(False)
        self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QTextEdit.NoFrame)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setPlaceholderText("Ask a follow-up…  (Cmd/Ctrl+Enter to send; Enter for newline)")
        self.setStyleSheet("QTextEdit { background:#1b1e22; color:#e6e6e6; border-radius:6px; padding:6px; }")

        self.document().setDocumentMargin(2)
        self.document().setTextWidth(self.viewport().width())

        self.textChanged.connect(self._schedule_adjust)
        self.document().documentLayout().documentSizeChanged.connect(lambda *_: self._schedule_adjust())

        self._adjust_height()

    # shortcuts
    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and (e.modifiers() & (Qt.ControlModifier | Qt.MetaModifier)):
            e.accept()
            self.sendRequested.emit()
            return
        super().keyPressEvent(e)

    # sizing
    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.document().setTextWidth(self.viewport().width())
        self._schedule_adjust()

    def _schedule_adjust(self):
        QTimer.singleShot(0, self._adjust_height)

    def _line_h(self) -> float:
        return QFontMetricsF(self.font()).lineSpacing()

    def _adjust_height(self):
        doc_h = float(self.document().size().height())  # respects textWidth
        min_h = self._min_lines * self._line_h() + self._pad
        max_h = self._max_lines * self._line_h() + self._pad
        new_h = int(max(min_h, min(max_h, doc_h + self._pad)))
        self.setFixedHeight(new_h)
        self.updateGeometry()

    def reset_to_min(self):
        self.setFixedHeight(int(self._min_lines * self._line_h() + self._pad))
        self.updateGeometry()
