# git_puller_gui.py

import sys
import json
import os
import subprocess
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QLineEdit, QLabel, QFrame, QCheckBox, QSpinBox, QGroupBox
)
from PySide6.QtCore import Qt, QDir, QTimer
from PySide6.QtGui import QIcon, QPalette, QColor

# Define the configuration file path (must match the service script)
CONFIG_DIR = os.path.expanduser("~/.config/git-puller")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# Ensure the configuration directory exists
os.makedirs(CONFIG_DIR, exist_ok=True)

class GitBuddyGui(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GitBuddy")
        self.setGeometry(100, 100, 800, 700) # x, y, width, height adjusted for new controls

        self.repositories_data = [] # Stores the full configuration for each repository

        self.init_ui()
        self.load_repositories_to_list()
        self.update_service_status() # Initial status update

        # Set up a timer to periodically update service status
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_service_status)
        self.status_timer.start(5000) # Update every 5 seconds

    def init_ui(self):
        """Initializes the user interface elements."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Apply a consistent style, relying on system theme for colors
        self.setStyleSheet("""
            QMainWindow {
                /* Remove background-color to let system theme handle it */
                border-radius: 12px;
            }
            QFrame#statusFrame {
                /* Remove background-color and border color to let system theme handle it */
                border: 1px solid; /* Use system's default border color */
                border-radius: 10px;
                padding: 10px;
            }
            QLabel#statusLabel {
                font-size: 16px;
                font-weight: bold;
                /* Remove color to let system theme handle it */
            }
            QListWidget {
                /* Remove background-color and border color to let system theme handle it */
                border: 1px solid; /* Use system's default border color */
                border-radius: 8px;
                padding: 5px;
                font-size: 14px;
            }
            QPushButton {
                /* Remove background-color and color to let system theme handle it */
                border: none;
                padding: 10px 20px;
                text-align: center;
                text-decoration: none;
                font-size: 14px;
                margin: 4px 2px;
                border-radius: 8px;
                box-shadow: 2px 2px 5px rgba(0, 0, 0, 0.2);
                min-width: 120px; /* Ensure consistent button width */
            }
            QPushButton:hover {
                /* Let system theme handle hover effects, or define subtle ones */
                /* background-color: rgba(0,0,0,0.1); */ /* Example if you want a subtle overlay */
            }
            QPushButton:pressed {
                /* Let system theme handle pressed effects */
                box-shadow: inset 1px 1px 3px rgba(0, 0, 0, 0.3);
            }
            /* Specific button styles - use system colors where possible or more neutral tones */
            QPushButton#removeButton {
                /* Use a more neutral red or let system theme provide */
                /* background-color: #f44336; */
            }
            QPushButton#stopButton {
                /* Use a more neutral orange or let system theme provide */
                /* background-color: #FF9800; */
            }
            QPushButton#startButton {
                /* Use a more neutral blue or let system theme provide */
                /* background-color: #2196F3; */
            }
            QLineEdit, QSpinBox {
                /* Remove border color to let system theme handle it */
                border: 1px solid; /* Use system's default border color */
                border-radius: 8px;
                padding: 8px;
                font-size: 14px;
            }
            QLabel {
                font-size: 15px;
                font-weight: bold;
                /* Remove color to let system theme handle it */
            }
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                /* Remove color to let system theme handle it */
                /* Remove border color to let system theme handle it */
                border: 1px solid; /* Use system's default border color */
                border-radius: 8px;
                margin-top: 1ex; /* leave space for title */
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left; /* position at the top left */
                padding: 0 3px;
                background-color: transparent;
            }
        """)

        # Service Status Section
        status_frame = QFrame()
        status_frame.setObjectName("statusFrame")
        status_layout = QHBoxLayout(status_frame)
        self.status_label = QLabel("Service Status: Unknown")
        self.status_label.setObjectName("statusLabel")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch(1) # Push label to left
        main_layout.addWidget(status_frame)

        # Service Control Buttons
        service_control_layout = QHBoxLayout()
        self.start_service_button = QPushButton("Start Service")
        self.start_service_button.setObjectName("startButton")
        self.start_service_button.clicked.connect(self.start_service)
        service_control_layout.addWidget(self.start_service_button)

        self.stop_service_button = QPushButton("Stop Service")
        self.stop_service_button.setObjectName("stopButton")
        self.stop_service_button.clicked.connect(self.stop_service)
        service_control_layout.addWidget(self.stop_service_button)

        refresh_status_button = QPushButton("Refresh Status")
        refresh_status_button.clicked.connect(self.update_service_status)
        service_control_layout.addWidget(refresh_status_button)
        service_control_layout.addStretch(1) # Pushes buttons to the left
        main_layout.addLayout(service_control_layout)


        # List Widget to display repositories
        main_layout.addWidget(QLabel("Configured Git Repositories:"))
        self.repo_list_widget = QListWidget()
        self.repo_list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.repo_list_widget.itemSelectionChanged.connect(self.load_selected_repository_details)
        main_layout.addWidget(self.repo_list_widget)

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
        self.commit_message_input.setText("Auto-commit from GitBuddy: {timestamp}")
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

        main_layout.addWidget(details_group_box)

        # Global Action Buttons (Remove, Save)
        global_button_layout = QHBoxLayout()
        global_button_layout.addStretch(1) # Pushes buttons to the right

        remove_button = QPushButton("Remove Selected")
        remove_button.setObjectName("removeButton") # Set object name for specific styling
        remove_button.clicked.connect(self.remove_selected_repository)
        global_button_layout.addWidget(remove_button)

        save_button = QPushButton("Save Configuration")
        save_button.clicked.connect(self.save_configuration)
        global_button_layout.addWidget(save_button)

        main_layout.addLayout(global_button_layout)

        # Initial state for commit/push fields
        self.toggle_commit_fields(self.auto_commit_checkbox.checkState())
        self.toggle_push_fields(self.auto_push_checkbox.checkState())
        self.clear_form() # Start with a clean form

    def toggle_commit_fields(self, state):
        """Enables/disables commit-related fields based on auto_commit_checkbox state."""
        enabled = (state == Qt.Checked)
        self.commit_message_input.setEnabled(enabled)

    def toggle_push_fields(self, state):
        """Enables/disables push-related fields based on auto_push_checkbox state."""
        enabled = (state == Qt.Checked)
        self.push_interval_spinbox.setEnabled(enabled)

    def load_repositories_to_list(self):
        """Loads repository paths from the config file and populates the QListWidget."""
        self.repo_list_widget.clear()
        self.repositories_data = [] # Clear existing data

        if not os.path.exists(CONFIG_FILE):
            return

        try:
            with open(CONFIG_FILE, 'r') as f:
                repos_config = json.load(f)
                if not isinstance(repos_config, list):
                    QMessageBox.warning(self, "Configuration Error",
                                        f"Configuration file '{CONFIG_FILE}' is malformed. Expected a list of objects.")
                    return
                
                for entry in repos_config:
                    if isinstance(entry, dict) and 'path' in entry:
                        # Ensure all expected keys are present with defaults
                        repo_data = {
                            'path': entry['path'],
                            'pull_interval': entry.get('pull_interval', 300),
                            'auto_commit': entry.get('auto_commit', False),
                            'commit_message_template': entry.get('commit_message_template', "Auto-commit from Git Puller: {timestamp}"),
                            'auto_push': entry.get('auto_push', False),
                            'push_interval': entry.get('push_interval', 3600)
                        }
                        self.repositories_data.append(repo_data)
                        self.repo_list_widget.addItem(repo_data['path'])
                    else:
                        QMessageBox.warning(self, "Configuration Warning",
                                            f"Skipping malformed entry in config file: {entry}")
        except json.JSONDecodeError:
            QMessageBox.warning(self, "Configuration Error",
                                f"Error reading configuration file '{CONFIG_FILE}'. It might be corrupted.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred while loading config: {e}")

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
            self.pull_interval_spinbox.setValue(repo_data['pull_interval'])
            self.auto_commit_checkbox.setChecked(repo_data['auto_commit'])
            self.commit_message_input.setText(repo_data['commit_message_template'])
            self.auto_push_checkbox.setChecked(repo_data['auto_push'])
            self.push_interval_spinbox.setValue(repo_data['push_interval'])
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
        self.commit_message_input.setText("Auto-commit from Git Puller: {timestamp}")
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
                self.repo_path_input.setText(directory) # Still set it, user can override

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
            'pull_interval': self.pull_interval_spinbox.value(),
            'auto_commit': self.auto_commit_checkbox.isChecked(),
            'commit_message_template': self.commit_message_input.text().strip(),
            'auto_push': self.auto_push_checkbox.isChecked(),
            'push_interval': self.push_interval_spinbox.value()
        }

        # Check if updating an existing entry
        existing_index = -1
        for i, r in enumerate(self.repositories_data):
            if r['path'] == normalized_path:
                existing_index = i
                break

        if existing_index != -1:
            # Update existing
            self.repositories_data[existing_index] = new_repo_data
            self.repo_list_widget.item(existing_index).setText(normalized_path) # Update list item text if path changed (though path is read-only when editing)
            QMessageBox.information(self, "Repository Updated", f"Repository '{normalized_path}' updated successfully.")
        else:
            # Add new
            # Check for duplicates before adding
            if any(r['path'] == normalized_path for r in self.repositories_data):
                QMessageBox.information(self, "Duplicate", "This repository is already in the list.")
                return

            self.repositories_data.append(new_repo_data)
            self.repo_list_widget.addItem(normalized_path)
            QMessageBox.information(self, "Repository Added", f"Repository '{normalized_path}' added successfully.")
        
        self.clear_form() # Clear form after add/update
        self.save_configuration() # Auto-save after add/update

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
            # Remove from internal data list
            self.repositories_data = [r for r in self.repositories_data if r['path'] != selected_path]
            # Remove from QListWidget
            row = self.repo_list_widget.row(selected_items[0])
            self.repo_list_widget.takeItem(row)
            self.clear_form() # Clear form after removal
            self.save_configuration() # Auto-save after removal
            QMessageBox.information(self, "Repository Removed", f"Repository '{selected_path}' removed successfully.")


    def save_configuration(self):
        """Saves the current list of repositories (with all their settings) to the configuration file."""
        # Only save the relevant configuration data, not internal timestamps
        config_to_save = [
            {k: v for k, v in repo.items() if k not in ['last_pulled_at', 'last_pushed_at']}
            for repo in self.repositories_data
        ]
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config_to_save, f, indent=4)
            QMessageBox.information(self, "Configuration Saved",
                                    f"Configuration saved successfully to '{CONFIG_FILE}'.\n"
                                    "Remember to restart the service for changes to take full effect.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save configuration: {e}")

    def run_systemctl_command(self, command):
        """Helper to run systemctl commands and return output/error."""
        try:
            result = subprocess.run(
                ['systemctl', '--user', command, 'git-puller.service'],
                capture_output=True,
                text=True,
                check=False # Do not raise exception for non-zero exit codes (e.g., if service is already stopped)
            )
            return result.stdout.strip(), result.stderr.strip(), result.returncode == 0
        except FileNotFoundError:
            QMessageBox.critical(self, "Error", "systemctl command not found. Is systemd installed and in your PATH?")
            return "", "systemctl not found", False
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred while running systemctl: {e}")
            return "", str(e), False

    def start_service(self):
        """Starts the systemd service."""
        stdout, stderr, success = self.run_systemctl_command("start")
        if success:
            QMessageBox.information(self, "Service Control", "Git Puller service started successfully.")
        else:
            QMessageBox.warning(self, "Service Control", f"Failed to start service:\n{stderr}")
        self.update_service_status()

    def stop_service(self):
        """Stops the systemd service."""
        stdout, stderr, success = self.run_systemctl_command("stop")
        if success:
            QMessageBox.information(self, "Service Control", "Git Puller service stopped successfully.")
        else:
            QMessageBox.warning(self, "Service Control", f"Failed to stop service:\n{stderr}")
        self.update_service_status()

    def update_service_status(self):
        """Updates the status label based on systemd service status."""
        stdout, stderr, success = self.run_systemctl_command("is-active")
        status_text = "Unknown"
        # Use QPalette to get system colors for status
        palette = self.palette()
        text_color = palette.color(QPalette.WindowText) # Default text color

        if "active" in stdout:
            status_text = "Running"
            # Use system's highlight/success color if available, or a neutral green
            text_color = palette.color(QPalette.Highlight) if palette.color(QPalette.Highlight).isValid() else QColor("#4CAF50")
            self.start_service_button.setEnabled(False)
            self.stop_service_button.setEnabled(True)
        elif "inactive" in stdout or "failed" in stdout:
            status_text = "Stopped" if "inactive" in stdout else "Failed"
            # Use system's destructive/error color if available, or a neutral red
            text_color = palette.color(QPalette.BrightText) if palette.color(QPalette.BrightText).isValid() else QColor("#f44336") # Often red
            self.start_service_button.setEnabled(True)
            self.stop_service_button.setEnabled(False)
        else:
            status_text = f"Unknown: {stdout}"
            # Use system's warning color if available, or a neutral orange
            text_color = palette.color(QPalette.ToolTipBase) if palette.color(QPalette.ToolTipBase).isValid() else QColor("orange") # Often yellow/orange
            self.start_service_button.setEnabled(True)
            self.stop_service_button.setEnabled(True)

        # Set text and color using QPalette for better system integration
        self.status_label.setText(f"Service Status: {status_text}")
        self.status_label.setStyleSheet(f"QLabel#statusLabel {{ color: {text_color.name()}; }}")
