# gitbuddy_app.py

import sys
import os
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QDir, Signal

# Import all tab widgets
from gitbuddy_service_manager_tab import ServiceManagerTab
from gitbuddy_repo_config_tab import RepoConfigTab
from gitbuddy_current_branch_tab import CurrentBranchTab
from gitbuddy_merge_tab import MergeTab
from gitbuddy_bisect_tab import BisectTab
from gitbuddy_git_settings_tab import GitSettingsTab # New import

# Define the base configuration directory
CONFIG_DIR = os.path.expanduser("~/.config/git-buddy")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
os.makedirs(CONFIG_DIR, exist_ok=True) # Ensure it exists

class GitBuddyApp(QMainWindow):
    # Define a signal that will be emitted when the global repository path changes
    global_repo_path_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GitBuddy")
        self.setGeometry(100, 100, 900, 750) # Adjusted size for tabbed interface

        self.init_ui()
        self.load_configured_repos_to_selector() # Load repos into the dropdown on startup

    def init_ui(self):
        """Initializes the main application UI with global repo selector and tabs."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0) # Tabs handle their own margins

        # Removed all custom QSS styling to allow native rendering
        self.setStyleSheet("") # Set an empty stylesheet

        # --- Global Repository Selection UI ---
        repo_selection_layout = QHBoxLayout()
        repo_selection_layout.setContentsMargins(10, 10, 10, 10)
        repo_selection_layout.setSpacing(10)

        repo_selection_layout.addWidget(QLabel("Selected Repository:"))

        self.repo_selector_combobox = QComboBox()
        self.repo_selector_combobox.setMinimumWidth(200)
        self.repo_selector_combobox.currentIndexChanged.connect(self.on_repo_selection_changed)
        repo_selection_layout.addWidget(self.repo_selector_combobox)

        self.global_repo_path_input = QLineEdit()
        self.global_repo_path_input.setPlaceholderText("Path to selected Git repository")
        self.global_repo_path_input.setReadOnly(True) # Initially read-only
        self.global_repo_path_input.textChanged.connect(self.on_global_repo_path_input_changed)
        repo_selection_layout.addWidget(self.global_repo_path_input)

        self.global_browse_button = QPushButton("Browse...")
        self.global_browse_button.clicked.connect(self.browse_global_repository)
        self.global_browse_button.setEnabled(False) # Initially disabled
        repo_selection_layout.addWidget(self.global_browse_button)

        main_layout.addLayout(repo_selection_layout)
        # --- End Global Repository Selection UI ---

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create instances of our tab widgets
        self.current_branch_tab = CurrentBranchTab()
        self.repo_config_tab = RepoConfigTab(CONFIG_DIR)
        self.merge_tab = MergeTab()
        self.bisect_tab = BisectTab()
        self.service_manager_tab = ServiceManagerTab(CONFIG_DIR)
        self.git_settings_tab = GitSettingsTab(CONFIG_DIR) # Pass CONFIG_DIR to GitSettingsTab

        # Connect the global signal to each tab's update method
        self.global_repo_path_changed.connect(self.current_branch_tab.set_selected_repo_path)
        self.global_repo_path_changed.connect(self.repo_config_tab.set_selected_repo_path)
        self.global_repo_path_changed.connect(self.merge_tab.set_selected_repo_path)
        self.global_repo_path_changed.connect(self.bisect_tab.set_selected_repo_path)
        # GitSettingsTab doesn't directly use a selected repo path, so no connection needed for set_selected_repo_path.

        # Connect RepoConfigTab's signal to refresh the global combobox
        self.repo_config_tab.repo_config_changed.connect(self.load_configured_repos_to_selector)

        # Add tabs to the QTabWidget in the specified order
        self.tab_widget.addTab(self.current_branch_tab, "Current Branch")
        self.tab_widget.addTab(self.repo_config_tab, "Repository Configurator")
        self.tab_widget.addTab(self.merge_tab, "Merge")
        self.tab_widget.addTab(self.bisect_tab, "Bisect")
        self.tab_widget.addTab(self.git_settings_tab, "Git Settings") # Add new tab
        self.tab_widget.addTab(self.service_manager_tab, "Service Manager")

    def load_configured_repos_to_selector(self):
        """Loads repository paths from config.json and populates the combobox."""
        current_selected_path = self.global_repo_path_input.text()
        
        # Disconnect to prevent triggering on_repo_selection_changed during repopulation
        self.repo_selector_combobox.currentIndexChanged.disconnect(self.on_repo_selection_changed)
        self.repo_selector_combobox.clear()

        configured_paths = []
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    repos_config = json.load(f)
                    if isinstance(repos_config, list):
                        for entry in repos_config:
                            if isinstance(entry, dict) and 'path' in entry:
                                configured_paths.append(entry['path'])
            except json.JSONDecodeError:
                QMessageBox.warning(self, "Config Load Error", "Could not load repository configuration. File might be corrupted.")
                pass # Handle corrupted config gracefully

        for path in configured_paths:
            repo_name = os.path.basename(path) # Get only the directory name
            self.repo_selector_combobox.addItem(repo_name, path) # Store full path as itemData
        
        self.repo_selector_combobox.addItem("-- Other (Manual Path) --", "") # Option for non-configured repos, empty data

        # Attempt to restore previous selection or set a default
        index_to_select = -1
        if current_selected_path:
            # Try to find by stored data (full path)
            index_to_select = self.repo_selector_combobox.findData(current_selected_path)
        
        if index_to_select != -1:
            self.repo_selector_combobox.setCurrentIndex(index_to_select)
            # Ensure global_repo_path_input is correctly set if it was a configured repo
            self.global_repo_path_input.setText(current_selected_path)
            self.global_repo_path_input.setReadOnly(True)
            self.global_browse_button.setEnabled(False)
        elif configured_paths:
            # If previous path not found, but there are configured paths, select the first one
            self.repo_selector_combobox.setCurrentIndex(0)
            self.global_repo_path_input.setText(self.repo_selector_combobox.currentData())
            self.global_repo_path_input.setReadOnly(True)
            self.global_browse_button.setEnabled(False)
        else:
            # If no configured paths, or previous path not found, select "Other"
            self.repo_selector_combobox.setCurrentIndex(self.repo_selector_combobox.count() - 1)
            self.global_repo_path_input.clear()
            self.global_repo_path_input.setReadOnly(False)
            self.global_browse_button.setEnabled(True)
            self.global_repo_path_input.setFocus()

        # Reconnect the signal
        self.repo_selector_combobox.currentIndexChanged.connect(self.on_repo_selection_changed)

        # Manually trigger the update for the initial state
        self.on_repo_selection_changed(self.repo_selector_combobox.currentIndex())


    def on_repo_selection_changed(self, index):
        """Handles changes in the repository selection combobox."""
        selected_display_text = self.repo_selector_combobox.currentText()

        if selected_display_text == "-- Other (Manual Path) --":
            self.global_repo_path_input.clear()
            self.global_repo_path_input.setReadOnly(False)
            self.global_browse_button.setEnabled(True)
            self.global_repo_path_input.setFocus()
            self.global_repo_path_changed.emit("")
        else:
            selected_full_path = self.repo_selector_combobox.currentData()
            self.global_repo_path_input.setText(selected_full_path)
            self.global_repo_path_input.setReadOnly(True)
            self.global_browse_button.setEnabled(False)
            self.global_repo_path_changed.emit(selected_full_path)

    def on_global_repo_path_input_changed(self, text):
        """Handles manual changes in the global repository path input."""
        if not self.global_repo_path_input.isReadOnly():
            self.global_repo_path_changed.emit(text)

    def browse_global_repository(self):
        """Opens a file dialog to select a repository for the global selector."""
        initial_path = self.global_repo_path_input.text() if self.global_repo_path_input.text() else QDir.homePath()
        directory = QFileDialog.getExistingDirectory(self, "Select Git Repository Directory", initial_path)
        if directory:
            if os.path.isdir(os.path.join(directory, ".git")):
                self.global_repo_path_input.setText(directory)
            else:
                QMessageBox.warning(self, "Not a Git Repository",
                                    f"The selected directory '{directory}' does not appear to be a Git repository (missing .git folder).")
                self.global_repo_path_input.clear()
                self.global_repo_path_changed.emit("")
