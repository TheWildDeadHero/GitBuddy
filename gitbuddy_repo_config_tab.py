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

        self.remove_button = QPushButton("Remove Selected") # Changed to self.remove_button
        self.remove_button.setObjectName("removeButton")
        self.remove_button.clicked.connect(self.remove_selected_repository)
        top_action_buttons_layout.addWidget(self.remove_button) # Use self.remove_button here too
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
        self.repo_table_widget.cellChanged.connect(self.handle_table_cell_changed)
        self.repo_table_widget.itemSelectionChanged.connect(self.load_selected_repository_details_into_form) # Changed connection
        layout.addWidget(self.repo_table_widget)

        # Re-added Repository Details/Add/Edit Form
        details_group_box = QGroupBox("Repository Details")
        details_layout = QVBoxLayout(details_group_box)

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

        layout.addWidget(details_group_box)

        # --- Global Action Buttons (Update, Save) ---
        global_action_buttons_layout = QHBoxLayout()
        global_action_buttons_layout.addStretch(1)

        # This button is now less critical as changes are saved on cell/form change
        # but can be kept as a "Force Save All"
        save_all_button = QPushButton("Save All Configuration")
        save_all_button.clicked.connect(self.save_configuration)
        global_action_buttons_layout.addWidget(save_all_button)
        layout.addLayout(global_action_buttons_layout)
        # --- End Global Action Buttons ---

        # Initial state for form and buttons
        self._set_form_enabled(False) # Disable form initially
        self.update_buttons_on_selection()

    def _set_form_enabled(self, enabled):
        """Helper to enable/disable all form fields."""
        self.auto_pull_checkbox.setEnabled(enabled)
        self.pull_interval_spinbox.setEnabled(enabled and self.auto_pull_checkbox.isChecked())
        
        self.auto_commit_checkbox.setEnabled(enabled)
        self.commit_interval_spinbox.setEnabled(enabled and self.auto_commit_checkbox.isChecked())
        self.commit_message_input.setEnabled(enabled and self.auto_commit_checkbox.isChecked())

        self.auto_push_checkbox.setEnabled(enabled)
        self.push_interval_spinbox.setEnabled(enabled and self.auto_push_checkbox.isChecked())

    def _block_form_signals(self, block):
        """Helper to block/unblock signals from form widgets."""
        self.auto_pull_checkbox.blockSignals(block)
        self.pull_interval_spinbox.blockSignals(block)
        self.auto_commit_checkbox.blockSignals(block)
        self.commit_interval_spinbox.blockSignals(block)
        self.commit_message_input.blockSignals(block)
        self.auto_push_checkbox.blockSignals(block)
        self.push_interval_spinbox.blockSignals(block)

    def set_selected_repo_path(self, path):
        """Called by GitBuddyApp to update the selected repository path."""
        self.current_selected_global_repo_path = path
        
        # Attempt to select the item in the table widget if it exists
        found_row_index = -1
        for row in range(self.repo_table_widget.rowCount()):
            item = self.repo_table_widget.item(row, 1) # Column 1 is Path
            if item and item.text() == path:
                found_row_index = row
                # Block signals to prevent handle_table_cell_changed from firing when programmatically selecting
                self.repo_table_widget.blockSignals(True)
                self.repo_table_widget.selectRow(row) # Select the entire row
                self.repo_table_widget.blockSignals(False)
                break
        
        if found_row_index != -1:
            self.current_selected_repo_index = found_row_index
            self.load_selected_repository_details_into_form()
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

    # --- Form field change handlers ---
    def _on_form_pull_checkbox_changed(self, state):
        if self.current_selected_repo_index == -1: return
        self._block_form_signals(True)
        repo_data = self.repositories_data[self.current_selected_repo_index]
        repo_data['auto_pull'] = (state == Qt.Checked)
        self._set_form_enabled(True) # Re-evaluate enabled state of spinbox
        self._update_repo_in_table(self.current_selected_repo_index, repo_data)
        self.save_configuration()
        self._block_form_signals(False)

    def _on_form_pull_interval_changed(self, value):
        if self.current_selected_repo_index == -1: return
        self._block_form_signals(True)
        repo_data = self.repositories_data[self.current_selected_repo_index]
        repo_data['pull_interval'] = value
        self._update_repo_in_table(self.current_selected_repo_index, repo_data)
        self.save_configuration()
        self._block_form_signals(False)

    def _on_form_commit_checkbox_changed(self, state):
        if self.current_selected_repo_index == -1: return
        self._block_form_signals(True)
        repo_data = self.repositories_data[self.current_selected_repo_index]
        repo_data['auto_commit'] = (state == Qt.Checked)
        self._set_form_enabled(True) # Re-evaluate enabled state of spinbox and message
        self._update_repo_in_table(self.current_selected_repo_index, repo_data)
        self.save_configuration()
        self._block_form_signals(False)

    def _on_form_commit_interval_changed(self, value):
        if self.current_selected_repo_index == -1: return
        self._block_form_signals(True)
        repo_data = self.repositories_data[self.current_selected_repo_index]
        repo_data['commit_interval'] = value
        self._update_repo_in_table(self.current_selected_repo_index, repo_data)
        self.save_configuration()
        self._block_form_signals(False)

    def _on_form_commit_message_changed(self, text):
        if self.current_selected_repo_index == -1: return
        self._block_form_signals(True)
        repo_data = self.repositories_data[self.current_selected_repo_index]
        repo_data['commit_message_template'] = text
        self._update_repo_in_table(self.current_selected_repo_index, repo_data)
        self.save_configuration()
        self._block_form_signals(False)

    def _on_form_push_checkbox_changed(self, state):
        if self.current_selected_repo_index == -1: return
        self._block_form_signals(True)
        repo_data = self.repositories_data[self.current_selected_repo_index]
        repo_data['auto_push'] = (state == Qt.Checked)
        self._set_form_enabled(True) # Re-evaluate enabled state of spinbox
        self._update_repo_in_table(self.current_selected_repo_index, repo_data)
        self.save_configuration()
        self._block_form_signals(False)

    def _on_form_push_interval_changed(self, value):
        if self.current_selected_repo_index == -1: return
        self._block_form_signals(True)
        repo_data = self.repositories_data[self.current_selected_repo_index]
        repo_data['push_interval'] = value
        self._update_repo_in_table(self.current_selected_repo_index, repo_data)
        self.save_configuration()
        self._block_form_signals(False)
    # --- End Form field change handlers ---


    def handle_table_cell_changed(self, row, column):
        """Handles changes made directly in the QTableWidget cells."""
        # This signal is blocked when programmatic updates happen from form,
        # but will fire if user directly edits a cell.
        self.repo_table_widget.blockSignals(True)

        selected_path = self.repo_table_widget.item(row, 1).text() # Path is always in column 1
        repo_data = next((r for r in self.repositories_data if r['path'] == selected_path), None)

        if not repo_data:
            QMessageBox.critical(self, "Data Error", "Could not find repository data for the edited row.")
            self.repo_table_widget.blockSignals(False)
            return

        new_value_str = self.repo_table_widget.item(row, column).text().strip()

        try:
            if column == 2: # Auto Pull (min)
                if new_value_str.lower() == "disabled":
                    repo_data['auto_pull'] = False
                    repo_data['pull_interval'] = 0
                else:
                    interval = int(new_value_str)
                    if interval <= 0:
                        raise ValueError("Interval must be a positive integer.")
                    repo_data['auto_pull'] = True
                    repo_data['pull_interval'] = interval
                self.repo_table_widget.item(row, column).setText(str(repo_data['pull_interval']) if repo_data['auto_pull'] else "Disabled")
            
            elif column == 3: # Auto Commit (min)
                if new_value_str.lower() == "disabled":
                    repo_data['auto_commit'] = False
                    repo_data['commit_interval'] = 0
                else:
                    interval = int(new_value_str)
                    if interval <= 0:
                        raise ValueError("Interval must be a positive integer.")
                    repo_data['auto_commit'] = True
                    repo_data['commit_interval'] = interval
                self.repo_table_widget.item(row, column).setText(str(repo_data['commit_interval']) if repo_data['auto_commit'] else "Disabled")

            elif column == 4: # Commit Message
                repo_data['commit_message_template'] = new_value_str
                self.repo_table_widget.item(row, column).setText(new_value_str) # Ensure consistent display

            elif column == 5: # Auto Push (min)
                if new_value_str.lower() == "disabled":
                    repo_data['auto_push'] = False
                    repo_data['push_interval'] = 0
                else:
                    interval = int(new_value_str)
                    if interval <= 0:
                        raise ValueError("Interval must be a positive integer.")
                    repo_data['auto_push'] = True
                    repo_data['push_interval'] = interval
                self.repo_table_widget.item(row, column).setText(str(repo_data['push_interval']) if repo_data['auto_push'] else "Disabled")

            # After updating data from table, update the form if this row is selected
            if row == self.current_selected_repo_index:
                self._block_form_signals(True) # Block form signals to prevent re-triggering table update
                self._populate_form_from_repo_data(repo_data)
                self._block_form_signals(False)

        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", f"Invalid value for column '{self.repo_table_widget.horizontalHeaderItem(column).text()}': {e}\n"
                                 "Please enter a positive integer or 'Disabled'.")
            # Revert to original value in table cell
            original_repo_data = next((r for r in self.repositories_data if r['path'] == selected_path), None)
            if original_repo_data:
                if column == 2: # Auto Pull
                    self.repo_table_widget.item(row, column).setText(str(original_repo_data['pull_interval']) if original_repo_data['auto_pull'] else "Disabled")
                elif column == 3: # Auto Commit
                    self.repo_table_widget.item(row, column).setText(str(original_repo_data['commit_interval']) if original_repo_data['auto_commit'] else "Disabled")
                elif column == 4: # Commit Message
                    self.repo_table_widget.item(row, column).setText(original_repo_data['commit_message_template'])
                elif column == 5: # Auto Push
                    self.repo_table_widget.item(row, column).setText(str(original_repo_data['push_interval']) if original_repo_data['auto_push'] else "Disabled")
        finally:
            self.repo_table_widget.blockSignals(False)
            self.save_configuration() # Save configuration after each valid cell change

    def load_repositories_to_list(self):
        """Loads repository data from the config file and populates the QTableWidget."""
        # Temporarily block signals to prevent handle_table_cell_changed from firing during load
        self.repo_table_widget.blockSignals(True)
        self.repo_table_widget.setRowCount(0) # Clear existing rows
        self.repositories_data = []

        if not os.path.exists(self.config_file):
            self.repo_table_widget.blockSignals(False)
            return

        try:
            with open(self.config_file, 'r') as f:
                repos_config = json.load(f)
                if not isinstance(repos_config, list):
                    QMessageBox.warning(self, "Configuration Error",
                                        f"Configuration file '{self.config_file}' is malformed. Expected a list.")
                    self.repo_table_widget.blockSignals(False)
                    return
                
                for entry in repos_config:
                    if isinstance(entry, dict) and 'path' in entry:
                        repo_data = {
                            'path': entry['path'],
                            'auto_pull': entry.get('auto_pull', True),
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


    def _add_repo_to_table(self, repo_data):
        """Helper to add a single repository's data to the QTableWidget."""
        row_position = self.repo_table_widget.rowCount()
        self.repo_table_widget.insertRow(row_position)

        repo_name = os.path.basename(repo_data['path'])

        # Name column (Non-editable)
        name_item = QTableWidgetItem(repo_name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        self.repo_table_widget.setItem(row_position, 0, name_item)

        # Path column (Non-editable)
        path_item = QTableWidgetItem(repo_data['path'])
        path_item.setFlags(path_item.flags() & ~Qt.ItemIsEditable)
        self.repo_table_widget.setItem(row_position, 1, path_item)
        
        # Auto Pull column
        pull_text = str(repo_data['pull_interval']) if repo_data['auto_pull'] else "Disabled"
        self.repo_table_widget.setItem(row_position, 2, QTableWidgetItem(pull_text))
        
        # Auto Commit column
        commit_text = str(repo_data['commit_interval']) if repo_data['auto_commit'] else "Disabled"
        self.repo_table_widget.setItem(row_position, 3, QTableWidgetItem(commit_text))

        # Commit Message column
        self.repo_table_widget.setItem(row_position, 4, QTableWidgetItem(repo_data['commit_message_template']))
        
        # Auto Push column
        push_text = str(repo_data['push_interval']) if repo_data['auto_push'] else "Disabled"
        self.repo_table_widget.setItem(row_position, 5, QTableWidgetItem(push_text))

    def _update_repo_in_table(self, row, repo_data):
        """Helper to update a single repository's data in the QTableWidget."""
        # Temporarily block signals to prevent handle_table_cell_changed from firing during programmatic update
        self.repo_table_widget.blockSignals(True)

        repo_name = os.path.basename(repo_data['path'])
        # Update Name and Path, ensuring they remain non-editable
        name_item = self.repo_table_widget.item(row, 0)
        if name_item:
            name_item.setText(repo_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        else: # Create if it doesn't exist (shouldn't happen in update)
            name_item = QTableWidgetItem(repo_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.repo_table_widget.setItem(row, 0, name_item)

        path_item = self.repo_table_widget.item(row, 1)
        if path_item:
            path_item.setText(repo_data['path'])
            path_item.setFlags(path_item.flags() & ~Qt.ItemIsEditable)
        else: # Create if it doesn't exist
            path_item = QTableWidgetItem(repo_data['path'])
            path_item.setFlags(path_item.flags() & ~Qt.ItemIsEditable)
            self.repo_table_widget.setItem(row, 1, path_item)
        
        # Auto Pull column
        pull_text = str(repo_data['pull_interval']) if repo_data['auto_pull'] else "Disabled"
        self.repo_table_widget.item(row, 2).setText(pull_text)
        
        # Auto Commit column
        commit_text = str(repo_data['commit_interval']) if repo_data['auto_commit'] else "Disabled"
        self.repo_table_widget.item(row, 3).setText(commit_text)

        # Commit Message column
        self.repo_table_widget.item(row, 4).setText(repo_data['commit_message_template'])
        
        # Auto Push column
        push_text = str(repo_data['push_interval']) if repo_data['auto_push'] else "Disabled"
        self.repo_table_widget.item(row, 5).setText(push_text)

        self.repo_table_widget.blockSignals(False)


    def load_selected_repository_details_into_form(self):
        """Loads details of the selected repository from the table into the form fields."""
        selected_rows = self.repo_table_widget.selectedIndexes()
        if not selected_rows:
            self.current_selected_repo_index = -1
            self.clear_form_and_selection()
            return

        selected_row = selected_rows[0].row()
        self.current_selected_repo_index = selected_row
        selected_path = self.repo_table_widget.item(selected_row, 1).text()
        
        repo_data = next((r for r in self.repositories_data if r['path'] == selected_path), None)

        if repo_data:
            self._set_form_enabled(True)
            self._block_form_signals(True) # Block signals before populating to avoid re-triggering updates

            self.repo_path_input.setText(repo_data['path'])
            self._populate_form_from_repo_data(repo_data)

            self._block_form_signals(False)
        else:
            self.current_selected_repo_index = -1
            self.clear_form_and_selection()


    def _populate_form_from_repo_data(self, repo_data):
        """Helper to populate form fields from a repo_data dictionary."""
        self.auto_pull_checkbox.setChecked(repo_data['auto_pull'])
        self.pull_interval_spinbox.setValue(repo_data['pull_interval'])
        
        self.auto_commit_checkbox.setChecked(repo_data['auto_commit'])
        self.commit_interval_spinbox.setValue(repo_data['commit_interval'])
        self.commit_message_input.setText(repo_data['commit_message_template'])
        
        self.auto_push_checkbox.setChecked(repo_data['auto_push'])
        self.push_interval_spinbox.setValue(repo_data['push_interval'])

        # Ensure correct enabled state after setting values
        self.pull_interval_spinbox.setEnabled(repo_data['auto_pull'])
        self.commit_interval_spinbox.setEnabled(repo_data['auto_commit'])
        self.commit_message_input.setEnabled(repo_data['auto_commit'])
        self.push_interval_spinbox.setEnabled(repo_data['auto_push'])


    def clear_form_and_selection(self):
        """Clears the repository details form and table selection."""
        self.repo_table_widget.clearSelection() # Clear table selection
        self.current_selected_repo_index = -1
        
        self._block_form_signals(True) # Block signals before clearing to avoid re-triggering updates

        self.repo_path_input.clear()
        
        self.auto_pull_checkbox.setChecked(False)
        self.pull_interval_spinbox.setValue(5)
        
        self.auto_commit_checkbox.setChecked(False)
        self.commit_interval_spinbox.setValue(60)
        self.commit_message_input.setText("Auto-commit from GitBuddy: {timestamp}")
        
        self.auto_push_checkbox.setChecked(False)
        self.push_interval_spinbox.setValue(60)
        
        self._set_form_enabled(False) # Disable form fields
        self._block_form_signals(False)


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

    def update_selected_repository(self):
        """This method is now largely redundant as changes are saved on cell/form change."""
        QMessageBox.information(self, "Info", "Changes are automatically saved when you modify values in the table or form.")


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
