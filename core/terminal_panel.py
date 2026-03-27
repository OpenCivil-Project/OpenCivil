"""
core/terminal_panel.py

Embedded terminal panel for OpenCivil — VSCode-style bottom panel.

Usage in main.py:
    from core.terminal_panel import TerminalPanel

    # create once, pass the live model and a refresh callback
    self.terminal_panel = TerminalPanel(
        model=self.model,
        on_model_modified=self.refresh_canvas,
        parent=self
    )

    # toggle visibility from a menu/button
    self.terminal_panel.toggle()

    # when the user opens a new model, swap the model reference
    self.terminal_panel.set_model(self.model)
"""

import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QLabel, QPushButton,
    QSizePolicy, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QTextCursor, QFont, QColor, QPalette, QKeyEvent

from core.cli import CLIDispatcher

class _StreamRedirect(QObject):
    """
    Drop-in replacement for sys.stdout / sys.stderr.
    Anything written to it is emitted as a Qt signal so the terminal
    widget can append it safely from any thread context.
    """
    text_written = pyqtSignal(str)

    def write(self, text: str):
        if text:
            self.text_written.emit(text)

    def flush(self):
        pass                                       

class TerminalPanel(QWidget):
    """
    Self-contained terminal panel.  Captures all stdout/stderr while open
    and routes it into a QTextEdit output area.  User types commands into a
    QLineEdit; each command is dispatched through CLIDispatcher.

    The widget is hidden by default.  Call toggle() or show()/hide().
    Closing (X button) hides — does NOT destroy — the widget or dispatcher.
    """

    def __init__(self, model, on_model_modified=None, on_file_opened=None, 
             on_model_saved=None, on_solve_requested=None, on_unlock=None, parent=None):

        super().__init__(parent)

        self._on_model_modified = on_model_modified
        self._on_file_opened    = on_file_opened           
        self._on_unlock         = on_unlock                
        self._on_solve_requested = on_solve_requested         
        self._on_model_saved    = on_model_saved           
        self._dispatcher        = CLIDispatcher(model)
        self._history           = []   
        self._history_index     = -1   

        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._redirect        = _StreamRedirect()
        self._redirect.text_written.connect(self._append_output)

        sys.stdout = self._redirect
        sys.stderr = self._redirect

        self._build_ui()
        self.hide()

    def set_model(self, model):
        """Call this whenever the GUI opens a new model file."""
        self._dispatcher = CLIDispatcher(model)
        self._append_output("--- Model updated in terminal ---\n")

    def toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self._input.setFocus()

    def _build_ui(self):
        self.setMinimumHeight(120)
        self.setMaximumHeight(600)
        self.resize(self.width(), 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        title_bar = QWidget()
        title_bar.setFixedHeight(28)
        title_bar.setStyleSheet("background-color: #1a1a1a; border-top: 1px solid #3a3a3a;")

        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(10, 0, 6, 0)
        tb_layout.setSpacing(6)

        lbl = QLabel("TERMINAL")
        lbl.setStyleSheet("color: #aaaaaa; font-family: 'Segoe UI'; font-size: 11px; font-weight: 600;")
        tb_layout.addWidget(lbl)
        tb_layout.addStretch()

        clear_btn = QPushButton("⊘")
        clear_btn.setToolTip("Clear output")
        clear_btn.setFixedSize(22, 22)
        clear_btn.setStyleSheet(_icon_btn_style())
        clear_btn.clicked.connect(self._clear_output)
        tb_layout.addWidget(clear_btn)

        close_btn = QPushButton("✕")
        close_btn.setToolTip("Hide terminal  (reopen from Options menu)")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet(_icon_btn_style())
        close_btn.clicked.connect(self.hide)
        tb_layout.addWidget(close_btn)

        root.addWidget(title_bar)

        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setFont(QFont("Consolas", 10))
        self._output.setStyleSheet("""
            QTextEdit {
                background-color: #0d0d0d;
                color: #d4d4d4;
                border: none;
                padding: 6px 10px;
                selection-background-color: #264f78;
            }
            QScrollBar:vertical {
                background: #1a1a1a;
                width: 8px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: #424242;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #686868; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        self._output.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._output)

        input_row = QWidget()
        input_row.setFixedHeight(32)
        input_row.setStyleSheet("background-color: #0d0d0d; border-top: 1px solid #2a2a2a;")

        ir_layout = QHBoxLayout(input_row)
        ir_layout.setContentsMargins(10, 0, 10, 0)
        ir_layout.setSpacing(6)

        prompt = QLabel("OC>")
        prompt.setFont(QFont("Consolas", 10))
        prompt.setStyleSheet("color: #4ec9b0; background: transparent;")
        ir_layout.addWidget(prompt)

        self._input = QLineEdit()
        self._input.setFont(QFont("Consolas", 10))
        self._input.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                color: #d4d4d4;
                border: none;
                selection-background-color: #264f78;
            }
        """)
        self._input.setPlaceholderText("type a command…  ('help' for reference) ('clear' to clear terminal)")
        self._input.returnPressed.connect(self._on_enter)
        self._input.installEventFilter(self)                              
        ir_layout.addWidget(self._input)

        root.addWidget(input_row)

        self._append_output(
            "="*65 + "\n"
            " OpenCivil Terminal  —  type {'help' for command reference} and {'clear' to clear the terminal}\n"
            "="*65 + "\n"
        )

    def showEvent(self, event):
        sys.stderr = self._redirect
        super().showEvent(event)

    def hideEvent(self, event):
        sys.stderr = self._original_stderr
        super().hideEvent(event)

    def _on_enter(self):
        raw = self._input.text().strip()
        self._input.clear()
        if not raw:
            return

        if not self._history or self._history[-1] != raw:
            self._history.append(raw)
        self._history_index = -1

        self._append_output(f"\nOC> {raw}\n", color="#4ec9b0")

        result = self._dispatcher.dispatch(raw)

        if result == "exit":
            self.hide()
        elif result == "clear":
            self._clear_output()
        elif result == "unlock":
            if self._on_unlock:
                self._on_unlock()
        elif result == "opened":
                                                                                     
            if self._on_file_opened:
                self._on_file_opened(self._dispatcher.model)
        elif result and result.startswith("solve:"):
            case_name = result.split(":", 1)[1]
            if self._on_solve_requested:
                self._on_solve_requested(case_name)
        elif result == "saved":
            if self._on_model_saved:
                self._on_model_saved(self._dispatcher.model)
        elif result == "modified" and self._on_model_modified:
            self._on_model_modified()
            
    def _append_output(self, text: str, color: str = "#d4d4d4"):
        cursor = self._output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = cursor.charFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(text)

        self._output.setTextCursor(cursor)
        self._output.ensureCursorVisible()

    def _clear_output(self):
        self._output.clear()

    def eventFilter(self, obj, event):
        if obj is self._input and isinstance(event, QKeyEvent):
            if event.key() == Qt.Key.Key_Up:
                self._history_navigate(-1)
                return True
            elif event.key() == Qt.Key.Key_Down:
                self._history_navigate(1)
                return True
        return super().eventFilter(obj, event)

    def _history_navigate(self, direction: int):
        if not self._history:
            return
        if self._history_index == -1:
            self._history_index = len(self._history)
        self._history_index = max(0, min(len(self._history) - 1,
                                         self._history_index + direction))
        self._input.setText(self._history[self._history_index])
        self._input.end(False)

def _icon_btn_style():
    return """
        QPushButton {
            background: transparent;
            color: #888888;
            border: none;
            font-size: 13px;
            border-radius: 3px;
        }
        QPushButton:hover {
            background-color: #3a3a3a;
            color: #cccccc;
        }
        QPushButton:pressed {
            background-color: #4a4a4a;
        }
    """
