# gitbuddy_repo_config_tab.py

import json
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox, QLineEdit, QLabel, QCheckBox, QSpinBox, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, QDir, Signal

class RepoConfigTab(QWidget):
    # Signal to notify GitBuddyApp of config changes, passing the new list of repositories
    repo_config_changed = Signal(list) 

    def __init__(self, repositories_data_initial, parent=None): # Accept initial data
        super().__init__(parent)
        # The config_dir and config_file are now managed by GitBuddyApp,
        # this tab only operates on the data passed to it.
        # self.config_dir = config_dir # Removed
        # self.config_file = os.path.join(self.config_dir, "config.json") # Removed
        self.repositories_data = repositories_data_initial # Stores the full configuration for each repository
        self.current_selected_global_repo_path = "" # To store the path from the global selector
        self.current_selected_repo_index = -1 # Index of the currently selected repo in self.repositories_data

        self.init_ui()
        self.load_repositories_to_table() # Load initial data into table

    def init_ui(self):
        """Initializes the repository configurator tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # --- Top Action Buttons (Add, Remove) ---
        top_action_buttons_layout = QHBoxLayout()
        self.add_repository_button = QPushButton("Add New Repository")
        self.add_repository_button.clicked.connect(self.add_or_update_repository)
        top_action_buttons_layout.addWidget(self.add_repository_button)

        self.remove_repository_button = QPushButton("Remove Selected Repository")
        self.remove_repository_button.clicked.connect(self.remove_selected_repository)
        self.remove_repository_button.setEnabled(False) # Disabled by default
        top_action_buttons_layout.addWidget(self.remove_repository_button)
        top_action_buttons_layout.addStretch(1)
        layout.addLayout(top_action_buttons_layout)

        # --- Repository Table ---
        self.repo_table_widget = QTableWidget()
        self.repo_table_widget.setColumnCount(6) # Path, Pull, Commit, Commit Msg, Push, Push Interval
        self.repo_table_widget.setHorizontalHeaderLabels([
            "Path", "Auto Pull (sec)", "Auto Commit", "Commit Message", "Auto Push", "Push Interval (sec)"
        ])
        self.repo_table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch) # Path takes most space
        self.repo_table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.repo_table_widget.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.repo_table_widget.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.repo_table_widget.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.repo_table_widget.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        
        self.repo_table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.repo_table_widget.setSelectionMode(QTableWidget.SingleSelection)
        self.repo_table_widget.verticalHeader().setVisible(False) # Hide row numbers
        self.repo_table_widget.itemSelectionChanged.connect(self.load_selected_repository_details)
        layout.addWidget(self.repo_table_widget)

        # --- Repository Details Form ---
        details_group_box = QGroupBox("Selected Repository Details")
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

        # Auto Pull & Interval
        pull_layout = QHBoxLayout()
        self.auto_pull_checkbox = QCheckBox("Enable Auto Pull")
        self.auto_pull_checkbox.stateChanged.connect(self.toggle_pull_interval_field)
        pull_layout.addWidget(self.auto_pull_checkbox)

        pull_layout.addWidget(QLabel("Interval (sec):"))
        self.pull_interval_spinbox = QSpinBox()
        self.pull_interval_spinbox.setRange(1, 86400) # 1 second to 24 hours
        self.pull_interval_spinbox.setValue(300) # Default 300 seconds (5 minutes)
        pull_layout.addWidget(self.pull_interval_spinbox)
        pull_layout.addStretch(1)
        details_layout.addLayout(pull_layout)

        # Auto Commit & Message
        commit_layout = QHBoxLayout()
        self.auto_commit_checkbox = QCheckBox("Enable Auto Commit")
        self.auto_commit_checkbox.stateChanged.connect(self.toggle_commit_fields)
        commit_layout.addWidget(self.auto_commit_checkbox)
        commit_layout.addStretch(1)
        details_layout.addLayout(commit_layout)

        commit_msg_layout = QHBoxLayout()
        commit_msg_layout.addWidget(QLabel("Commit Message Template:"))
        self.commit_message_input = QLineEdit()
        self.commit_message_input.setPlaceholderText("e.g., Auto-commit: {timestamp}")
        self.commit_message_input.setText("Auto-commit from GitBuddy: {timestamp}")
        commit_msg_layout.addWidget(self.commit_message_input)
        details_layout.addLayout(commit_msg_layout)

        # Auto Push & Interval
        push_layout = QHBoxLayout()
        self.auto_push_checkbox = QCheckBox("Enable Auto Push")
        self.auto_push_checkbox.stateChanged.connect(self.toggle_push_fields)
        push_layout.addWidget(self.auto_push_checkbox)

        push_layout.addWidget(QLabel("Interval (sec):"))
        self.push_interval_spinbox = QSpinBox()
        self.push_interval_spinbox.setRange(1, 86400 * 7) # 1 second to 7 days
        self.push_interval_spinbox.setValue(3600) # Default 3600 seconds (1 hour)
        push_layout.addWidget(self.push_interval_spinbox)
        push_layout.addStretch(1)
        details_layout.addLayout(push_layout)

        # Form action buttons
        form_buttons_layout = QHBoxLayout()
        self.update_selected_button = QPushButton("Update Selected Repository")
        self.update_selected_button.clicked.connect(self.add_or_update_repository)
        self.update_selected_button.setEnabled(False) # Disabled until item selected
        form_buttons_layout.addWidget(self.update_selected_button)

        self.clear_form_button = QPushButton("Clear Form")
        self.clear_form_button.clicked.connect(self.clear_form_and_selection)
        form_buttons_layout.addWidget(self.clear_form_button)
        form_buttons_layout.addStretch(1)
        details_layout.addLayout(form_buttons_layout)

        layout.addWidget(details_group_box)
        layout.addStretch(1)

        # Initial state for fields based on checkboxes
        self.toggle_pull_interval_field(self.auto_pull_checkbox.checkState())
        self.toggle_commit_fields(self.auto_commit_checkbox.checkState())
        self.toggle_push_fields(self.auto_push_checkbox.checkState())
        self.clear_form_and_selection() # Start with a clean form and no selection

    def set_repositories_data(self, data):
        """
        Receives the full repositories data from GitBuddyApp.
        Updates the internal list and refreshes the table.
        """
        self.repositories_data = data
        self.load_repositories_to_table()

    def set_selected_repo_path(self, path):
        """
        Called by GitBuddyApp to update the selected repository path from the global selector.
        This tab doesn't directly use this for its UI, but it's available if needed.
        """
        self.current_selected_global_repo_path = path
        # No direct UI update needed here, as this tab manages its own list/selection.

    def toggle_pull_interval_field(self, state):
        """Enables/disables pull interval field based on auto_pull_checkbox state."""
        self.pull_interval_spinbox.setEnabled(state == Qt.Checked)

    def toggle_commit_fields(self, state):
        """Enables/disables commit-related fields based on auto_commit_checkbox state."""
        enabled = (state == Qt.Checked)
        self.commit_message_input.setEnabled(enabled)

    def toggle_push_fields(self, state):
        """Enables/disables push-related fields based on auto_push_checkbox state."""
        enabled = (state == Qt.Checked)
        self.push_interval_spinbox.setEnabled(enabled)

    def load_repositories_to_table(self):
        """Populates the QTableWidget with data from self.repositories_data."""
        self.repo_table_widget.setRowCount(0) # Clear existing rows
        for repo_data in self.repositories_data:
            self._add_repo_to_table(repo_data)
        self.clear_form_and_selection() # Clear form after loading

    def _add_repo_to_table(self, repo_data):
        """Helper to add a single repository's data to the QTableWidget."""
        row_position = self.repo_table_widget.rowCount()
        self.repo_table_widget.insertRow(row_position)

        self.repo_table_widget.setItem(row_position, 0, QTableWidgetItem(repo_data['path']))
        
        pull_interval_text = f"{repo_data['pull_interval']} sec" if repo_data.get('auto_pull', False) else "Disabled"
        self.repo_table_widget.setItem(row_position, 1, QTableWidgetItem(pull_interval_text))

        commit_status_text = "Enabled" if repo_data.get('auto_commit', False) else "Disabled"
        self.repo_table_widget.setItem(row_position, 2, QTableWidgetItem(commit_status_text))
        self.repo_table_widget.setItem(row_position, 3, QTableWidgetItem(repo_data.get('commit_message_template', 'N/A')))

        push_interval_text = f"{repo_data['push_interval']} sec" if repo_data.get('auto_push', False) else "Disabled"
        self.repo_table_widget.setItem(row_position, 4, QTableWidgetItem(push_interval_text))
        self.repo_table_widget.setItem(row_position, 5, QTableWidgetItem(push_interval_text)) # Redundant but matches column

    def load_selected_repository_details(self):
        """Loads details of the selected repository from the table into the form fields."""
        selected_rows = self.repo_table_widget.selectedIndexes()
        if not selected_rows:
            self.clear_form_and_selection()
            return

        selected_row_index = selected_rows[0].row()
        self.current_selected_repo_index = selected_row_index
        self.remove_repository_button.setEnabled(True)
        self.update_selected_button.setEnabled(True)
        self.add_repository_button.setText("Add New Repository") # Change text back to "Add New"

        repo_data = self.repositories_data[selected_row_index]

        self.repo_path_input.setText(repo_data['path'])
        self.repo_path_input.setReadOnly(True) # Path is read-only when editing existing
        
        self.auto_pull_checkbox.setChecked(repo_data.get('auto_pull', False))
        self.pull_interval_spinbox.setValue(repo_data.get('pull_interval', 300))
        
        self.auto_commit_checkbox.setChecked(repo_data.get('auto_commit', False))
        self.commit_message_input.setText(repo_data.get('commit_message_template', "Auto-commit from GitBuddy: {timestamp}"))
        
        self.auto_push_checkbox.setChecked(repo_data.get('auto_push', False))
        self.push_interval_spinbox.setValue(repo_data.get('push_interval', 3600))

    def clear_form_and_selection(self):
        """Clears the repository details form and table selection."""
        self.repo_table_widget.clearSelection()
        self.current_selected_repo_index = -1
        self.remove_repository_button.setEnabled(False)
        self.update_selected_button.setEnabled(False)
        self.add_repository_button.setText("Add New Repository") # Ensure button says "Add New"

        self.repo_path_input.clear()
        self.repo_path_input.setReadOnly(False) # Allow editing path for new entry
        
        self.auto_pull_checkbox.setChecked(False)
        self.pull_interval_spinbox.setValue(300)
        
        self.auto_commit_checkbox.setChecked(False)
        self.commit_message_input.setText("Auto-commit from GitBuddy: {timestamp}")
        
        self.auto_push_checkbox.setChecked(False)
        self.push_interval_spinbox.setValue(3600)

        # Ensure dependent fields are disabled if checkboxes are unchecked
        self.toggle_pull_interval_field(Qt.Unchecked)
        self.toggle_commit_fields(Qt.Unchecked)
        self.toggle_push_fields(Qt.Unchecked)

    def browse_for_repository(self):
        """Opens a file dialog to select a Git repository directory."""
        initial_path = self.repo_path_input.text() if self.repo_path_input.text() else QDir.homePath()
        directory = QFileDialog.getExistingDirectory(self, "Select Git Repository Directory", initial_path)
        if directory:
            normalized_path = os.path.abspath(os.path.expanduser(directory))
            if os.path.isdir(os.path.join(normalized_path, ".git")):
                self.repo_path_input.setText(normalized_path)
            else:
                QMessageBox.warning(self, "Not a Git Repository",
                                    f"The selected directory '{normalized_path}' does not appear to be a Git repository (missing .git folder).")
                self.repo_path_input.setText(normalized_path) # Still set it, user can override

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
            # Allow adding anyway, but warn the user. They might be adding a parent directory etc.

        new_repo_data = {
            'path': normalized_path,
            'auto_pull': self.auto_pull_checkbox.isChecked(),
            'pull_interval': self.pull_interval_spinbox.value(),
            'auto_commit': self.auto_commit_checkbox.isChecked(),
            'commit_message_template': self.commit_message_input.text().strip(),
            'auto_push': self.auto_push_checkbox.isChecked(),
            'push_interval': self.push_interval_spinbox.value()
        }

        if self.current_selected_repo_index != -1 and self.repositories_data[self.current_selected_repo_index]['path'] == normalized_path:
            # Update existing entry
            self.repositories_data[self.current_selected_repo_index] = new_repo_data
            QMessageBox.information(self, "Repository Updated", f"Repository '{os.path.basename(normalized_path)}' updated successfully.")
        else:
            # Check for duplicates before adding new
            if any(r['path'] == normalized_path for r in self.repositories_data):
                QMessageBox.information(self, "Duplicate", "This repository is already in the list.")
                return

            self.repositories_data.append(new_repo_data)
            QMessageBox.information(self, "Repository Added", f"Repository '{os.path.basename(normalized_path)}' added successfully.")
        
        # Emit the updated list of repositories for the parent to save
        self.repo_config_changed.emit(self.repositories_data) 
        self.clear_form_and_selection() # Clear form after add/update

    def remove_selected_repository(self):
        """Removes the selected repository from the list widget and data."""
        selected_rows = self.repo_table_widget.selectedIndexes()
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select a repository to remove.")
            return

        reply = QMessageBox.question(self, "Confirm Removal",
                                     "Are you sure you want to remove the selected repository?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        selected_path = self.repo_table_widget.item(selected_rows[0].row(), 0).text()
        
        # Remove from internal data list
        self.repositories_data = [r for r in self.repositories_data if r['path'] != selected_path]
        
        # Emit the updated list of repositories for the parent to save
        self.repo_config_changed.emit(self.repositories_data) 
        self.clear_form_and_selection() # Clear form after removal
        QMessageBox.information(self, "Repository Removed", f"Repository '{os.path.basename(selected_path)}' removed successfully.")
