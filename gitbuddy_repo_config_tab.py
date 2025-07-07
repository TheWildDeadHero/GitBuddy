# gitbuddy_repo_config_tab.py

import sys
import json
import os
import subprocess
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QLineEdit, QLabel, QFrame, QCheckBox, QSpinBox, QGroupBox
)
from PySide6.QtCore import Qt, QDir, Signal

class RepoConfigTab(QWidget):
    # Define a signal that will be emitted when the repository configuration changes
    # This signal will carry the updated list of repositories
    repo_config_changed = Signal(list)

    def __init__(self, initial_repositories_data, parent=None):
        super().__init__(parent)
        # Receive initial data from GitBuddyApp
        self.repositories_data = list(initial_repositories_data) # Make a mutable copy

        self.current_selected_repo_path = "" # To store the path from the global selector

        self.init_ui()
        self.load_repositories_to_list() # Populate list with initial data

    def init_ui(self):
        """Initializes the user interface elements for the Repo Config Tab."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Selected Repository Path Display
        repo_path_display_layout = QHBoxLayout()
        repo_path_display_layout.addWidget(QLabel("Currently Selected Repository:"))
        self.selected_repo_display_input = QLineEdit()
        self.selected_repo_display_input.setPlaceholderText("Path from global selector will appear here...")
        self.selected_repo_display_input.setReadOnly(True)
        repo_path_display_layout.addWidget(self.selected_repo_display_input)
        layout.addLayout(repo_path_display_layout)

        # List Widget to display repositories
        layout.addWidget(QLabel("Configured Git Repositories:"))
        self.repo_list_widget = QListWidget()
        self.repo_list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.repo_list_widget.itemSelectionChanged.connect(self.load_selected_repository_details)
        layout.addWidget(self.repo_list_widget)

        # Repository Details/Add/Edit Form
        details_group_box = QGroupBox("Repository Details")
        details_layout = QVBoxLayout(details_group_box)

        # Path
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Path:"))
        self.repo_path_input = QLineEdit()
        self.repo_path_input.setPlaceholderText("Enter Git repository path or browse...")
        path_layout.addWidget(self.repo_path_input)
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.browse_for_repository)
        path_layout.addWidget(self.browse_button)
        details_layout.addLayout(path_layout)

        # Pull Interval
        pull_interval_layout = QHBoxLayout()
        pull_interval_layout.addWidget(QLabel("Pull Interval (seconds):"))
        self.pull_interval_spinbox = QSpinBox()
        self.pull_interval_spinbox.setRange(30, 86400) # 30 seconds to 24 hours
        self.pull_interval_spinbox.setValue(300) # Default 5 minutes
        pull_interval_layout.addWidget(self.pull_interval_spinbox)
        pull_interval_layout.addStretch(1)
        details_layout.addLayout(pull_interval_layout)

        # Auto Commit
        self.auto_commit_checkbox = QCheckBox("Enable Auto Commit")
        self.auto_commit_checkbox.stateChanged.connect(self.toggle_commit_fields)
        details_layout.addWidget(self.auto_commit_checkbox)

        commit_msg_layout = QHBoxLayout()
        commit_msg_layout.addWidget(QLabel("Commit Message Template:"))
        self.commit_message_input = QLineEdit()
        self.commit_message_input.setPlaceholderText("e.g., Auto-commit: {timestamp}")
        self.commit_message_input.setText("Auto-commit from GitBuddy: {timestamp}") # Updated default commit message
        commit_msg_layout.addWidget(self.commit_message_input)
        details_layout.addLayout(commit_msg_layout)

        # Auto Push
        self.auto_push_checkbox = QCheckBox("Enable Auto Push")
        self.auto_push_checkbox.stateChanged.connect(self.toggle_push_fields)
        details_layout.addWidget(self.auto_push_checkbox)

        push_interval_layout = QHBoxLayout()
        push_interval_layout.addWidget(QLabel("Push Interval (seconds):"))
        self.push_interval_spinbox = QSpinBox()
        self.push_interval_spinbox.setRange(60, 86400 * 7) # 1 minute to 7 days
        self.push_interval_spinbox.setValue(3600) # Default 1 hour
        push_interval_layout.addWidget(self.push_interval_spinbox)
        push_interval_layout.addStretch(1)
        details_layout.addLayout(push_interval_layout)

        # Form action buttons
        form_buttons_layout = QHBoxLayout()
        self.add_update_button = QPushButton("Add Repository")
        self.add_update_button.clicked.connect(self.add_or_update_repository)
        form_buttons_layout.addWidget(self.add_update_button)

        self.clear_form_button = QPushButton("Clear Form")
        self.clear_form_button.clicked.connect(self.clear_form)
        form_buttons_layout.addWidget(self.clear_form_button)
        form_buttons_layout.addStretch(1)
        details_layout.addLayout(form_buttons_layout)

        layout.addWidget(details_group_box)

        # Global Action Buttons (Remove, Save)
        global_button_layout = QHBoxLayout()
        global_button_layout.addStretch(1) # Pushes buttons to the right

        remove_button = QPushButton("Remove Selected")
        remove_button.setObjectName("removeButton") # Set object name for specific styling
        remove_button.clicked.connect(self.remove_selected_repository)
        global_button_layout.addWidget(remove_button)

        # The "Save Configuration" button is removed as saving is handled by GitBuddyApp
        # save_button = QPushButton("Save Configuration")
        # save_button.clicked.connect(self.save_configuration)
        # global_button_layout.addWidget(save_button)

        layout.addLayout(global_button_layout)
        layout.addStretch(1)

        # Initial state for commit/push fields
        self.toggle_commit_fields(self.auto_commit_checkbox.checkState())
        self.toggle_push_fields(self.auto_push_checkbox.checkState())
        self.clear_form() # Start with a clean form

    def set_selected_repo_path(self, path):
        """Called by GitBuddyApp to update the selected repository path."""
        self.current_selected_repo_path = path
        self.selected_repo_display_input.setText(path)

    def on_repo_data_updated(self, updated_repositories_data: list):
        """Slot to receive updated repository data from GitBuddyApp."""
        self.repositories_data = list(updated_repositories_data) # Update internal data
        self.load_repositories_to_list() # Reload the list widget

    def toggle_commit_fields(self, state):
        """Enables/disables commit-related fields based on auto_commit_checkbox state."""
        enabled = (state == Qt.Checked)
        self.commit_message_input.setEnabled(enabled)

    def toggle_push_fields(self, state):
        """Enables/disables push-related fields based on auto_push_checkbox state."""
        enabled = (state == Qt.Checked)
        self.push_interval_spinbox.setEnabled(enabled)

    def load_repositories_to_list(self):
        """Populates the QListWidget with data from self.repositories_data."""
        self.repo_list_widget.clear()
        for repo_data in self.repositories_data:
            self.repo_list_widget.addItem(repo_data['path'])

    def load_selected_repository_details(self):
        """Loads details of the selected repository into the form fields."""
        selected_items = self.repo_list_widget.selectedItems()
        if not selected_items:
            self.clear_form()
            self.add_update_button.setText("Add Repository")
            self.repo_path_input.setReadOnly(False) # Allow editing path for new entry
            return

        selected_path = selected_items[0].text()
        repo_data = next((r for r in self.repositories_data if r['path'] == selected_path), None)

        if repo_data:
            self.repo_path_input.setText(repo_data['path'])
            self.repo_path_input.setReadOnly(True) # Path is read-only when editing existing
            self.pull_interval_spinbox.setValue(repo_data.get('pull_interval', 300))
            self.auto_commit_checkbox.setChecked(repo_data.get('auto_commit', False))
            self.commit_message_input.setText(repo_data.get('commit_message_template', "Auto-commit from GitBuddy: {timestamp}"))
            self.auto_push_checkbox.setChecked(repo_data.get('auto_push', False))
            self.push_interval_spinbox.setValue(repo_data.get('push_interval', 3600))
            self.add_update_button.setText("Update Selected Repository")
        else:
            self.clear_form() # Should not happen if data is consistent
            self.add_update_button.setText("Add Repository")
            self.repo_path_input.setReadOnly(False)

    def clear_form(self):
        """Clears the repository details form."""
        self.repo_list_widget.clearSelection() # Deselect any item
        self.repo_path_input.clear()
        self.repo_path_input.setReadOnly(False)
        self.pull_interval_spinbox.setValue(300)
        self.auto_commit_checkbox.setChecked(False)
        self.commit_message_input.setText("Auto-commit from GitBuddy: {timestamp}")
        self.auto_push_checkbox.setChecked(False)
        self.push_interval_spinbox.setValue(3600)
        self.add_update_button.setText("Add Repository")

    def browse_for_repository(self):
        """Opens a file dialog to select a Git repository directory."""
        initial_path = self.repo_path_input.text() if self.repo_path_input.text() else QDir.homePath()
        directory = QFileDialog.getExistingDirectory(self, "Select Git Repository Directory", initial_path)
        if directory:
            if os.path.isdir(os.path.join(directory, ".git")):
                self.repo_path_input.setText(directory)
            else:
                QMessageBox.warning(self, "Not a Git Repository",
                                    f"The selected directory '{directory}' does not appear to be a Git repository (missing .git folder).")
                self.repo_path_input.setText(directory)

    def add_or_update_repository(self):
        """Adds a new repository or updates an existing one based on form input."""
        repo_path = self.repo_path_input.text().strip()
        if not repo_path:
            QMessageBox.warning(self, "Input Error", "Please enter a repository path.")
            return

        normalized_path = os.path.abspath(os.path.expanduser(repo_path))

        if not os.path.isdir(normalized_path):
            QMessageBox.warning(self, "Invalid Path", f"The path '{normalized_path}' is not a valid directory.")
            return
        if not os.path.isdir(os.path.join(normalized_path, ".git")):
            QMessageBox.warning(self, "Not a Git Repository",
                                f"The directory '{normalized_path}' does not appear to be a Git repository (missing .git folder).")

        new_repo_data = {
            'path': normalized_path,
            'pull_interval': self.pull_interval_spinbox.value(),
            'auto_commit': self.auto_commit_checkbox.isChecked(),
            'commit_message_template': self.commit_message_input.text().strip(),
            'auto_push': self.auto_push_checkbox.isChecked(),
            'push_interval': self.push_interval_spinbox.value()
        }

        existing_index = -1
        for i, r in enumerate(self.repositories_data):
            if r['path'] == normalized_path:
                existing_index = i
                break

        if existing_index != -1:
            self.repositories_data[existing_index] = new_repo_data
        else:
            if any(r['path'] == normalized_path for r in self.repositories_data):
                QMessageBox.information(self, "Duplicate", "This repository is already in the list.")
                return

            self.repositories_data.append(new_repo_data)
        
        self.clear_form()
        self.repo_config_changed.emit(self.repositories_data) # Emit signal with updated data

    def remove_selected_repository(self):
        """Removes the selected repository from the list widget and data."""
        selected_items = self.repo_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select a repository to remove.")
            return

        reply = QMessageBox.question(self, "Confirm Removal",
                                     "Are you sure you want to remove the selected repository?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            selected_path = selected_items[0].text()
            self.repositories_data = [r for r in self.repositories_data if r['path'] != selected_path]
            
            self.clear_form()
            self.repo_config_changed.emit(self.repositories_data) # Emit signal with updated data
