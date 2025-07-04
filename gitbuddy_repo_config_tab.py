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
        self.current_selected_repo_index = -1 # Index of the currently selected repo in self.repositories_data

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

        self.remove_button = QPushButton("Remove Selected")
        self.remove_button.setObjectName("removeButton")
        self.remove_button.clicked.connect(self.remove_selected_repository)
        top_action_buttons_layout.addWidget(self.remove_button)
        top_action_buttons_layout.addStretch(1)

        layout.addLayout(top_action_buttons_layout)
        # --- End Top Action Buttons ---

        # Table Widget to display repositories
        layout.addWidget(QLabel("Configured Git Repositories:"))
        self.repo_table_widget = QTableWidget()
        self.repo_table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.repo_table_widget.setSelectionMode(QTableWidget.SingleSelection)
        self.repo_table_widget.setColumnCount(6)
        self.repo_table_widget.setHorizontalHeaderLabels(["Name", "Path", "Auto Pull (min)", "Auto Commit (min)", "Commit Message", "Auto Push (min)"])
        
        # Set column resize modes
        self.repo_table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive) # Name
        self.repo_table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch) # Path
        self.repo_table_widget.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive) # Auto Pull
        self.repo_table_widget.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive) # Auto Commit
        self.repo_table_widget.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch) # Commit Message
        self.repo_table_widget.horizontalHeader().setSectionResizeMode(5, QHeaderView.Interactive) # Auto Push
        
        self.repo_table_widget.verticalHeader().setVisible(False)
        self.repo_table_widget.setSortingEnabled(True)
        # Connect signals: these will now directly update the data model
        self.repo_table_widget.cellChanged.connect(self._on_table_cell_edited)
        self.repo_table_widget.itemSelectionChanged.connect(self._on_table_selection_changed)
        layout.addWidget(self.repo_table_widget)

        # Repository Details/Add/Edit Form
        self.details_group_box = QGroupBox("Repository Details")
        details_layout = QVBoxLayout(self.details_group_box)

        # Path (read-only, displays selected repo path)
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Path:"))
        self.repo_path_input = QLineEdit()
        self.repo_path_input.setPlaceholderText("Path will be displayed here...")
        self.repo_path_input.setReadOnly(True)
        path_layout.addWidget(self.repo_path_input)
        details_layout.addLayout(path_layout)

        # Auto Pull Checkbox and Interval
        self.auto_pull_checkbox = QCheckBox("Enable Auto Pull")
        self.auto_pull_checkbox.stateChanged.connect(self._on_form_pull_checkbox_changed)
        details_layout.addWidget(self.auto_pull_checkbox)

        pull_interval_layout = QHBoxLayout()
        pull_interval_layout.addWidget(QLabel("Pull Interval (minutes):"))
        self.pull_interval_spinbox = QSpinBox()
        self.pull_interval_spinbox.setRange(1, 43200) # 1 minute to 30 days
        self.pull_interval_spinbox.setValue(5)
        self.pull_interval_spinbox.valueChanged.connect(self._on_form_pull_interval_changed)
        pull_interval_layout.addWidget(self.pull_interval_spinbox)
        pull_interval_layout.addStretch(1)
        details_layout.addLayout(pull_interval_layout)

        # Auto Commit Checkbox, Interval, and Message
        self.auto_commit_checkbox = QCheckBox("Enable Auto Commit")
        self.auto_commit_checkbox.stateChanged.connect(self._on_form_commit_checkbox_changed)
        details_layout.addWidget(self.auto_commit_checkbox)

        commit_interval_layout = QHBoxLayout()
        commit_interval_layout.addWidget(QLabel("Commit Interval (minutes):"))
        self.commit_interval_spinbox = QSpinBox()
        self.commit_interval_spinbox.setRange(1, 43200) # 1 minute to 30 days
        self.commit_interval_spinbox.setValue(60) # Default 1 hour
        self.commit_interval_spinbox.valueChanged.connect(self._on_form_commit_interval_changed)
        commit_interval_layout.addWidget(self.commit_interval_spinbox)
        commit_interval_layout.addStretch(1)
        details_layout.addLayout(commit_interval_layout)

        commit_msg_layout = QHBoxLayout()
        commit_msg_layout.addWidget(QLabel("Commit Message Template:"))
        self.commit_message_input = QLineEdit()
        self.commit_message_input.setPlaceholderText("e.g., Auto-commit from GitBuddy: {timestamp}")
        self.commit_message_input.setText("Auto-commit from GitBuddy: {timestamp}")
        self.commit_message_input.textChanged.connect(self._on_form_commit_message_changed)
        commit_msg_layout.addWidget(self.commit_message_input)
        details_layout.addLayout(commit_msg_layout)

        # Auto Push Checkbox and Interval
        self.auto_push_checkbox = QCheckBox("Enable Auto Push")
        self.auto_push_checkbox.stateChanged.connect(self._on_form_push_checkbox_changed)
        details_layout.addWidget(self.auto_push_checkbox)

        push_interval_layout = QHBoxLayout()
        push_interval_layout.addWidget(QLabel("Push Interval (minutes):"))
        self.push_interval_spinbox = QSpinBox()
        self.push_interval_spinbox.setRange(1, 525600) # 1 minute to 365 days
        self.push_interval_spinbox.setValue(60)
        self.push_interval_spinbox.valueChanged.connect(self._on_form_push_interval_changed)
        push_interval_layout.addWidget(self.push_interval_spinbox)
        push_interval_layout.addStretch(1)
        details_layout.addLayout(push_interval_layout)

        # Form action buttons (Clear Form - now just clears selection)
        form_buttons_layout = QHBoxLayout()
        self.clear_form_button = QPushButton("Clear Selection") # Renamed for clarity
        self.clear_form_button.clicked.connect(self.clear_form_and_selection)
        form_buttons_layout.addWidget(self.clear_form_button)
        form_buttons_layout.addStretch(1)
        details_layout.addLayout(form_buttons_layout)

        layout.addWidget(self.details_group_box)

        # --- Global Action Buttons (Save) ---
        global_action_buttons_layout = QHBoxLayout()
        global_action_buttons_layout.addStretch(1)

        save_all_button = QPushButton("Save All Configuration")
        save_all_button.clicked.connect(self.save_configuration)
        global_action_buttons_layout.addWidget(save_all_button)
        layout.addLayout(global_action_buttons_layout)
        # --- End Global Action Buttons ---

        # Initial state for form and buttons
        self._set_form_enabled(False) # Disable form initially
        self.update_buttons_on_selection()

    def _set_form_enabled(self, enabled):
        """Helper to enable/disable the repository details form group box."""
        self.details_group_box.setEnabled(enabled)
        # When enabling, ensure sub-fields correctly reflect their checkbox state
        if enabled:
            self.pull_interval_spinbox.setEnabled(self.auto_pull_checkbox.isChecked())
            self.commit_interval_spinbox.setEnabled(self.auto_commit_checkbox.isChecked())
            self.commit_message_input.setEnabled(self.auto_commit_checkbox.isChecked())
            self.push_interval_spinbox.setEnabled(self.auto_push_checkbox.isChecked())

    def set_selected_repo_path(self, path):
        """Called by GitBuddyApp to update the selected repository path."""
        self.current_selected_global_repo_path = path
        
        # Find and select the corresponding row in the table
        found_row_index = -1
        for row in range(self.repo_table_widget.rowCount()):
            item = self.repo_table_widget.item(row, 1) # Column 1 is Path
            if item and item.text() == path:
                found_row_index = row
                # Block signals to prevent _on_table_selection_changed from firing when programmatically selecting
                self.repo_table_widget.blockSignals(True)
                self.repo_table_widget.selectRow(row) # Select the entire row
                self.repo_table_widget.blockSignals(False)
                break
        
        if found_row_index != -1:
            self.current_selected_repo_index = found_row_index
            self._load_selected_repository_details_into_form()
        else:
            # If the path is not in our configured list (e.g., "Other" path), clear selection
            self.repo_table_widget.clearSelection()
            self.current_selected_repo_index = -1
            self.clear_form_and_selection() # Clear form as well
        
        self.update_buttons_on_selection() # Update button states based on selection

    def update_buttons_on_selection(self):
        """Updates the enabled state of remove button based on table selection."""
        has_selection = bool(self.repo_table_widget.selectedIndexes())
        self.remove_button.setEnabled(has_selection) # Ensure remove button is enabled/disabled

    # --- Form field change handlers: Update data model and then refresh UI ---
    def _on_form_pull_checkbox_changed(self, state):
        if self.current_selected_repo_index == -1: return
        repo_data = self.repositories_data[self.current_selected_repo_index]
        repo_data['auto_pull'] = (state == Qt.Checked)
        # Directly enable/disable associated spinbox
        self.pull_interval_spinbox.setEnabled(state == Qt.Checked)
        # No longer calling _refresh_ui_after_data_change here to prevent double-click issue

    def _on_form_pull_interval_changed(self, value):
        if self.current_selected_repo_index == -1: return
        repo_data = self.repositories_data[self.current_selected_repo_index]
        repo_data['pull_interval'] = value
        # No longer calling _refresh_ui_after_data_change here

    def _on_form_commit_checkbox_changed(self, state):
        if self.current_selected_repo_index == -1: return
        repo_data = self.repositories_data[self.current_selected_repo_index]
        repo_data['auto_commit'] = (state == Qt.Checked)
        # Directly enable/disable associated spinbox and input
        self.commit_interval_spinbox.setEnabled(state == Qt.Checked)
        self.commit_message_input.setEnabled(state == Qt.Checked)
        # No longer calling _refresh_ui_after_data_change here

    def _on_form_commit_interval_changed(self, value):
        if self.current_selected_repo_index == -1: return
        repo_data = self.repositories_data[self.current_selected_repo_index]
        repo_data['commit_interval'] = value
        # No longer calling _refresh_ui_after_data_change here

    def _on_form_commit_message_changed(self, text):
        if self.current_selected_repo_index == -1: return
        repo_data = self.repositories_data[self.current_selected_repo_index]
        repo_data['commit_message_template'] = text
        # No longer calling _refresh_ui_after_data_change here

    def _on_form_push_checkbox_changed(self, state):
        if self.current_selected_repo_index == -1: return
        repo_data = self.repositories_data[self.current_selected_repo_index]
        repo_data['auto_push'] = (state == Qt.Checked)
        # Directly enable/disable associated spinbox
        self.push_interval_spinbox.setEnabled(state == Qt.Checked)
        # No longer calling _refresh_ui_after_data_change here

    def _on_form_push_interval_changed(self, value):
        if self.current_selected_repo_index == -1: return
        repo_data = self.repositories_data[self.current_selected_repo_index]
        repo_data['push_interval'] = value
        # No longer calling _refresh_ui_after_data_change here
    # --- End Form field change handlers ---

    def _on_table_cell_edited(self, row, column):
        """Handles changes made directly in the QTableWidget cells."""
        # Block signals to prevent recursion when programmatically updating the cell
        self.repo_table_widget.blockSignals(True)

        if not (0 <= row < len(self.repositories_data)):
            QMessageBox.critical(self, "Data Error", "Edited row index out of bounds.")
            self.repo_table_widget.blockSignals(False)
            return

        repo_data = self.repositories_data[row]
        new_value_str = self.repo_table_widget.item(row, column).text().strip()

        try:
            if column == 2: # Auto Pull (min)
                if new_value_str.lower() in ["disabled", "off", ""]:
                    repo_data['auto_pull'] = False
                    repo_data['pull_interval'] = 0
                else:
                    interval = int(new_value_str)
                    if interval <= 0: raise ValueError("Interval must be a positive integer.")
                    repo_data['auto_pull'] = True
                    repo_data['pull_interval'] = interval
            
            elif column == 3: # Auto Commit (min)
                if new_value_str.lower() in ["disabled", "off", ""]:
                    repo_data['auto_commit'] = False
                    repo_data['commit_interval'] = 0
                else:
                    interval = int(new_value_str)
                    if interval <= 0: raise ValueError("Interval must be a positive integer.")
                    repo_data['auto_commit'] = True
                    repo_data['commit_interval'] = interval

            elif column == 4: # Commit Message
                repo_data['commit_message_template'] = new_value_str

            elif column == 5: # Auto Push (min)
                if new_value_str.lower() in ["disabled", "off", ""]:
                    repo_data['auto_push'] = False
                    repo_data['push_interval'] = 0
                else:
                    interval = int(new_value_str)
                    if interval <= 0: raise ValueError("Interval must be a positive integer.")
                    repo_data['auto_push'] = True
                    repo_data['push_interval'] = interval
            
            # After updating data, refresh the UI elements
            self._refresh_ui_after_data_change(row)

        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", f"Invalid value for column '{self.repo_table_widget.horizontalHeaderItem(column).text()}': {e}\n"
                                 "Please enter a positive integer or 'Disabled'/'Off'.")
            # Revert the table cell to its original value from the data model
            self._update_table_cell_from_data(row, column, repo_data)
        finally:
            self.repo_table_widget.blockSignals(False)
            self.save_configuration() # Save configuration after each valid cell change

    def _on_table_selection_changed(self):
        """Handles selection changes in the QTableWidget."""
        selected_rows = self.repo_table_widget.selectedIndexes()
        if not selected_rows:
            self.current_selected_repo_index = -1
            self.clear_form_and_selection()
            return

        selected_row = selected_rows[0].row()
        self.current_selected_repo_index = selected_row
        self._load_selected_repository_details_into_form()
        self.update_buttons_on_selection()

    def _refresh_ui_after_data_change(self, changed_row_index):
        """Refreshes the table row and the form if the changed row is selected."""
        # Update the table row
        if 0 <= changed_row_index < self.repo_table_widget.rowCount():
            self._update_table_row_from_data(changed_row_index, self.repositories_data[changed_row_index])
        
        # If the changed row is the currently selected one, update the form
        if changed_row_index == self.current_selected_repo_index:
            self._load_selected_repository_details_into_form()

        self.update() # Force repaint of the entire tab

    def load_repositories_to_list(self):
        """Loads repository data from the config file and populates the QTableWidget."""
        self.repo_table_widget.blockSignals(True) # Block signals during initial load
        self.repo_table_widget.setRowCount(0) # Clear existing rows
        self.repositories_data = []

        if not os.path.exists(self.config_file):
            self.repo_table_widget.blockSignals(False)
            self.repo_table_widget.viewport().update()
            return

        try:
            with open(self.config_file, 'r') as f:
                repos_config = json.load(f)
                if not isinstance(repos_config, list):
                    QMessageBox.warning(self, "Configuration Error",
                                        f"Configuration file '{self.config_file}' is malformed. Expected a list.")
                    self.repo_table_widget.blockSignals(False)
                    self.repo_table_widget.viewport().update()
                    return
                
                for entry in repos_config:
                    if isinstance(entry, dict) and 'path' in entry:
                        # Ensure all keys are present with default values
                        repo_data = {
                            'path': entry['path'],
                            'auto_pull': entry.get('auto_pull', False),
                            'pull_interval': entry.get('pull_interval', 300) // 60, # Convert to minutes
                            'auto_commit': entry.get('auto_commit', False),
                            'commit_interval': entry.get('commit_interval', 3600) // 60, # Convert to minutes
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
        finally:
            self.repo_table_widget.blockSignals(False)
            self.repo_table_widget.viewport().update() # Force repaint after loading

    def _add_repo_to_table(self, repo_data):
        """Helper to add a single repository's data to the QTableWidget."""
        row_position = self.repo_table_widget.rowCount()
        self.repo_table_widget.insertRow(row_position)
        self._update_table_row_from_data(row_position, repo_data)

    def _update_table_row_from_data(self, row, repo_data):
        """Helper to update a single repository's data in the QTableWidget from the data model."""
        self.repo_table_widget.blockSignals(True) # Block signals during programmatic update

        repo_name = os.path.basename(repo_data['path'])

        # Name column (Non-editable)
        name_item = QTableWidgetItem(repo_name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        self.repo_table_widget.setItem(row, 0, name_item)

        # Path column (Non-editable)
        path_item = QTableWidgetItem(repo_data['path'])
        path_item.setFlags(path_item.flags() & ~Qt.ItemIsEditable)
        self.repo_table_widget.setItem(row, 1, path_item)
        
        # Auto Pull column
        pull_text = str(repo_data['pull_interval']) if repo_data['auto_pull'] else "Disabled"
        self.repo_table_widget.setItem(row, 2, QTableWidgetItem(pull_text))
        
        # Auto Commit column
        commit_text = str(repo_data['commit_interval']) if repo_data['auto_commit'] else "Disabled"
        self.repo_table_widget.setItem(row, 3, QTableWidgetItem(commit_text))

        # Commit Message column
        self.repo_table_widget.setItem(row, 4, QTableWidgetItem(repo_data['commit_message_template']))
        
        # Auto Push column
        push_text = str(repo_data['push_interval']) if repo_data['auto_push'] else "Disabled"
        self.repo_table_widget.setItem(row, 5, QTableWidgetItem(push_text))

        self.repo_table_widget.blockSignals(False)
        self.repo_table_widget.viewport().update() # Force repaint

    def _update_table_cell_from_data(self, row, column, repo_data):
        """Helper to update a specific cell in the table from the data model."""
        self.repo_table_widget.blockSignals(True) # Block signals during programmatic update
        
        if column == 2: # Auto Pull
            text = str(repo_data['pull_interval']) if repo_data['auto_pull'] else "Disabled"
        elif column == 3: # Auto Commit
            text = str(repo_data['commit_interval']) if repo_data['auto_commit'] else "Disabled"
        elif column == 4: # Commit Message
            text = repo_data['commit_message_template']
        elif column == 5: # Auto Push
            text = str(repo_data['push_interval']) if repo_data['auto_push'] else "Disabled"
        else:
            text = "" # Should not happen for editable columns

        self.repo_table_widget.item(row, column).setText(text)
        self.repo_table_widget.blockSignals(False)
        self.repo_table_widget.viewport().update()


    def _load_selected_repository_details_into_form(self):
        """Loads details of the selected repository from the data model into the form fields."""
        if self.current_selected_repo_index == -1:
            self.clear_form_and_selection()
            return

        repo_data = self.repositories_data[self.current_selected_repo_index]

        self._set_form_enabled(True)
        self.repo_path_input.setText(repo_data['path'])
        self._populate_form_from_repo_data(repo_data)
        self.update() # Force repaint of the form area after loading


    def _populate_form_from_repo_data(self, repo_data):
        """Helper to populate form fields from a repo_data dictionary."""
        # Disconnect signals to prevent them from firing when setting values programmatically
        self.auto_pull_checkbox.stateChanged.disconnect(self._on_form_pull_checkbox_changed)
        self.pull_interval_spinbox.valueChanged.disconnect(self._on_form_pull_interval_changed)
        self.auto_commit_checkbox.stateChanged.disconnect(self._on_form_commit_checkbox_changed)
        self.commit_interval_spinbox.valueChanged.disconnect(self._on_form_commit_interval_changed)
        self.commit_message_input.textChanged.disconnect(self._on_form_commit_message_changed)
        self.auto_push_checkbox.stateChanged.disconnect(self._on_form_push_checkbox_changed)
        self.push_interval_spinbox.valueChanged.disconnect(self._on_form_push_interval_changed)

        self.repo_path_input.setText(repo_data['path']) # Ensure this is always set

        self.auto_pull_checkbox.setChecked(repo_data['auto_pull'])
        self.pull_interval_spinbox.setValue(repo_data['pull_interval'])
        self.pull_interval_spinbox.setEnabled(repo_data['auto_pull'])

        self.auto_commit_checkbox.setChecked(repo_data['auto_commit'])
        self.commit_interval_spinbox.setValue(repo_data['commit_interval'])
        self.commit_message_input.setText(repo_data['commit_message_template'])
        self.commit_interval_spinbox.setEnabled(repo_data['auto_commit'])
        self.commit_message_input.setEnabled(repo_data['auto_commit'])
        
        self.auto_push_checkbox.setChecked(repo_data['auto_push'])
        self.push_interval_spinbox.setValue(repo_data['push_interval'])
        self.push_interval_spinbox.setEnabled(repo_data['auto_push'])

        # Reconnect signals
        self.auto_pull_checkbox.stateChanged.connect(self._on_form_pull_checkbox_changed)
        self.pull_interval_spinbox.valueChanged.connect(self._on_form_pull_interval_changed)
        self.auto_commit_checkbox.stateChanged.connect(self._on_form_commit_checkbox_changed)
        self.commit_interval_spinbox.valueChanged.connect(self._on_form_commit_interval_changed)
        self.commit_message_input.textChanged.connect(self._on_form_commit_message_changed)
        self.auto_push_checkbox.stateChanged.connect(self._on_form_push_checkbox_changed)
        self.push_interval_spinbox.valueChanged.connect(self._on_form_push_interval_changed)


    def clear_form_and_selection(self):
        """Clears the repository details form and table selection."""
        self.repo_table_widget.clearSelection() # Clear table selection
        self.current_selected_repo_index = -1
        
        self.repo_path_input.clear()
        
        # Disconnect signals before clearing/setting default values
        self.auto_pull_checkbox.stateChanged.disconnect(self._on_form_pull_checkbox_changed)
        self.pull_interval_spinbox.valueChanged.disconnect(self._on_form_pull_interval_changed)
        self.auto_commit_checkbox.stateChanged.disconnect(self._on_form_commit_checkbox_changed)
        self.commit_interval_spinbox.valueChanged.disconnect(self._on_form_commit_interval_changed)
        self.commit_message_input.textChanged.disconnect(self._on_form_commit_message_changed)
        self.auto_push_checkbox.stateChanged.disconnect(self._on_form_push_checkbox_changed)
        self.push_interval_spinbox.valueChanged.disconnect(self._on_form_push_interval_changed)

        self.auto_pull_checkbox.setChecked(False)
        self.pull_interval_spinbox.setValue(5)
        self.pull_interval_spinbox.setEnabled(False) # Ensure disabled when checkbox is unchecked
        
        self.auto_commit_checkbox.setChecked(False)
        self.commit_interval_spinbox.setValue(60)
        self.commit_message_input.setText("Auto-commit from GitBuddy: {timestamp}")
        self.commit_interval_spinbox.setEnabled(False)
        self.commit_message_input.setEnabled(False)
        
        self.auto_push_checkbox.setChecked(False)
        self.push_interval_spinbox.setValue(60)
        self.push_interval_spinbox.setEnabled(False)
        
        self._set_form_enabled(False) # Disable form fields

        # Reconnect signals
        self.auto_pull_checkbox.stateChanged.connect(self._on_form_pull_checkbox_changed)
        self.pull_interval_spinbox.valueChanged.connect(self._on_form_pull_interval_changed)
        self.auto_commit_checkbox.stateChanged.connect(self._on_form_commit_checkbox_changed)
        self.commit_interval_spinbox.valueChanged.connect(self._on_form_commit_interval_changed)
        self.commit_message_input.textChanged.connect(self._on_form_commit_message_changed)
        self.auto_push_checkbox.stateChanged.connect(self._on_form_push_checkbox_changed)
        self.push_interval_spinbox.valueChanged.connect(self._on_form_push_interval_changed)

        self.update() # Force repaint of the form area

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

        # Set default values for a new repository
        new_repo_data = {
            'path': normalized_path,
            'auto_pull': False, # Default to False for new additions
            'pull_interval': 5,
            'auto_commit': False,
            'commit_interval': 60,
            'commit_message_template': "Auto-commit from GitBuddy: {timestamp}",
            'auto_push': False,
            'push_interval': 60
        }

        self.repositories_data.append(new_repo_data)
        self._add_repo_to_table(new_repo_data) # Add to table
        QMessageBox.information(self, "Repository Added", f"Repository '{normalized_path}' added successfully.")
        
        self.clear_form_and_selection() # Clear selection and update buttons
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
        self.clear_form_and_selection() # Clear selection and update buttons
        self.save_configuration()
        QMessageBox.information(self, "Repository Removed", f"Repository '{selected_path}' removed successfully.")


    def save_configuration(self):
        """Saves the current list of repositories (with all their settings) to the configuration file."""
        config_to_save = []
        for repo in self.repositories_data:
            repo_copy = repo.copy()
            # Convert intervals from minutes back to seconds for saving
            repo_copy['pull_interval'] = repo_copy['pull_interval'] * 60
            repo_copy['commit_interval'] = repo_copy['commit_interval'] * 60
            repo_copy['push_interval'] = repo_copy['push_interval'] * 60
            # Exclude runtime-only keys like last_pulled_at, last_pushed_at
            config_to_save.append({k: v for k, v in repo_copy.items() if k not in ['last_pulled_at', 'last_pushed_at', 'last_committed_at']})

        try:
            with open(self.config_file, 'w') as f:
                json.dump(config_to_save, f, indent=4)
            self.repo_config_changed.emit() # Emit signal for other parts of the app (e.g., GitBuddyApp)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save configuration: {e}")
