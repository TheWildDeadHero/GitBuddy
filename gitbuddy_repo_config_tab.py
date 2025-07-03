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
    repo_config_changed = Signal() # Signal to notify GitBuddyApp of config changes

    def __init__(self, config_dir, parent=None):
        super().__init__(parent)
        self.config_dir = config_dir
        self.config_file = os.path.join(self.config_dir, "config.json")
        self.repositories_data = [] # Stores the full configuration for each repository
        self.current_selected_global_repo_path = "" # To store the path from the global selector

        self.init_ui()
        self.load_repositories_to_list()

    def init_ui(self):
        """Initializes the repository configurator tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # --- Top Action Buttons (Add, Remove) ---
        top_action_buttons_layout = QHBoxLayout()
        self.add_repository_button = QPushButton("Add New Repository")
        self.add_repository_button.clicked.connect(self.add_new_repository_dialog)
        top_action_buttons_layout.addWidget(self.add_repository_button)

        remove_button = QPushButton("Remove Selected")
        remove_button.setObjectName("removeButton")
        remove_button.clicked.connect(self.remove_selected_repository)
        top_action_buttons_layout.addWidget(remove_button)
        top_action_buttons_layout.addStretch(1)

        layout.addLayout(top_action_buttons_layout)
        # --- End Top Action Buttons ---

        # Table Widget to display repositories
        layout.addWidget(QLabel("Configured Git Repositories:"))
        self.repo_table_widget = QTableWidget()
        self.repo_table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.repo_table_widget.setSelectionMode(QTableWidget.SingleSelection)
        self.repo_table_widget.setColumnCount(5) # Name, Path, Auto Pull, Auto Commit, Auto Push
        self.repo_table_widget.setHorizontalHeaderLabels(["Name", "Path", "Auto Pull (min)", "Auto Commit (min)", "Auto Push (min)"]) # Updated header
        
        # Set "Path" column (index 1) to stretch
        self.repo_table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive) # Name
        self.repo_table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch) # Path (index 1)
        self.repo_table_widget.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive) # Auto Pull
        self.repo_table_widget.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive) # Auto Commit (new)
        self.repo_table_widget.horizontalHeader().setSectionResizeMode(4, QHeaderView.Interactive) # Auto Push
        
        self.repo_table_widget.verticalHeader().setVisible(False)
        self.repo_table_widget.setSortingEnabled(True)
        self.repo_table_widget.itemSelectionChanged.connect(self.load_selected_repository_details)
        layout.addWidget(self.repo_table_widget)

        # Repository Details/Add/Edit Form
        details_group_box = QGroupBox("Repository Details")
        details_layout = QVBoxLayout(details_group_box)

        # Path
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Path:"))
        self.repo_path_input = QLineEdit()
        self.repo_path_input.setPlaceholderText("Path will be displayed here...")
        self.repo_path_input.setReadOnly(True)
        path_layout.addWidget(self.repo_path_input)
        details_layout.addLayout(path_layout)

        # Auto Pull Checkbox
        self.auto_pull_checkbox = QCheckBox("Enable Auto Pull")
        self.auto_pull_checkbox.stateChanged.connect(self.toggle_pull_fields)
        details_layout.addWidget(self.auto_pull_checkbox)

        # Pull Interval
        pull_interval_layout = QHBoxLayout()
        pull_interval_layout.addWidget(QLabel("Pull Interval (minutes):"))
        self.pull_interval_spinbox = QSpinBox()
        self.pull_interval_spinbox.setRange(1, 43200) # 1 minute to 30 days (43200 minutes)
        self.pull_interval_spinbox.setValue(5)
        pull_interval_layout.addWidget(self.pull_interval_spinbox)
        pull_interval_layout.addStretch(1)
        details_layout.addLayout(pull_interval_layout)

        # Auto Commit
        self.auto_commit_checkbox = QCheckBox("Enable Auto Commit")
        self.auto_commit_checkbox.stateChanged.connect(self.toggle_commit_fields)
        details_layout.addWidget(self.auto_commit_checkbox)

        # Commit Interval (NEW)
        commit_interval_layout = QHBoxLayout()
        commit_interval_layout.addWidget(QLabel("Commit Interval (minutes):"))
        self.commit_interval_spinbox = QSpinBox()
        self.commit_interval_spinbox.setRange(1, 43200) # 1 minute to 30 days
        self.commit_interval_spinbox.setValue(60) # Default 1 hour
        commit_interval_layout.addWidget(self.commit_interval_spinbox)
        commit_interval_layout.addStretch(1)
        details_layout.addLayout(commit_interval_layout)

        commit_msg_layout = QHBoxLayout()
        commit_msg_layout.addWidget(QLabel("Commit Message Template:"))
        self.commit_message_input = QLineEdit()
        self.commit_message_input.setPlaceholderText("e.g., Auto-commit from GitBuddy: {timestamp}")
        self.commit_message_input.setText("Auto-commit from GitBuddy: {timestamp}")
        commit_msg_layout.addWidget(self.commit_message_input)
        details_layout.addLayout(commit_msg_layout)

        # Auto Push
        self.auto_push_checkbox = QCheckBox("Enable Auto Push")
        self.auto_push_checkbox.stateChanged.connect(self.toggle_push_fields)
        details_layout.addWidget(self.auto_push_checkbox)

        push_interval_layout = QHBoxLayout()
        push_interval_layout.addWidget(QLabel("Push Interval (minutes):"))
        self.push_interval_spinbox = QSpinBox()
        self.push_interval_spinbox.setRange(1, 525600) # 1 minute to 365 days (525600 minutes)
        self.push_interval_spinbox.setValue(60)
        push_interval_layout.addWidget(self.push_interval_spinbox)
        push_interval_layout.addStretch(1)
        details_layout.addLayout(push_interval_layout)

        # Form action buttons (Clear Form)
        form_buttons_layout = QHBoxLayout()
        self.clear_form_button = QPushButton("Clear Form")
        self.clear_form_button.clicked.connect(self.clear_form)
        form_buttons_layout.addWidget(self.clear_form_button)
        form_buttons_layout.addStretch(1)
        details_layout.addLayout(form_buttons_layout)

        layout.addWidget(details_group_box)

        # --- Global Action Buttons (Update, Save) ---
        global_action_buttons_layout = QHBoxLayout()
        global_action_buttons_layout.addStretch(1)

        self.update_repository_button = QPushButton("Update Repository")
        self.update_repository_button.clicked.connect(self.update_selected_repository)
        self.update_repository_button.setEnabled(False)
        global_action_buttons_layout.addWidget(self.update_repository_button)

        save_button = QPushButton("Save All Configuration")
        save_button.clicked.connect(self.save_configuration)
        global_action_buttons_layout.addWidget(save_button)
        layout.addLayout(global_action_buttons_layout)
        # --- End Global Action Buttons ---

        # Initial state for all fields
        self.clear_form()


    def set_selected_repo_path(self, path):
        """Called by GitBuddyApp to update the selected repository path."""
        self.current_selected_global_repo_path = path
        self.repo_path_input.setText(path)
        
        # Attempt to select the item in the table widget if it exists
        found_item = None
        for row in range(self.repo_table_widget.rowCount()):
            item = self.repo_table_widget.item(row, 1) # Column 1 is Path
            if item and item.text() == path:
                found_item = item
                self.repo_table_widget.selectRow(row) # Select the entire row
                break
        
        if not found_item:
            # If the path is not in our configured list (e.g., "Other" path), clear the form
            self.clear_form()
            self.repo_path_input.setText(path) # Display the non-configured path
            self.update_repository_button.setEnabled(False) # Cannot update a non-configured repo


    def toggle_pull_fields(self, state):
        """Enables/disables pull-related fields based on auto_pull_checkbox state."""
        enabled = (state == Qt.Checked)
        self.pull_interval_spinbox.setEnabled(enabled)

    def toggle_commit_fields(self, state):
        """Enables/disables commit-related fields based on auto_commit_checkbox state."""
        enabled = (state == Qt.Checked)
        self.commit_interval_spinbox.setEnabled(enabled) # NEW: Enable/disable commit interval
        self.commit_message_input.setEnabled(enabled)

    def toggle_push_fields(self, state):
        """Enables/disables push-related fields based on auto_push_checkbox state."""
        enabled = (state == Qt.Checked)
        self.push_interval_spinbox.setEnabled(enabled)

    def load_repositories_to_list(self):
        """Loads repository data from the config file and populates the QTableWidget."""
        self.repo_table_widget.setRowCount(0) # Clear existing rows
        self.repositories_data = []

        if not os.path.exists(self.config_file):
            return

        try:
            with open(self.config_file, 'r') as f:
                repos_config = json.load(f)
                if not isinstance(repos_config, list):
                    QMessageBox.warning(self, "Configuration Error",
                                        f"Configuration file '{self.config_file}' is malformed. Expected a list of objects.")
                    return
                
                for entry in repos_config:
                    if isinstance(entry, dict) and 'path' in entry:
                        repo_data = {
                            'path': entry['path'],
                            'auto_pull': entry.get('auto_pull', True),
                            'pull_interval': entry.get('pull_interval', 300) // 60, # Convert to minutes
                            'auto_commit': entry.get('auto_commit', False),
                            'commit_interval': entry.get('commit_interval', 3600) // 60, # NEW: Convert to minutes
                            'commit_message_template': entry.get('commit_message_template', "Auto-commit from GitBuddy: {timestamp}"),
                            'auto_push': entry.get('auto_push', False),
                            'push_interval': entry.get('push_interval', 3600) // 60 # Convert to minutes
                        }
                        self.repositories_data.append(repo_data)
                        self._add_repo_to_table(repo_data) # Add to table
                    else:
                        QMessageBox.warning(self, "Configuration Warning",
                                            f"Skipping malformed entry in config file: {entry}")
        except json.JSONDecodeError:
            QMessageBox.warning(self, "Configuration Error",
                                f"Error reading configuration file '{self.config_file}'. It might be corrupted.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred while loading config: {e}")

    def _add_repo_to_table(self, repo_data):
        """Helper to add a single repository's data to the QTableWidget."""
        row_position = self.repo_table_widget.rowCount()
        self.repo_table_widget.insertRow(row_position)

        repo_name = os.path.basename(repo_data['path'])

        self.repo_table_widget.setItem(row_position, 0, QTableWidgetItem(repo_name))
        self.repo_table_widget.setItem(row_position, 1, QTableWidgetItem(repo_data['path']))
        self.repo_table_widget.setItem(row_position, 2, QTableWidgetItem(str(repo_data['pull_interval'])))
        self.repo_table_widget.setItem(row_position, 3, QTableWidgetItem(str(repo_data['commit_interval']))) # NEW: Commit interval
        self.repo_table_widget.setItem(row_position, 4, QTableWidgetItem(str(repo_data['push_interval'])))

    def _update_repo_in_table(self, row, repo_data):
        """Helper to update a single repository's data in the QTableWidget."""
        repo_name = os.path.basename(repo_data['path'])
        self.repo_table_widget.item(row, 0).setText(repo_name)
        self.repo_table_widget.item(row, 1).setText(repo_data['path'])
        self.repo_table_widget.item(row, 2).setText(str(repo_data['pull_interval']))
        self.repo_table_widget.item(row, 3).setText(str(repo_data['commit_interval'])) # NEW: Commit interval
        self.repo_table_widget.item(row, 4).setText(str(repo_data['push_interval']))


    def load_selected_repository_details(self):
        """Loads details of the selected repository from the table into the form fields."""
        selected_rows = self.repo_table_widget.selectedIndexes()
        if not selected_rows:
            self.clear_form()
            self.update_repository_button.setEnabled(False)
            return

        # Get the path from the selected row (column 1)
        selected_row = selected_rows[0].row()
        selected_path = self.repo_table_widget.item(selected_row, 1).text()
        
        repo_data = next((r for r in self.repositories_data if r['path'] == selected_path), None)

        if repo_data:
            self.repo_path_input.setText(repo_data['path'])
            self.repo_path_input.setReadOnly(True)

            self.auto_pull_checkbox.setChecked(repo_data['auto_pull'])
            self.toggle_pull_fields(self.auto_pull_checkbox.checkState())
            self.pull_interval_spinbox.setValue(repo_data['pull_interval'])
            
            self.auto_commit_checkbox.setChecked(repo_data['auto_commit'])
            self.toggle_commit_fields(self.auto_commit_checkbox.checkState())
            self.commit_interval_spinbox.setValue(repo_data['commit_interval']) # NEW: Set commit interval
            self.commit_message_input.setText(repo_data['commit_message_template'])
            
            self.auto_push_checkbox.setChecked(repo_data['auto_push'])
            self.toggle_push_fields(self.auto_push_checkbox.checkState())
            self.push_interval_spinbox.setValue(repo_data['push_interval'])
            
            self.update_repository_button.setEnabled(True)
        else:
            self.clear_form()
            self.update_repository_button.setEnabled(False)

    def clear_form(self):
        """Clears the repository details form."""
        self.repo_table_widget.clearSelection() # Clear table selection
        self.repo_path_input.clear()
        self.repo_path_input.setReadOnly(True) # Keep read-only, path comes from global selector or table selection
        
        self.auto_pull_checkbox.setChecked(True)
        self.toggle_pull_fields(Qt.Checked)
        self.pull_interval_spinbox.setValue(5)
        
        self.auto_commit_checkbox.setChecked(False)
        self.toggle_commit_fields(Qt.Unchecked)
        self.commit_interval_spinbox.setValue(60) # NEW: Default commit interval
        self.commit_message_input.setText("Auto-commit from GitBuddy: {timestamp}")
        
        self.auto_push_checkbox.setChecked(False)
        self.toggle_push_fields(Qt.Unchecked)
        self.push_interval_spinbox.setValue(60)
        
        self.update_repository_button.setEnabled(False)
        self.add_repository_button.setText("Add New Repository")


    def add_new_repository_dialog(self):
        """Opens a directory selector dialog to add a new Git repository."""
        initial_path = self.current_selected_global_repo_path if self.current_selected_global_repo_path and os.path.isdir(os.path.expanduser(self.current_selected_global_repo_path)) else QDir.homePath()
        directory = QFileDialog.getExistingDirectory(self, "Select Git Repository Directory to Add", initial_path)
        if not directory:
            return # User cancelled dialog
        
        normalized_path = os.path.abspath(os.path.expanduser(directory))

        if not os.path.isdir(normalized_path):
            QMessageBox.warning(self, "Invalid Path", f"The selected path '{normalized_path}' is not a valid directory.")
            return
        if not os.path.isdir(os.path.join(normalized_path, ".git")):
            QMessageBox.warning(self, "Not a Git Repository",
                                f"The selected directory '{normalized_path}' does not appear to be a Git repository (missing .git folder).")
            # Allow adding anyway, but warn the user.

        # Check for duplicates before adding
        if any(r['path'] == normalized_path for r in self.repositories_data):
            QMessageBox.information(self, "Duplicate", "This repository is already in the list.")
            return

        new_repo_data = {
            'path': normalized_path,
            'auto_pull': self.auto_pull_checkbox.isChecked(),
            'pull_interval': self.pull_interval_spinbox.value(),
            'auto_commit': self.auto_commit_checkbox.isChecked(),
            'commit_interval': self.commit_interval_spinbox.value(), # NEW: Save commit interval
            'commit_message_template': self.commit_message_input.text().strip(),
            'auto_push': self.auto_push_checkbox.isChecked(),
            'push_interval': self.push_interval_spinbox.value()
        }

        self.repositories_data.append(new_repo_data)
        self._add_repo_to_table(new_repo_data) # Add to table
        QMessageBox.information(self, "Repository Added", f"Repository '{normalized_path}' added successfully.")
        
        self.clear_form()
        self.save_configuration()

    def update_selected_repository(self):
        """Updates the configuration of the currently selected repository."""
        selected_rows = self.repo_table_widget.selectedIndexes()
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select a repository from the list to update its configuration.")
            return

        selected_row = selected_rows[0].row()
        repo_path = self.repo_table_widget.item(selected_row, 1).text() # Get path from table
        normalized_path = os.path.abspath(os.path.expanduser(repo_path))

        existing_repo_data = next((r for r in self.repositories_data if r['path'] == normalized_path), None)

        if not existing_repo_data:
            QMessageBox.critical(self, "Update Error", "Selected repository not found in internal data. Please refresh or re-add.")
            return

        # Update the data with current form values
        existing_repo_data.update({
            'auto_pull': self.auto_pull_checkbox.isChecked(),
            'pull_interval': self.pull_interval_spinbox.value(),
            'auto_commit': self.auto_commit_checkbox.isChecked(),
            'commit_interval': self.commit_interval_spinbox.value(), # NEW: Update commit interval
            'commit_message_template': self.commit_message_input.text().strip(),
            'auto_push': self.auto_push_checkbox.isChecked(),
            'push_interval': self.push_interval_spinbox.value()
        })
        
        self._update_repo_in_table(selected_row, existing_repo_data) # Update table display
        QMessageBox.information(self, "Repository Updated", f"Configuration for '{normalized_path}' updated successfully.")
        self.save_configuration() # Save changes to file

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

        selected_row = selected_rows[0].row()
        selected_path = self.repo_table_widget.item(selected_row, 1).text() # Get path from table

        self.repositories_data = [r for r in self.repositories_data if r['path'] != selected_path]
        self.repo_table_widget.removeRow(selected_row) # Remove row from table
        self.clear_form()
        self.save_configuration()
        QMessageBox.information(self, "Repository Removed", f"Repository '{selected_path}' removed successfully.")


    def save_configuration(self):
        """Saves the current list of repositories (with all their settings) to the configuration file."""
        config_to_save = []
        for repo in self.repositories_data:
            repo_copy = repo.copy()
            repo_copy['pull_interval'] = repo_copy['pull_interval'] * 60
            repo_copy['commit_interval'] = repo_copy['commit_interval'] * 60 # NEW: Convert commit interval to seconds
            repo_copy['push_interval'] = repo_copy['push_interval'] * 60
            config_to_save.append({k: v for k, v in repo_copy.items() if k not in ['last_pulled_at', 'last_pushed_at']})

        try:
            with open(self.config_file, 'w') as f:
                json.dump(config_to_save, f, indent=4)
            QMessageBox.information(self, "Configuration Saved",
                                    f"Configuration saved successfully to '{self.config_file}'.\n"
                                    "Remember to restart the GitBuddy service for changes to take full effect.")
            self.repo_config_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save configuration: {e}")
