# gitbuddy_git_graph_widget.py

from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPalette, QColor, QPainter, QPen, QBrush, QFontMetrics

class GitGraphWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.commits_data = []
        self.commit_positions = {}
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Drawing parameters
        self.COMMIT_RADIUS = 5
        self.COMMIT_SPACING_Y = 30
        self.LANE_SPACING_X = 20
        self.TEXT_OFFSET_X = 15

    def set_commits_data(self, data):
        """Sets the commit data to be visualized."""
        self.commits_data = data
        self.update_commit_positions()
        self.update()

    def update_commit_positions(self):
        """Calculates the drawing positions for each commit."""
        self.commit_positions = {}
        if not self.commits_data:
            self.setMinimumHeight(50) # Smaller height when no data
            self.setMaximumHeight(50)
            return

        y_pos = self.COMMIT_SPACING_Y / 2
        for i, commit in enumerate(self.commits_data):
            commit['lane'] = 0
            x_pos = self.LANE_SPACING_X
            self.commit_positions[commit['hash']] = QPointF(x_pos, y_pos)
            y_pos += self.COMMIT_SPACING_Y
        
        self.setMinimumHeight(int(y_pos))
        self.setMaximumHeight(int(y_pos))

    def paintEvent(self, event):
        """Draws the Git graph."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if not self.commits_data:
            painter.drawText(self.rect(), Qt.AlignCenter, "No Git history to display.")
            return

        palette = self.palette()
        text_color = palette.color(QPalette.WindowText)
        line_color = palette.color(QPalette.Mid)
        commit_dot_color = palette.color(QPalette.Highlight)

        painter.setPen(QPen(line_color, 1))
        painter.setBrush(QBrush(commit_dot_color))

        for i, commit in enumerate(self.commits_data):
            commit_hash = commit['hash']
            commit_message = commit['message']
            commit_pos = self.commit_positions.get(commit_hash)

            if not commit_pos:
                continue

            painter.drawEllipse(commit_pos, self.COMMIT_RADIUS, self.COMMIT_RADIUS)

            painter.setPen(QPen(text_color))
            text_rect = QRectF(commit_pos.x() + self.COMMIT_RADIUS + self.TEXT_OFFSET_X,
                               commit_pos.y() - self.COMMIT_SPACING_Y / 2,
                               self.width() - (commit_pos.x() + self.COMMIT_RADIUS + self.TEXT_OFFSET_X) - 10,
                               self.COMMIT_SPACING_Y)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, f"{commit_hash[:7]} {commit_message}")

            painter.setPen(QPen(line_color, 1))
            for parent_hash in commit['parents']:
                parent_pos = self.commit_positions.get(parent_hash)
                if parent_pos:
                    start_point = commit_pos
                    end_point = parent_pos
                    painter.drawLine(start_point, end_point)
