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
# Removed: from gitbuddy_service_manager_tab import ServiceManagerTab

# Define the base configuration directory
CONFIG_DIR = os.path.expanduser("~/.config/git-buddy")
MAIN_CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json") # Main config for repos and global settings
GIT_ACCOUNTS_FILE = os.path.join(CONFIG_DIR, "git_accounts.json") # Git accounts config file
LOG_FILE = os.path.join(CONFIG_DIR, "git_buddy.log") # Log file for integrated functions
os.makedirs(CONFIG_DIR, exist_ok=True) # Ensure it exists

# Set up logging for the main application
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler() # This sends logs to stderr
    ]
)

class GitBuddyApp(QMainWindow):
    # Define signals that will be emitted when global data changes
    global_repo_path_changed = Signal(str)
    repo_data_updated = Signal(list) # Signal to notify tabs when repo data changes
    git_accounts_data_updated = Signal(list) # Signal to notify tabs when git accounts data changes

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GitBuddy")
        self.setGeometry(100, 100, 900, 750) # Adjusted size for tabbed interface

        # Set the application icon
        self.setWindowIcon(QIcon("icon.png"))

        # Initialize data structures
        self.repositories_data = [] # Stores the full configuration for each repository
        self.git_accounts_data = [] # Stores configured Git accounts
        self.global_pause_pull = False
        self.global_pause_commit = False
        self.global_pause_push = False
        self.auto_start_ssh_agent = False

        # Load all configurations on startup
        self.load_all_configurations()

        self.init_ui()
        self.setup_tray_icon()
        self.load_configured_repos_to_selector() # Load repos into the dropdown on startup

        # After init_ui, ensure the SSH agent state reflects the loaded setting
        # This needs to be done after git_settings_tab is initialized
        if self.auto_start_ssh_agent:
            if hasattr(self, 'git_settings_tab') and self.git_settings_tab.git_installed:
                self.git_settings_tab.start_ssh_agent()
            else:
                logging.warning("Auto-start SSH agent enabled, but GitSettingsTab not ready or Git not installed.")
        else:
            if hasattr(self, 'git_settings_tab') and self.git_settings_tab.git_installed:
                self.git_settings_tab.stop_ssh_agent()

        # Setup periodic sync timer
        self.periodic_sync_timer = QTimer(self)
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
        self.pause_pull_checkbox.setChecked(self.global_pause_pull)
        self.pause_pull_checkbox.stateChanged.connect(lambda: self.set_global_pause('pull', self.pause_pull_checkbox.isChecked()))
        global_pause_layout.addWidget(self.pause_pull_checkbox)

        self.pause_commit_checkbox = QCheckBox("Pause All Auto Commits")
        self.pause_commit_checkbox.setChecked(self.global_pause_commit)
        self.pause_commit_checkbox.stateChanged.connect(lambda: self.set_global_pause('commit', self.pause_commit_checkbox.isChecked()))
        global_pause_layout.addWidget(self.pause_commit_checkbox)

        self.pause_push_checkbox = QCheckBox("Pause All Auto Pushes")
        self.pause_push_checkbox.setChecked(self.global_pause_push)
        self.pause_push_checkbox.stateChanged.connect(lambda: self.set_global_pause('push', self.pause_push_checkbox.isChecked()))
        global_pause_layout.addWidget(self.pause_push_checkbox)
        
        global_pause_layout.addStretch(1) # Pushes checkboxes to the left

        main_layout.addWidget(global_pause_group)
        # --- End Global Pause Controls ---

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create instances of our tab widgets, passing initial data and parent explicitly
        self.current_branch_tab = CurrentBranchTab(parent=self)
        self.repo_config_tab = RepoConfigTab(self.repositories_data, parent=self)
        self.merge_tab = MergeTab(parent=self)
        self.bisect_tab = BisectTab(parent=self)
        self.git_settings_tab = GitSettingsTab(initial_git_accounts_data=self.git_accounts_data, auto_start_ssh_agent_initial=self.auto_start_ssh_agent, parent=self)

        # Connect global signals to each tab's update method
        self.global_repo_path_changed.connect(self.current_branch_tab.set_selected_repo_path)
        self.global_repo_path_changed.connect(self.repo_config_tab.set_selected_repo_path)
        self.global_repo_path_changed.connect(self.merge_tab.set_selected_repo_path)
        self.global_repo_path_changed.connect(self.bisect_tab.set_selected_repo_path)

        # Connect signals from tabs to GitBuddyApp slots for centralized management
        self.repo_config_tab.repo_config_changed.connect(self.on_repo_config_changed)
        self.git_settings_tab.git_accounts_changed.connect(self.on_git_accounts_changed)
        self.git_settings_tab.auto_start_ssh_agent_setting_changed.connect(self.set_auto_start_ssh_agent)

        # Connect GitBuddyApp's data update signals to tabs for refresh
        self.repo_data_updated.connect(self.repo_config_tab.on_repo_data_updated)
        self.git_accounts_data_updated.connect(self.git_settings_tab.on_git_accounts_data_updated)


        # Add tabs to the QTabWidget in the specified order
        self.tab_widget.addTab(self.current_branch_tab, "Current Branch")
        self.tab_widget.addTab(self.repo_config_tab, "Repository Configurator")
        self.tab_widget.addTab(self.merge_tab, "Merge")
        self.tab_widget.addTab(self.bisect_tab, "Bisect")
        self.tab_widget.addTab(self.git_settings_tab, "Git Settings")


    def setup_tray_icon(self):
        """Sets up the system tray icon and its context menu."""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("icon.png"))
        self.tray_icon.setToolTip("GitBuddy: Auto Git Sync")

        # Create context menu
        self.tray_menu = QMenu()
        self.tray_menu.aboutToShow.connect(self.update_tray_menu_state)

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
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def update_tray_menu_state(self):
        """Updates the checked state of the pause menu items before the tray menu is shown."""
        self.action_pause_pull.setChecked(self.global_pause_pull)
        self.action_pause_commit.setChecked(self.global_pause_commit)
        self.action_pause_push.setChecked(self.global_pause_push)

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
            self.activateWindow() # Bring to front

    def exit_application(self):
        """Closes the application cleanly."""
        reply = QMessageBox.question(self, "Exit GitBuddy",
                                     "Are you sure you want to exit GitBuddy?\n"
                                     "Automatic sync functions will stop.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return
        
        # Stop SSH Agent if it was auto-started and is running
        if self.auto_start_ssh_agent and self.git_settings_tab.git_installed:
            if "SSH_AUTH_SOCK" in os.environ and os.path.exists(os.environ["SSH_AUTH_SOCK"]):
                self.git_settings_tab.stop_ssh_agent()

        self.tray_icon.hide()
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
            event.ignore()
        else:
            event.accept()

    def load_configured_repos_to_selector(self):
        """Loads repository paths from self.repositories_data and populates the combobox."""
        current_selected_path = self.global_repo_path_input.text()
        
        self.repo_selector_combobox.currentIndexChanged.disconnect(self.on_repo_selection_changed)
        self.repo_selector_combobox.clear()

        configured_paths = [repo['path'] for repo in self.repositories_data if 'path' in repo]

        for path in configured_paths:
            repo_name = os.path.basename(path)
            self.repo_selector_combobox.addItem(repo_name, path)
        
        self.repo_selector_combobox.addItem("-- Other (Manual Path) --", "")

        index_to_select = -1
        if current_selected_path:
            index_to_select = self.repo_selector_combobox.findData(current_selected_path)
        
        if index_to_select != -1:
            self.repo_selector_combobox.setCurrentIndex(index_to_select)
            self.global_repo_path_input.setText(current_selected_path)
            self.global_repo_path_input.setReadOnly(True)
            self.global_browse_button.setEnabled(False)
        elif configured_paths:
            self.repo_selector_combobox.setCurrentIndex(0)
            self.global_repo_path_input.setText(self.repo_selector_combobox.currentData())
            self.global_repo_path_input.setReadOnly(True)
            self.global_browse_button.setEnabled(False)
        else:
            self.repo_selector_combobox.setCurrentIndex(self.repo_selector_combobox.count() - 1)
            self.global_repo_path_input.clear()
            self.global_repo_path_input.setReadOnly(False)
            self.global_browse_button.setEnabled(True)
            self.global_repo_path_input.setFocus()

        self.repo_selector_combobox.currentIndexChanged.connect(self.on_repo_selection_changed)
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
        if task_type == 'pull':
            self.global_pause_pull = paused
            self.pause_pull_checkbox.setChecked(paused)
        elif task_type == 'commit':
            self.global_pause_commit = paused
            self.pause_commit_checkbox.setChecked(paused)
        elif task_type == 'push':
            self.global_pause_push = paused
            self.pause_push_checkbox.setChecked(paused)
        self.save_all_configurations() # Save changes
        logging.info(f"Global pause for {task_type} set to {paused}.")

    def set_auto_start_ssh_agent(self, enable: bool):
        """
        Slot to handle the auto-start SSH agent setting change from GitSettingsTab.
        Updates the global setting and triggers SSH agent start/stop if applicable.
        """
        logging.info(f"Received auto-start SSH agent setting: {enable}")
        self.auto_start_ssh_agent = enable
        self.save_all_configurations() # Save changes

        if enable:
            if self.git_settings_tab.git_installed:
                self.git_settings_tab.start_ssh_agent()
        else:
            if self.git_settings_tab.git_installed:
                self.git_settings_tab.stop_ssh_agent()

    def on_repo_config_changed(self, new_repos_data: list):
        """Slot to receive updated repository data from RepoConfigTab."""
        self.repositories_data = new_repos_data
        self.save_all_configurations() # Save the updated data
        self.load_configured_repos_to_selector() # Refresh the global selector
        self.repo_data_updated.emit(self.repositories_data) # Notify other tabs

    def on_git_accounts_changed(self, new_accounts_data: list):
        """Slot to receive updated Git accounts data from GitSettingsTab."""
        self.git_accounts_data = new_accounts_data
        self.save_all_configurations() # Save the updated data
        self.git_accounts_data_updated.emit(self.git_accounts_data) # Notify other tabs

    def load_all_configurations(self):
        """
        Loads all application configurations (repositories, global settings, git accounts)
        from their respective files.
        """
        # Load main config file (repositories and global settings)
        if os.path.exists(MAIN_CONFIG_FILE):
            try:
                with open(MAIN_CONFIG_FILE, 'r') as f:
                    full_config = json.load(f)
                    if isinstance(full_config, list): # Handle old list format
                        self.repositories_data = full_config
                        # Default global settings for old format
                        self.global_pause_pull = False
                        self.global_pause_commit = False
                        self.global_pause_push = False
                        self.auto_start_ssh_agent = False
                        logging.info(f"Migrated old config format from {MAIN_CONFIG_FILE}.")
                    elif isinstance(full_config, dict):
                        self.repositories_data = full_config.get('repositories', [])
                        self.global_pause_pull = full_config.get('global_pause_pull', False)
                        self.global_pause_commit = full_config.get('global_pause_commit', False)
                        self.global_pause_push = full_config.get('global_pause_push', False)
                        self.auto_start_ssh_agent = full_config.get('auto_start_ssh_agent', False)
                    else:
                        logging.error(f"Main config file {MAIN_CONFIG_FILE} is malformed. Expected dict or list.")
                        self.repositories_data = []
            except json.JSONDecodeError as e:
                logging.error(f"Error decoding JSON from {MAIN_CONFIG_FILE}: {e}")
                self.repositories_data = []
            except Exception as e:
                logging.error(f"An unexpected error occurred while loading main config: {e}")
                self.repositories_data = []
        else:
            logging.info(f"Main config file not found: {MAIN_CONFIG_FILE}. Initializing defaults.")
            self.repositories_data = [] # Ensure it's empty if file doesn't exist

        # Initialize 'last_pulled_at', 'last_committed_at', 'last_pushed_at' for periodic sync
        for repo in self.repositories_data:
            repo.setdefault('last_pulled_at', datetime.min)
            repo.setdefault('last_committed_at', datetime.min)
            repo.setdefault('last_pushed_at', datetime.min)
            # Ensure intervals are in seconds for internal use
            repo['pull_interval'] = max(60, repo.get('pull_interval', 120) * 60 if repo.get('pull_interval') < 1000 else repo.get('pull_interval', 120)) # Convert minutes to seconds if small value, otherwise assume seconds
            repo['commit_interval'] = max(60, repo.get('commit_interval', 20) * 60 if repo.get('commit_interval') < 1000 else repo.get('commit_interval', 20))
            repo['push_interval'] = max(60, repo.get('push_interval', 60) * 60 if repo.get('push_interval') < 1000 else repo.get('push_interval', 60))

        logging.info(f"Loaded {len(self.repositories_data)} repositories for periodic sync.")

        # Load Git accounts data
        if os.path.exists(GIT_ACCOUNTS_FILE):
            try:
                with open(GIT_ACCOUNTS_FILE, 'r') as f:
                    accounts_config = json.load(f)
                    if isinstance(accounts_config, list):
                        self.git_accounts_data = accounts_config
                    else:
                        logging.warning(f"Git accounts file '{GIT_ACCOUNTS_FILE}' is malformed. Expected a list.")
                        self.git_accounts_data = []
            except json.JSONDecodeError as e:
                logging.error(f"Error decoding JSON from {GIT_ACCOUNTS_FILE}: {e}")
                self.git_accounts_data = []
            except Exception as e:
                logging.error(f"An unexpected error occurred while loading Git accounts: {e}")
                self.git_accounts_data = []
        else:
            logging.info(f"Git accounts file not found: {GIT_ACCOUNTS_FILE}. Initializing empty list.")
            self.git_accounts_data = []

        # Update UI checkboxes if they exist (will be called before init_ui for initial load,
        # so these might not exist yet. The init_ui will set them based on self.global_pause_X)
        if hasattr(self, 'pause_pull_checkbox'):
            self.pause_pull_checkbox.setChecked(self.global_pause_pull)
        if hasattr(self, 'pause_commit_checkbox'):
            self.pause_commit_checkbox.setChecked(self.global_pause_commit)
        if hasattr(self, 'pause_push_checkbox'):
            self.pause_push_checkbox.setChecked(self.global_pause_push)

    def save_all_configurations(self):
        """
        Saves all application configurations (repositories, global settings, git accounts)
        to their respective files.
        """
        # Save main config file (repositories and global settings)
        main_config_to_save = {
            'repositories': [
                {k: v for k, v in repo.items() if k not in ['last_pulled_at', 'last_committed_at', 'last_pushed_at']}
                for repo in self.repositories_data
            ],
            'global_pause_pull': self.global_pause_pull,
            'global_pause_commit': self.global_pause_commit,
            'global_pause_push': self.global_pause_push,
            'auto_start_ssh_agent': self.auto_start_ssh_agent
        }
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(MAIN_CONFIG_FILE, 'w') as f:
                json.dump(main_config_to_save, f, indent=4)
            logging.info(f"Main configuration saved to {MAIN_CONFIG_FILE}.")
        except Exception as e:
            logging.error(f"Failed to save main configuration: {e}")

        # Save Git accounts data
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(GIT_ACCOUNTS_FILE, 'w') as f:
                json.dump(self.git_accounts_data, f, indent=4)
            logging.info(f"Git accounts saved to {GIT_ACCOUNTS_FILE}")
        except Exception as e:
            logging.error(f"Failed to save Git accounts: {e}")

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
        
        env = os.environ.copy()
        env['GIT_TERMINAL_PROMPT'] = '0'
        env['GIT_ASKPASS'] = '/bin/true'

        try:
            result = subprocess.run(
                full_command,
                cwd=repo_path,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                stdin=subprocess.PIPE,
                env=env
            )
            
            stderr_output = result.stderr.strip()
            stdout_output = result.stdout.strip()

            auth_error_keywords = [
                "authentication failed", "could not read username", "could not read password",
                "permission denied (publickey)", "fatal: authentication failed", "remote: authentication required",
                "bad credentials", "no matching private key", "sign_and_send_pubkey: no mutual signature algorithm",
                "username for", "password for", "ssh: connect to host",
                "no supported authentication methods available", "fatal: could not read from remote repository",
                "fatal: repository not found"
            ]
            is_auth_error = any(keyword in stderr_output.lower() for keyword in auth_error_keywords)

            if result.returncode != 0:
                logging.error(f"Command failed for {repo_path}. Return code: {result.returncode}. Error: {stderr_output}")
                logging.error(f"stdout: {stdout_output}")
                return False, stderr_output, is_auth_error
            
            logging.info(f"Command success for {repo_path}: {stdout_output}")
            if stderr_output:
                logging.warning(f"Command for {repo_path} had stderr output:\n{stderr_output}")
            return True, stdout_output, False
        
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
                                     "2. Or, set up **SSH Keys** for password-less authentication.\n\n"
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
        commit_message = commit_message_template.format(timestamp=timestamp)
        logging.info(f"Attempting to commit {repo_path} with message: '{commit_message}'")
        success_commit, message_commit, is_auth_error = self.run_git_command(repo_path, ['commit', '-m', commit_message])
        return self.handle_git_operation_result(repo_path, "commit", success_commit, message_commit, is_auth_error)

    def push_repository(self, repo_path):
        """Attempts to perform a 'git push'."""
        logging.info(f"Attempting to push repository: {repo_path}")
        success, message, is_auth_error = self.run_git_command(repo_path, ['push'])
        return self.handle_git_operation_result(repo_path, "push", success, message, is_auth_error)

    def perform_periodic_sync(self):
        """
        Performs periodic Git operations (pull, commit, push) for all configured repositories.
        This method is called by the QTimer.
        """
        logging.info("Performing periodic Git sync for configured repositories.")
        if not self.repositories_data:
            logging.info("No repositories configured for periodic sync.")
            return

        for repo_data in self.repositories_data:
            repo_path = repo_data['path']
            
            if not os.path.isdir(repo_path) or not os.path.isdir(os.path.join(repo_path, ".git")):
                logging.warning(f"Skipping invalid repository path: {repo_path}. Not a directory or not a Git repo.")
                continue

            current_time = datetime.now()

            # --- Pull Logic ---
            if not self.global_pause_pull and repo_data['auto_pull']:
                pull_interval_seconds = repo_data['pull_interval']
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
                if self.global_pause_pull:
                    logging.debug(f"Auto-pull is globally paused. Skipping for {repo_path}.")
                else:
                    logging.debug(f"Auto-pull is disabled for {repo_path}.")

            # --- Commit Logic ---
            if not self.global_pause_commit and repo_data['auto_commit']:
                commit_interval_seconds = repo_data['commit_interval']
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
                if self.global_pause_commit:
                    logging.debug(f"Auto-commit is globally paused. Skipping for {repo_path}.")
                else:
                    logging.debug(f"Auto-commit is disabled for {repo_path}.")

            # --- Push Logic ---
            if not self.global_pause_push and repo_data['auto_push']:
                push_interval_seconds = repo_data['push_interval']
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
                if self.global_pause_push:
                    logging.debug(f"Auto-push is globally paused. Skipping for {repo_path}.")
                else:
                    logging.debug(f"Auto-push is disabled for {repo_path}.")

    def send_notification(self, title, message):
        """
        Sends a desktop notification using notify-send (Linux/Unix-like systems).
        """
        try:
            if "DISPLAY" in os.environ:
                subprocess.run(['notify-send', title, message], check=False)
                logging.info(f"Notification sent: Title='{title}', Message='{message}'")
            else:
                logging.warning("DISPLAY environment variable not set. Cannot send desktop notifications.")
        except FileNotFoundError:
            logging.warning("notify-send command not found. Desktop notifications may not work.")
        except Exception as e:
            logging.error(f"Failed to send notification: {e}")
