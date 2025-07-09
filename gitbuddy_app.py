# gitbuddy_app.py

import sys
import os
import json
import subprocess
import logging
import time
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton, QFileDialog,
    QMessageBox, QSystemTrayIcon, QMenu, QStyle, QCheckBox, QGroupBox
)
from PySide6.QtCore import Qt, QDir, Signal, QTimer
from PySide6.QtGui import QIcon, QAction

# Import all tab widgets
from gitbuddy_repo_config_tab import RepoConfigTab
from gitbuddy_current_branch_tab import CurrentBranchTab
from gitbuddy_merge_tab import MergeTab
from gitbuddy_bisect_tab import BisectTab
from gitbuddy_git_settings_tab import GitSettingsTab

# Define the base configuration directory
CONFIG_DIR = os.path.expanduser("~/.config/git-buddy")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json") # Consolidated config file
GIT_ACCOUNTS_FILE = os.path.join(CONFIG_DIR, "git_accounts.json") # Define git_accounts.json path
LOG_FILE = os.path.join(CONFIG_DIR, "git_buddy.log") # Log file for integrated functions
os.makedirs(CONFIG_DIR, exist_ok=True) # Ensure it exists

# Set up logging for the main application
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler() # This sends logs to stderr, which systemd captures
    ]
)

class GitBuddyApp(QMainWindow):
    # Define a signal that will be emitted when the global repository path changes
    global_repo_path_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GitBuddy")
        self.setGeometry(100, 100, 900, 750) # Adjusted size for tabbed interface

        # Set the application icon
        # Ensure 'icon.png' is in the same directory as this script,
        # or provide a full path to the icon file.
        self.setWindowIcon(QIcon("icon.png"))

        # Centralized application state
        self.app_state = {
            'repositories': [],
            'git_accounts': [],
            'global_pause_pull': False,
            'global_pause_commit': False,
            'global_pause_push': False,
            'auto_start_ssh_agent': False,
        }

        self.load_app_state() # Load initial application state from config file

        self.init_ui()
        self.setup_tray_icon()
        self.load_configured_repos_to_selector() # Populate global repo selector

        # If auto-start SSH agent is enabled, try to start it on launch
        if self.app_state['auto_start_ssh_agent']:
            logging.info("Auto-start SSH Agent is enabled. Attempting to start SSH agent...")
            # Call the start_ssh_agent method on the git_settings_tab instance
            # as it contains the subprocess logic for starting the agent.
            if hasattr(self, 'git_settings_tab') and self.git_settings_tab.git_installed:
                 self.git_settings_tab.start_ssh_agent()
            else:
                logging.warning("GitSettingsTab not ready or Git not installed. Cannot auto-start SSH agent.")


        # Setup periodic sync timer
        self.periodic_sync_timer = QTimer(self)
        # The interval for the main application's timer. This defines how often
        # the application checks if any repositories are due for pull/commit/push.
        self.periodic_sync_timer.setInterval(30 * 1000) # Check every 30 seconds
        self.periodic_sync_timer.timeout.connect(self.perform_periodic_sync)
        self.periodic_sync_timer.start()
        logging.info("GitBuddy periodic sync timer started.")

    def init_ui(self):
        """Initializes the main application UI with global repo selector and tabs."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0) # Tabs handle their own margins

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

        # --- Global Pause Controls ---
        global_pause_group = QGroupBox("Global Auto-Sync Pause Controls")
        global_pause_layout = QHBoxLayout(global_pause_group)
        global_pause_layout.setContentsMargins(10, 10, 10, 10)
        global_pause_layout.setSpacing(15)

        self.pause_pull_checkbox = QCheckBox("Pause All Auto Pulls")
        # Corrected: Use isChecked() to get the boolean state
        self.pause_pull_checkbox.setChecked(self.app_state['global_pause_pull'])
        self.pause_pull_checkbox.stateChanged.connect(lambda: self.set_global_pause('pull', self.pause_pull_checkbox.isChecked()))
        global_pause_layout.addWidget(self.pause_pull_checkbox)

        self.pause_commit_checkbox = QCheckBox("Pause All Auto Commits")
        # Corrected: Use isChecked() to get the boolean state
        self.pause_commit_checkbox.setChecked(self.app_state['global_pause_commit'])
        self.pause_commit_checkbox.stateChanged.connect(lambda: self.set_global_pause('commit', self.pause_commit_checkbox.isChecked()))
        global_pause_layout.addWidget(self.pause_commit_checkbox)

        self.pause_push_checkbox = QCheckBox("Pause All Auto Pushes")
        # Corrected: Use isChecked() to get the boolean state
        self.pause_push_checkbox.setChecked(self.app_state['global_pause_push'])
        self.pause_push_checkbox.stateChanged.connect(lambda: self.set_global_pause('push', self.pause_push_checkbox.isChecked()))
        global_pause_layout.addWidget(self.pause_push_checkbox)
        
        global_pause_layout.addStretch(1) # Pushes checkboxes to the left

        main_layout.addWidget(global_pause_group)
        # --- End Global Pause Controls ---

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create instances of our tab widgets
        self.current_branch_tab = CurrentBranchTab()
        # Pass initial repositories data to RepoConfigTab
        self.repo_config_tab = RepoConfigTab(self.app_state['repositories'], self) 
        self.merge_tab = MergeTab()
        self.bisect_tab = BisectTab()
        # Pass initial git_accounts_data and auto_start_ssh_agent to GitSettingsTab
        self.git_settings_tab = GitSettingsTab(
            git_accounts_initial=self.app_state['git_accounts'],
            auto_start_ssh_agent_initial=self.app_state['auto_start_ssh_agent'],
            parent=self # Pass self as parent
        )

        # Connect the global signal to each tab's update method
        self.global_repo_path_changed.connect(self.current_branch_tab.set_selected_repo_path)
        self.global_repo_path_changed.connect(self.repo_config_tab.set_selected_repo_path)
        self.global_repo_path_changed.connect(self.merge_tab.set_selected_repo_path)
        self.global_repo_path_changed.connect(self.bisect_tab.set_selected_repo_path)

        # Connect RepoConfigTab's signal to refresh the global combobox AND the internal repo data
        self.repo_config_tab.repo_config_changed.connect(self.update_repositories_data)
        # Connect GitSettingsTab's signal to refresh Git accounts data in GitBuddyApp
        self.git_settings_tab.git_accounts_changed.connect(self.update_git_accounts_data)
        # New: Connect GitSettingsTab's auto_start_ssh_agent_setting_changed signal
        self.git_settings_tab.auto_start_ssh_agent_setting_changed.connect(self.set_auto_start_ssh_agent)


        # Add tabs to the QTabWidget in the specified order
        self.tab_widget.addTab(self.current_branch_tab, "Current Branch")
        self.tab_widget.addTab(self.repo_config_tab, "Repository Configurator")
        self.tab_widget.addTab(self.merge_tab, "Merge")
        self.tab_widget.addTab(self.bisect_tab, "Bisect")
        self.tab_widget.addTab(self.git_settings_tab, "Git Settings")

    def setup_tray_icon(self):
        """Sets up the system tray icon and its context menu."""
        self.tray_icon = QSystemTrayIcon(self)
        # Set the tray icon
        # Ensure 'icon.png' is in the same directory as this script,
        # or provide a full path to the icon file.
        self.setWindowIcon(QIcon("icon.png")) # Use setWindowIcon for the main window
        self.tray_icon.setIcon(QIcon("icon.png")) # Set icon for the tray
        self.tray_icon.setToolTip("GitBuddy: Auto Git Sync")

        # Create context menu
        self.tray_menu = QMenu()
        self.tray_menu.aboutToShow.connect(self.update_tray_menu_state) # Connect to update state before showing

        # Add actions to the tray menu
        show_hide_action = QAction("Show/Hide GitBuddy", self)
        show_hide_action.triggered.connect(self.show_hide_window)
        self.tray_menu.addAction(show_hide_action)
        self.tray_menu.addSeparator()

        # Global Pause Actions
        self.action_pause_pull = QAction("Pause All Auto Pulls", self)
        self.action_pause_pull.setCheckable(True)
        self.action_pause_pull.triggered.connect(lambda checked: self.set_global_pause('pull', checked))
        self.tray_menu.addAction(self.action_pause_pull)

        self.action_pause_commit = QAction("Pause All Auto Commits", self)
        self.action_pause_commit.setCheckable(True)
        self.action_pause_commit.triggered.connect(lambda checked: self.set_global_pause('commit', checked))
        self.tray_menu.addAction(self.action_pause_commit)

        self.action_pause_push = QAction("Pause All Auto Pushes", self)
        self.action_pause_push.setCheckable(True)
        self.action_pause_push.triggered.connect(lambda checked: self.set_global_pause('push', checked))
        self.tray_menu.addAction(self.action_pause_push)
        self.tray_menu.addSeparator()

        exit_action = QAction("Exit GitBuddy", self)
        exit_action.triggered.connect(self.exit_application)
        self.tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated) # For double-click
        self.tray_icon.show()

    def update_tray_menu_state(self):
        """Updates the checked state of the pause menu items before the tray menu is shown."""
        self.action_pause_pull.setChecked(self.app_state['global_pause_pull'])
        self.action_pause_commit.setChecked(self.app_state['global_pause_commit'])
        self.action_pause_push.setChecked(self.app_state['global_pause_push'])

    def on_tray_icon_activated(self, reason):
        """Handles activation of the tray icon (e.g., double-click)."""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_hide_window()

    def show_hide_window(self):
        """Toggles the visibility of the main window."""
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()

    def exit_application(self):
        """Closes the application cleanly."""
        reply = QMessageBox.question(self, "Exit GitBuddy",
                                     "Are you sure you want to exit GitBuddy?\n"
                                     "Automatic sync functions will stop.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return
        
        # Stop SSH Agent if it was auto-started and is running
        if self.app_state['auto_start_ssh_agent'] and hasattr(self, 'git_settings_tab') and self.git_settings_tab.git_installed:
            # Check if agent is actually running before attempting to stop
            if "SSH_AUTH_SOCK" in os.environ and os.path.exists(os.environ["SSH_AUTH_SOCK"]):
                self.git_settings_tab.stop_ssh_agent()

        self.tray_icon.hide() # Hide tray icon before quitting
        QApplication.quit()

    def closeEvent(self, event):
        """Overrides the close event to minimize to tray."""
        if self.tray_icon.isVisible():
            self.hide()
            self.tray_icon.showMessage(
                "GitBuddy",
                "GitBuddy is minimized to tray. Click icon to restore or right-click to exit.",
                QSystemTrayIcon.Information,
                2000
            )
            event.ignore() # Do not close the application
        else:
            # If for some reason tray icon is not visible, allow normal close
            event.accept()

    def load_configured_repos_to_selector(self):
        """Loads repository paths from config.json and populates the combobox."""
        current_selected_path = self.global_repo_path_input.text()
        
        # Disconnect to prevent triggering on_repo_selection_changed during repopulation
        self.repo_selector_combobox.currentIndexChanged.disconnect(self.on_repo_selection_changed)
        self.repo_selector_combobox.clear()

        configured_paths = []
        for entry in self.app_state['repositories']:
            configured_paths.append(entry['path'])
        
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

    def set_global_pause(self, task_type, paused):
        """Sets the global pause state for a specific task type and saves it."""
        self.app_state[f'global_pause_{task_type}'] = paused
        # Update GUI checkbox (already handled by signal connection, but explicit for clarity)
        if task_type == 'pull':
            self.pause_pull_checkbox.setChecked(paused)
        elif task_type == 'commit':
            self.pause_commit_checkbox.setChecked(paused)
        elif task_type == 'push':
            self.pause_push_checkbox.setChecked(paused)
        self.save_app_state() # Save the updated global pause settings
        logging.info(f"Global pause for {task_type} set to {paused}.")

    def set_auto_start_ssh_agent(self, enable: bool):
        """
        Slot to handle the auto-start SSH agent setting change from GitSettingsTab.
        Updates the global setting and triggers SSH agent start/stop if applicable.
        """
        logging.info(f"Received auto-start SSH agent setting: {enable}")
        self.app_state['auto_start_ssh_agent'] = enable
        self.save_app_state() # Save the updated setting

        # Now, instruct the GitSettingsTab to manage the SSH agent based on this setting
        # This ensures the GitSettingsTab's internal logic for starting/stopping is used.
        if hasattr(self, 'git_settings_tab') and self.git_settings_tab.git_installed:
            if enable:
                self.git_settings_tab.start_ssh_agent()
            else:
                self.git_settings_tab.stop_ssh_agent()
        else:
            logging.warning("GitSettingsTab not ready or Git not installed. Cannot manage SSH agent.")

    def save_app_state(self):
        """Saves the entire application configuration to the main config file."""
        config_to_save = {
            'global_pause_pull': self.app_state['global_pause_pull'],
            'global_pause_commit': self.app_state['global_pause_commit'],
            'global_pause_push': self.app_state['global_pause_push'],
            'auto_start_ssh_agent': self.app_state['auto_start_ssh_agent'],
            'repositories': [], # This will be populated from self.app_state['repositories']
            'git_accounts': self.app_state['git_accounts'] # Save git accounts
        }

        for repo in self.app_state['repositories']:
            repo_copy = repo.copy()
            # Convert intervals from minutes back to seconds for saving
            repo_copy['pull_interval'] = repo_copy.get('pull_interval', 0)
            repo_copy['commit_interval'] = repo_copy.get('commit_interval', 0)
            repo_copy['push_interval'] = repo_copy.get('push_interval', 0)
            # Exclude runtime-only keys like last_pulled_at, last_pushed_at, last_committed_at
            config_to_save['repositories'].append({k: v for k, v in repo_copy.items() if k not in ['last_pulled_at', 'last_pushed_at', 'last_committed_at']})

        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config_to_save, f, indent=4)
            logging.info(f"Application configuration saved to {CONFIG_FILE}.")
        except Exception as e:
            logging.error(f"Failed to save application configuration: {e}")

    def load_app_state(self):
        """
        Loads the entire application configuration from the main config file.
        Initializes global pause settings, auto_start_ssh_agent, and repository data.
        """
        if not os.path.exists(CONFIG_FILE):
            logging.warning(f"Application configuration file not found: {CONFIG_FILE}. Initializing defaults.")
            # self.app_state already has defaults
            return

        try:
            with open(CONFIG_FILE, 'r') as f:
                full_config = json.load(f)

                if not isinstance(full_config, dict):
                    logging.error(f"Application configuration file {CONFIG_FILE} is malformed. Expected a dictionary. Using default state.")
                    # Keep default app_state
                    return

                # Load global pause settings
                self.app_state['global_pause_pull'] = full_config.get('global_pause_pull', False)
                self.app_state['global_pause_commit'] = full_config.get('global_pause_commit', False)
                self.app_state['global_pause_push'] = full_config.get('global_pause_push', False)
                self.app_state['auto_start_ssh_agent'] = full_config.get('auto_start_ssh_agent', False)

                repos_config = full_config.get('repositories', [])
                if not isinstance(repos_config, list):
                    logging.error(f"Repositories section in {CONFIG_FILE} is malformed. Expected a list.")
                    self.app_state['repositories'] = []
                    return

                new_repositories_data = []
                for entry in repos_config:
                    if not isinstance(entry, dict) or 'path' not in entry:
                        logging.warning(f"Malformed repository entry: {entry}. Skipping.")
                        continue

                    repo_path = entry['path']
                    
                    auto_pull = entry.get('auto_pull', False)
                    pull_interval = entry.get('pull_interval', 300) # Default 300 seconds (5 min)
                    auto_commit = entry.get('auto_commit', False)
                    commit_interval = entry.get('commit_interval', 3600) # Default 3600 seconds (60 min)
                    commit_message_template = entry.get('commit_message_template', "Auto-commit from GitBuddy: {timestamp}")
                    auto_push = entry.get('auto_push', False)
                    push_interval = entry.get('push_interval', 3600) # Default 3600 seconds (60 min)

                    # Validate intervals (ensure they are at least 1 second)
                    pull_interval = max(1, pull_interval)
                    commit_interval = max(1, commit_interval)
                    push_interval = max(1, push_interval)

                    # Initialize with datetime.min for runtime tracking
                    new_repositories_data.append({
                        'path': repo_path,
                        'auto_pull': auto_pull,
                        'pull_interval': pull_interval,
                        'last_pulled_at': datetime.min,
                        'auto_commit': auto_commit,
                        'commit_interval': commit_interval,
                        'last_committed_at': datetime.min,
                        'commit_message_template': commit_message_template,
                        'auto_push': auto_push,
                        'push_interval': push_interval,
                        'last_pushed_at': datetime.min
                    })
                self.app_state['repositories'] = new_repositories_data
                
                # Load Git accounts data
                git_accounts_config = full_config.get('git_accounts', [])
                if not isinstance(git_accounts_config, list):
                    logging.error(f"Git accounts section in {CONFIG_FILE} is malformed. Expected a list.")
                    self.app_state['git_accounts'] = []
                else:
                    self.app_state['git_accounts'] = git_accounts_config

                logging.info(f"Loaded {len(self.app_state['repositories'])} repositories and {len(self.app_state['git_accounts'])} Git accounts for periodic sync.")
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from {CONFIG_FILE}: {e}")
            # Keep default app_state
        except Exception as e:
            logging.error(f"An unexpected error occurred while loading app config: {e}")
            # Keep default app_state

        # After loading, update the UI checkboxes if they exist (will be called before init_ui for initial load,
        # so these might not exist yet. The init_ui will set them based on self.app_state)
        if hasattr(self, 'pause_pull_checkbox'):
            self.pause_pull_checkbox.setChecked(self.app_state['global_pause_pull'])
            self.pause_commit_checkbox.setChecked(self.app_state['global_pause_commit'])
            self.pause_push_checkbox.setChecked(self.app_state['global_pause_push'])

    def update_repositories_data(self, new_repos_data):
        """
        Slot to receive notification from RepoConfigTab that its internal data has changed.
        This method will update GitBuddyApp's master repositories_data and save the config.
        It also preserves runtime timestamps.
        """
        logging.info("Received repo_config_changed signal. Updating central repositories data.")
        # Create a new list for self.app_state['repositories']
        updated_repos_with_timestamps = []
        for new_repo in new_repos_data:
            # Find the corresponding old repo to preserve timestamps
            existing_repo = next((r for r in self.app_state['repositories'] if r['path'] == new_repo['path']), None)
            
            if existing_repo:
                # Preserve existing runtime timestamps
                merged_repo = {
                    **new_repo,
                    'last_pulled_at': existing_repo.get('last_pulled_at', datetime.min),
                    'last_committed_at': existing_repo.get('last_committed_at', datetime.min),
                    'last_pushed_at': existing_repo.get('last_pushed_at', datetime.min)
                }
                updated_repos_with_timestamps.append(merged_repo)
            else:
                # New repository, initialize timestamps
                new_repo_with_timestamps = {
                    **new_repo,
                    'last_pulled_at': datetime.min,
                    'last_committed_at': datetime.min,
                    'last_pushed_at': datetime.min
                }
                updated_repos_with_timestamps.append(new_repo_with_timestamps)
        
        self.app_state['repositories'] = updated_repos_with_timestamps
        self.save_app_state()
        self.load_configured_repos_to_selector() # Refresh the global combobox
        self.update_all_tabs_data() # Ensure all tabs are synchronized

    def update_git_accounts_data(self, new_accounts_data):
        """
        Slot to receive notification from GitSettingsTab that its internal data has changed.
        This method will update GitBuddyApp's master git_accounts_data and save it.
        """
        logging.info("Received git_accounts_changed signal. Updating central Git accounts data.")
        self.app_state['git_accounts'] = new_accounts_data[:] # Make a copy
        self.save_app_state()
        self.update_all_tabs_data() # Ensure all tabs are synchronized

    def update_all_tabs_data(self):
        """Notifies all relevant tabs to refresh their data from the central state."""
        # Update RepoConfigTab's internal data
        if hasattr(self, 'repo_config_tab'):
            self.repo_config_tab.set_repositories_data(self.app_state['repositories'])
        
        # Update GitSettingsTab's internal data
        if hasattr(self, 'git_settings_tab'):
            self.git_settings_tab.set_git_accounts_data(self.app_state['git_accounts'])
            self.git_settings_tab.set_auto_start_ssh_agent_setting(self.app_state['auto_start_ssh_agent'])
        
        # CurrentBranchTab needs the full repositories data to retrieve commit message templates
        if hasattr(self, 'current_branch_tab'):
            self.current_branch_tab.set_repositories_data(self.app_state['repositories'])

    # --- Integrated Auto Functions ---
    def send_notification(self, title, message):
        """
        Sends a desktop notification using notify-send (Linux/Unix-like systems).
        """
        try:
            # Check if DISPLAY environment variable is set for notify-send to work
            if "DISPLAY" in os.environ:
                subprocess.run(['notify-send', title, message], check=False)
                logging.info(f"Notification sent: Title='{title}', Message='{message}'")
            else:
                logging.warning("DISPLAY environment variable not set. Cannot send desktop notifications.")
        except FileNotFoundError:
            logging.warning("notify-send command not found. Desktop notifications may not work.")
        except Exception as e:
            logging.error(f"Failed to send notification: {e}")

    def run_git_command(self, repo_path, command_args, timeout=300):
        """
        Helper function to run a git command in a specified repository.
        Returns (success: bool, output: str, is_auth_error: bool).
        """
        if not os.path.isdir(repo_path):
            logging.error(f"Path is not a directory: {repo_path}. Cannot run git command.")
            return False, "Not a directory", False

        git_dir = os.path.join(repo_path, ".git")
        if not os.path.isdir(git_dir):
            logging.error(f"Not a Git repository: {repo_path}. Missing .git directory.")
            return False, "Not a Git repository", False

        full_command = ['git'] + command_args
        logging.info(f"Executing '{' '.join(full_command)}' in {repo_path}")
        
        # Create a copy of the current environment variables
        env = os.environ.copy()
        # Set GIT_TERMINAL_PROMPT to 0 and GIT_ASKPASS to /bin/true to prevent Git from asking for credentials interactively
        env['GIT_TERMINAL_PROMPT'] = '0'
        env['GIT_ASKPASS'] = '/bin/true' # Forces Git to use a non-interactive password helper

        try:
            result = subprocess.run(
                full_command,
                cwd=repo_path,
                check=False, # Do not raise CalledProcessError automatically
                capture_output=True,
                text=True,
                timeout=timeout,
                stdin=subprocess.PIPE, # Prevent interactive prompts by closing stdin
                env=env # Pass the modified environment
            )
            
            stderr_output = result.stderr.strip()
            stdout_output = result.stdout.strip()

            # Check for common authentication failure messages in stderr
            auth_error_keywords = [
                "authentication failed",
                "could not read username",
                "could not read password",
                "permission denied (publickey)",
                "fatal: authentication failed",
                "remote: authentication required",
                "bad credentials",
                "no matching private key",
                "sign_and_send_pubkey: no mutual signature algorithm", # Specific SSH key error
                "username for", # Direct prompt for username (less likely with GIT_ASKPASS)
                "password for", # Direct prompt for password (less likely with GIT_ASKPASS)
                "ssh: connect to host", # General SSH connection issue, often auth related
                "no supported authentication methods available", # SSH auth methods exhausted
                "fatal: could not read from remote repository", # Generic remote repo error, often auth related
                "fatal: repository not found" # Can sometimes be a disguised auth issue for private repos
            ]
            is_auth_error = any(keyword in stderr_output.lower() for keyword in auth_error_keywords)

            if result.returncode != 0:
                logging.error(f"Command failed for {repo_path}. Return code: {result.returncode}. Error: {stderr_output}")
                logging.error(f"stdout: {stdout_output}")
                return False, stderr_output, is_auth_error
            
            logging.info(f"Command success for {repo_path}: {stdout_output}")
            if stderr_output:
                logging.warning(f"Command for {repo_path} had stderr output:\n{stderr_output}")
            return True, stdout_output, False # No authentication error if successful return code
        
        except FileNotFoundError:
            logging.error("Git command not found. Please ensure Git is installed and in your PATH.")
            return False, "Git command not found", False
        except subprocess.TimeoutExpired:
            logging.error(f"Command for {repo_path} timed out after {timeout} seconds.")
            return False, "Command timed out", False
        except Exception as e:
            logging.error(f"An unexpected error occurred while running git command in {repo_path}: {e}")
            return False, str(e), False

    def handle_git_operation_result(self, repo_path, operation_name, success, message, is_auth_error):
        """
        Handles the result of a Git operation, showing appropriate messages and notifications.
        """
        repo_base_name = os.path.basename(repo_path)
        if success:
            logging.info(f"Successfully {operation_name}d {repo_path}")
            self.send_notification(f"GitBuddy: {operation_name.capitalize()} Complete", 
                                   f"Repository: {repo_base_name}\nOperation: {operation_name.capitalize()}")
        else:
            logging.error(f"Failed to {operation_name} {repo_path}: {message}")
            if is_auth_error:
                QMessageBox.critical(self, f"Authentication Required for {operation_name.capitalize()}",
                                     f"GitBuddy failed to {operation_name} repository '{repo_base_name}' due to an authentication error.\n\n"
                                     "**The application is configured to suppress interactive Git prompts.**\n\n"
                                     "To resolve this, please go to the 'Git Settings' tab and:\n"
                                     "1. Configure a **Credential Helper** (e.g., 'store' or 'manager') to save your username/password.\n"
                                     "2. Or, set up **SSH Keys** for password-less authentication (and ensure SSH Agent is running).\n\n"
                                     f"Error details: {message}")
                self.send_notification(f"GitBuddy: {operation_name.capitalize()} Failed (Auth)", 
                                       f"Repository: {repo_base_name}\nError: Authentication required. Check Git Settings tab.")
            else:
                self.send_notification(f"GitBuddy: {operation_name.capitalize()} Failed", 
                                       f"Repository: {repo_base_name}\nError: {message}")
        return success

    def pull_repository(self, repo_path):
        """Attempts to perform a 'git pull'."""
        logging.info(f"Attempting to pull repository: {repo_path}")
        success, message, is_auth_error = self.run_git_command(repo_path, ['pull'])
        return self.handle_git_operation_result(repo_path, "pull", success, message, is_auth_error)

    def commit_repository(self, repo_path, commit_message_template):
        """
        Stages all changes and performs a 'git commit'.
        Uses a human-readable timestamp in the commit message.
        """
        # First, check if there are any changes to commit
        success_status, output_status, _ = self.run_git_command(repo_path, ['status', '--porcelain'], timeout=60)
        if not success_status:
            logging.error(f"Failed to get git status for {repo_path}. Skipping commit.")
            self.send_notification("GitBuddy: Commit Failed", f"Repository: {os.path.basename(repo_path)}\nError: Failed to get status.")
            return False
        
        if not output_status.strip():
            logging.info(f"No changes to commit in {repo_path}. Skipping commit.")
            return False

        logging.info(f"Staging changes in {repo_path}...")
        success_add, message_add, _ = self.run_git_command(repo_path, ['add', '.'])
        if not success_add:
            logging.error(f"Failed to stage changes in {repo_path}: {message_add}")
            self.send_notification("GitBuddy: Commit Failed", f"Repository: {os.path.basename(repo_path)}\nError: Failed to stage changes.")
            return False

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        final_commit_message = commit_message_template.format(timestamp=timestamp)
        logging.info(f"Attempting to commit {repo_path} with message: '{final_commit_message}'")
        success_commit, message_commit, is_auth_error = self.run_git_command(repo_path, ['commit', '-m', final_commit_message])
        # Commit itself usually doesn't need auth, but it's good to pass the flag just in case
        return self.handle_git_operation_result(repo_path, "commit", success_commit, message_commit, is_auth_error)

    def push_repository(self, repo_path):
        """Performs a git push on the selected repository."""
        logging.info(f"Attempting to push repository: {repo_path}")
        success, message, is_auth_error = self.run_git_command(repo_path, ['push'])
        return self.handle_git_operation_result(repo_path, "push", success, message, is_auth_error)

    def perform_periodic_sync(self):
        """
        Performs periodic Git operations (pull, commit, push) for all configured repositories.
        This method is called by the QTimer.
        """
        logging.info("Performing periodic Git sync for configured repositories.")
        if not self.app_state['repositories']:
            logging.info("No repositories configured for periodic sync.")
            return

        for repo_data in self.app_state['repositories']:
            repo_path = repo_data['path']
            
            # Ensure the repository path is valid before attempting operations
            if not os.path.isdir(repo_path) or not os.path.isdir(os.path.join(repo_path, ".git")):
                logging.warning(f"Skipping invalid repository path: {repo_path}. Not a directory or not a Git repo.")
                continue # Skip to the next repository

            current_time = datetime.now()

            # --- Pull Logic ---
            # Check global pause for pull and individual auto_pull setting
            if not self.app_state['global_pause_pull'] and repo_data['auto_pull']:
                pull_interval_seconds = repo_data['pull_interval'] # Already in seconds
                last_pulled = repo_data['last_pulled_at']
                time_since_last_pull = current_time - last_pulled
                
                if time_since_last_pull.total_seconds() >= pull_interval_seconds:
                    logging.info(f"Repository {repo_path} is due for a pull (last pulled {time_since_last_pull} ago).")
                    if self.pull_repository(repo_path):
                        repo_data['last_pulled_at'] = current_time
                else:
                    remaining_seconds = pull_interval_seconds - time_since_last_pull.total_seconds()
                    logging.debug(f"Repository {repo_path} not due for pull yet. Next pull in {timedelta(seconds=remaining_seconds)}.")
            else:
                if self.app_state['global_pause_pull']:
                    logging.debug(f"Auto-pull is globally paused. Skipping for {repo_path}.")
                else:
                    logging.debug(f"Auto-pull is disabled for {repo_path}.")

            # --- Commit Logic ---
            # Check global pause for commit and individual auto_commit setting
            if not self.app_state['global_pause_commit'] and repo_data['auto_commit']:
                commit_interval_seconds = repo_data['commit_interval'] # Already in seconds
                last_committed = repo_data['last_committed_at']
                time_since_last_committed = current_time - last_committed
                
                if time_since_last_committed.total_seconds() >= commit_interval_seconds:
                    logging.info(f"Repository {repo_path} is due for a commit (last committed {time_since_last_committed} ago).")
                    commit_message_template = repo_data.get('commit_message_template', "Auto-commit from GitBuddy: {timestamp}")
                    if self.commit_repository(repo_path, commit_message_template):
                        repo_data['last_committed_at'] = current_time
                else:
                    remaining_seconds = commit_interval_seconds - time_since_last_committed.total_seconds()
                    logging.debug(f"Repository {repo_path} not due for commit yet. Next commit in {timedelta(seconds=remaining_seconds)}.")
            else:
                if self.app_state['global_pause_commit']:
                    logging.debug(f"Auto-commit is globally paused. Skipping for {repo_path}.")
                else:
                    logging.debug(f"Auto-commit is disabled for {repo_path}.")

            # --- Push Logic ---
            # Check global pause for push and individual auto_push setting
            if not self.app_state['global_pause_push'] and repo_data['auto_push']:
                push_interval_seconds = repo_data['push_interval'] # Already in seconds
                last_pushed = repo_data['last_pushed_at']
                time_since_last_push = current_time - last_pushed

                if time_since_last_push.total_seconds() >= push_interval_seconds:
                    logging.info(f"Repository {repo_path} is due for a push (last pushed {time_since_last_push} ago).")
                    if self.push_repository(repo_path):
                        repo_data['last_pushed_at'] = current_time
                else:
                    remaining_seconds = push_interval_seconds - time_since_last_push.total_seconds()
                    logging.debug(f"Repository {repo_path} not due for push yet. Next push in {timedelta(seconds=remaining_seconds)}.")
            else:
                if self.app_state['global_pause_push']:
                    logging.debug(f"Auto-push is globally paused. Skipping for {repo_path}.")
                else:
                    logging.debug(f"Auto-push is disabled for {repo_path}.")
