from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                             QCheckBox, QPushButton, QGroupBox, QGridLayout,
                             QMessageBox, QLabel, QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, QRect, QPoint, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QPolygon
from app.commands import CmdAssignRestraints

class SupportCard(QFrame):
    """
    Clickable card that draws a structural support diagram via QPainter.
    support_type: "fixed" | "pinned" | "roller" | "free"
    """

    HATCH_COLOR   = QColor("#555555")
    GROUND_COLOR  = QColor("#888888")
    MEMBER_COLOR  = QColor("#1565C0")
    WHEEL_COLOR   = QColor("#444444")
    SELECT_COLOR  = QColor("#1976D2")
    BG_NORMAL     = QColor("#F5F5F5")
    BG_HOVER      = QColor("#E3F2FD")
    BG_SELECTED   = QColor("#BBDEFB")

    def __init__(self, support_type: str, label: str, parent=None):
        super().__init__(parent)
        self.support_type = support_type
        self.label        = label
        self.selected     = False
        self._hovered     = False

        self.setFixedSize(90, 100)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"Fast assign: {label}")

    def set_selected(self, val: bool):
        self.selected = val
        self.update()

    def enterEvent(self, e):
        self._hovered = True
        self.update()

    def leaveEvent(self, e):
        self._hovered = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.parent().parent()._card_clicked(self.support_type)              

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        if self.selected:
            bg = self.BG_SELECTED
            border = self.SELECT_COLOR
            bw = 2
        elif self._hovered:
            bg = self.BG_HOVER
            border = QColor("#90CAF9")
            bw = 1
        else:
            bg = self.BG_NORMAL
            border = QColor("#CCCCCC")
            bw = 1

        p.setBrush(QBrush(bg))
        p.setPen(QPen(border, bw))
        p.drawRoundedRect(2, 2, w - 4, h - 4, 6, 6)

        self._draw_support(p, w, 70)

        lbl_y = 72
        if self.selected:
            p.setPen(QPen(self.SELECT_COLOR))
            font = QFont()
            font.setBold(True)
            font.setPointSize(8)
        else:
            p.setPen(QPen(QColor("#333333")))
            font = QFont()
            font.setPointSize(8)
        p.setFont(font)
        p.drawText(QRect(0, lbl_y, w, h - lbl_y - 2),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                   self.label)

        p.end()

    def _draw_support(self, p: QPainter, card_w: int, diagram_h: int):
        """Route to the correct diagram drawing method."""
        cx = card_w // 2                                     
        node_y = 18                                           

        support_y = diagram_h - 22                                               

        p.setPen(QPen(self.MEMBER_COLOR, 3, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.drawLine(cx, node_y, cx, support_y)

        if self.support_type != "fixed":
            p.setBrush(QBrush(self.MEMBER_COLOR))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(cx - 4, node_y - 4, 8, 8)

        if self.support_type == "fixed":
            self._draw_fixed(p, cx, support_y, diagram_h)
        elif self.support_type == "pinned":
            self._draw_pinned(p, cx, support_y, diagram_h)
        elif self.support_type == "roller":
            self._draw_roller(p, cx, support_y, diagram_h)
        elif self.support_type == "free":
            self._draw_free(p, cx, node_y)

    def _draw_fixed(self, p, cx, tip_y, diagram_h):
        """Thick horizontal bar + diagonal ticks — all 6 DOFs fixed."""
        half = 14

        p.setPen(QPen(self.HATCH_COLOR, 3, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.drawLine(cx - half, tip_y, cx + half, tip_y)

        p.setPen(QPen(self.GROUND_COLOR, 1))
        for i in range(5):
            x = cx - half + 2 + i * 7
            p.drawLine(x, tip_y, x - 5, tip_y + 7)

    def _draw_pinned(self, p, cx, tip_y, diagram_h):
        """Triangle + ground line + hatching."""
        half = 12
        tri = QPolygon([
            QPoint(cx,          tip_y),
            QPoint(cx - half,   tip_y + half * 2),
            QPoint(cx + half,   tip_y + half * 2),
        ])
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(self.HATCH_COLOR, 2))
        p.drawPolygon(tri)

        ground_y = tip_y + half * 2
        p.drawLine(cx - half - 4, ground_y, cx + half + 4, ground_y)

        p.setPen(QPen(self.GROUND_COLOR, 1))
        for i in range(5):
            x = cx - half - 2 + i * 7
            p.drawLine(x, ground_y, x - 5, ground_y + 6)

    def _draw_roller(self, p, cx, tip_y, diagram_h):
        """Triangle + two circles (wheels) + ground line."""
        half = 12
        tri = QPolygon([
            QPoint(cx,          tip_y),
            QPoint(cx - half,   tip_y + half * 2),
            QPoint(cx + half,   tip_y + half * 2),
        ])
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(self.HATCH_COLOR, 2))
        p.drawPolygon(tri)

        wheel_y  = tip_y + half * 2 + 1
        r        = 4
        p.setBrush(QBrush(self.WHEEL_COLOR))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx - half + 2,     wheel_y, r * 2, r * 2)
        p.drawEllipse(cx + half - r * 2 - 2, wheel_y, r * 2, r * 2)

        ground_y = wheel_y + r * 2 + 1
        p.setPen(QPen(self.GROUND_COLOR, 1))
        p.drawLine(cx - half - 4, ground_y, cx + half + 4, ground_y)

    def _draw_free(self, p, cx, node_y):
        """Just an arrow indicating freedom — no constraint symbol."""
                                                               
        p.setPen(QPen(QColor("#888888"), 1, Qt.PenStyle.DashLine))
                                  
        ay = node_y + 20
        p.drawLine(cx - 14, ay, cx + 14, ay)
        p.setPen(QPen(QColor("#888888"), 1))
                     
        p.drawLine(cx + 14, ay, cx + 9,  ay - 4)
        p.drawLine(cx + 14, ay, cx + 9,  ay + 4)
        p.drawLine(cx - 14, ay, cx - 9,  ay - 4)
        p.drawLine(cx - 14, ay, cx - 9,  ay + 4)

class RestraintDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window

        self.setWindowTitle("Assign Joint Restraints")
        self.setFixedSize(400, 340)
        self.setModal(False)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        fast_group = QGroupBox("Fast Assign")
        fast_layout = QHBoxLayout(fast_group)
        fast_layout.setSpacing(8)
        fast_layout.setContentsMargins(8, 12, 8, 8)

        self._cards: dict[str, SupportCard] = {}
        for key, lbl in [("fixed", "Fixed"), ("pinned", "Pinned"),
                          ("roller", "Roller"), ("free", "Free")]:
            card = SupportCard(key, lbl, parent=fast_group)
            self._cards[key] = card
            fast_layout.addWidget(card)

        root.addWidget(fast_group)

        dof_group = QGroupBox("Restraints in Global Directions")
        dof_layout = QGridLayout(dof_group)
        dof_layout.setVerticalSpacing(6)
        dof_layout.setHorizontalSpacing(20)

        self.cb_tx = QCheckBox("Translation X (U1)")
        self.cb_ty = QCheckBox("Translation Y (U2)")
        self.cb_tz = QCheckBox("Translation Z (U3)")
        self.cb_rx = QCheckBox("Rotation X (R1)")
        self.cb_ry = QCheckBox("Rotation Y (R2)")
        self.cb_rz = QCheckBox("Rotation Z (R3)")

        dof_layout.addWidget(self.cb_tx, 0, 0)
        dof_layout.addWidget(self.cb_ty, 1, 0)
        dof_layout.addWidget(self.cb_tz, 2, 0)
        dof_layout.addWidget(self.cb_rx, 0, 1)
        dof_layout.addWidget(self.cb_ry, 1, 1)
        dof_layout.addWidget(self.cb_rz, 2, 1)

        for cb in (self.cb_tx, self.cb_ty, self.cb_tz,
                   self.cb_rx, self.cb_ry, self.cb_rz):
            cb.stateChanged.connect(self._deselect_cards)

        root.addWidget(dof_group)

        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        self.btn_apply = QPushButton("Apply")
        self.btn_apply.setFixedHeight(30)
        self.btn_apply.clicked.connect(self.apply_changes)

        self.btn_close = QPushButton("Close")
        self.btn_close.setFixedHeight(30)
        self.btn_close.clicked.connect(self.close)

        action_layout.addWidget(self.btn_apply)
        action_layout.addWidget(self.btn_close)
        root.addLayout(action_layout)

    def _card_clicked(self, support_type: str):
        """Called by a SupportCard when clicked."""
        for key, card in self._cards.items():
            card.set_selected(key == support_type)
        self._apply_fast(support_type)

    def _deselect_cards(self):
        for card in self._cards.values():
            card.set_selected(False)

    def _apply_fast(self, r_type: str):
        """Set checkboxes according to support type without triggering card deselect."""
                                                                   
        boxes = (self.cb_tx, self.cb_ty, self.cb_tz,
                 self.cb_rx, self.cb_ry, self.cb_rz)
        for cb in boxes:
            cb.blockSignals(True)

        self.cb_tx.setChecked(False); self.cb_ty.setChecked(False)
        self.cb_tz.setChecked(False); self.cb_rx.setChecked(False)
        self.cb_ry.setChecked(False); self.cb_rz.setChecked(False)

        if r_type == "fixed":
            for cb in boxes:
                cb.setChecked(True)
        elif r_type == "pinned":
            self.cb_tx.setChecked(True)
            self.cb_ty.setChecked(True)
            self.cb_tz.setChecked(True)
        elif r_type == "roller":
            self.cb_tz.setChecked(True)
        elif r_type == "free":
            pass

        for cb in boxes:
            cb.blockSignals(False)

    def apply_changes(self):
        selected_nodes = self.main_window.selected_node_ids

        if not selected_nodes:
            QMessageBox.warning(self, "Selection Error",
                                "Please select at least one Joint to assign restraints.")
            return

        restraints = [
            self.cb_tx.isChecked(), self.cb_ty.isChecked(), self.cb_tz.isChecked(),
            self.cb_rx.isChecked(), self.cb_ry.isChecked(), self.cb_rz.isChecked(),
        ]

        cmd = CmdAssignRestraints(
            self.main_window.model,
            self.main_window,
            list(selected_nodes),
            restraints,
        )
        self.main_window.add_command(cmd)
        self.main_window.status.showMessage(
            f"Assigned Restraints to {len(selected_nodes)} Joints."
        )
