# gitbuddy_merge_tab.py

import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt

class MergeTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_selected_repo_path = ""
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        self.repo_path_label = QLabel("Selected Repository: N/A")
        self.repo_path_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self.repo_path_label)

        label = QLabel("Merge functionality will be implemented here.")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        layout.addStretch(1)

    def set_selected_repo_path(self, path):
        """Called by GitBuddyApp to update the selected repository path."""
        self.current_selected_repo_path = path
        if path and os.path.isdir(os.path.join(path, ".git")):
            self.repo_path_label.setText(f"Selected Repository: {path}")
        else:
            self.repo_path_label.setText("Selected Repository: N/A (Not a Git Repo or No Selection)")

