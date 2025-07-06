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
    QMessageBox, QSystemTrayIcon, QMenu, QStyle
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
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
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
    # Define a signal that will be emitted when the global repository path changes
    global_repo_path_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GitBuddy")
        self.setGeometry(100, 100, 900, 750) # Adjusted size for tabbed interface

        self.repositories_data = [] # Stores the full configuration for each repository
        self.load_configured_repos_data() # Load initial repo data for auto functions

        self.init_ui()
        self.setup_tray_icon()
        self.load_configured_repos_to_selector() # Load repos into the dropdown on startup

        # Setup periodic sync timer
        self.periodic_sync_timer = QTimer(self)
        # The interval for the main application's timer. This defines how often
        # the application checks if any repositories are due for pull/commit/push.
        # Set to a relatively short interval (e.g., 30 seconds) so it's responsive
        # to individual repo intervals which might be longer.
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

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create instances of our tab widgets
        self.current_branch_tab = CurrentBranchTab()
        self.repo_config_tab = RepoConfigTab(CONFIG_DIR)
        self.merge_tab = MergeTab()
        self.bisect_tab = BisectTab()
        # self.service_manager_tab = ServiceManagerTab(CONFIG_DIR) # REMOVED
        self.git_settings_tab = GitSettingsTab(CONFIG_DIR)

        # Connect the global signal to each tab's update method
        self.global_repo_path_changed.connect(self.current_branch_tab.set_selected_repo_path)
        self.global_repo_path_changed.connect(self.repo_config_tab.set_selected_repo_path)
        self.global_repo_path_changed.connect(self.merge_tab.set_selected_repo_path)
        self.global_repo_path_changed.connect(self.bisect_tab.set_selected_repo_path)

        # Connect RepoConfigTab's signal to refresh the global combobox AND the internal repo data
        self.repo_config_tab.repo_config_changed.connect(self.load_configured_repos_to_selector)
        self.repo_config_tab.repo_config_changed.connect(self.load_configured_repos_data) # Refresh internal data

        # Add tabs to the QTabWidget in the specified order
        self.tab_widget.addTab(self.current_branch_tab, "Current Branch")
        self.tab_widget.addTab(self.repo_config_tab, "Repository Configurator")
        self.tab_widget.addTab(self.merge_tab, "Merge")
        self.tab_widget.addTab(self.bisect_tab, "Bisect")
        self.tab_widget.addTab(self.git_settings_tab, "Git Settings")
        # self.tab_widget.addTab(self.service_manager_tab, "Service Manager") # REMOVED

    def setup_tray_icon(self):
        """Sets up the system tray icon and its context menu."""
        self.tray_icon = QSystemTrayIcon(self)
        # Use a generic icon or provide a custom one if available
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon)) # Example icon
        self.tray_icon.setToolTip("GitBuddy: Auto Git Sync")

        # Create context menu
        tray_menu = QMenu()
        show_hide_action = QAction("Show/Hide GitBuddy", self)
        show_hide_action.triggered.connect(self.show_hide_window)
        tray_menu.addAction(show_hide_action)

        exit_action = QAction("Exit GitBuddy", self)
        exit_action.triggered.connect(self.exit_application)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated) # For double-click
        self.tray_icon.show()

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
        if reply == QMessageBox.Yes:
            self.tray_icon.hide() # Hide tray icon before quitting
            QApplication.quit()
        else:
            pass # Do nothing if user cancels

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
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    repos_config = json.load(f)
                    if isinstance(repos_config, list):
                        for entry in repos_config:
                            if isinstance(entry, dict) and 'path' in entry:
                                configured_paths.append(entry['path'])
            except json.JSONDecodeError:
                logging.warning("Config Load Error: Could not load repository configuration. File might be corrupted.")
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

    # --- Integrated Auto Functions ---
    def load_configured_repos_data(self):
        """
        Loads the list of Git repository configurations from the configuration file.
        Initializes 'last_pulled_at', 'last_committed_at', and 'last_pushed_at' for internal tracking.
        Converts intervals from minutes to seconds.
        Returns an empty list if the file does not exist or is malformed.
        """
        if not os.path.exists(CONFIG_FILE):
            logging.warning(f"Configuration file not found: {CONFIG_FILE}. Initializing empty list.")
            self.repositories_data = []
            return

        try:
            with open(CONFIG_FILE, 'r') as f:
                repos_config = json.load(f)
                if not isinstance(repos_config, list):
                    logging.error(f"Configuration file {CONFIG_FILE} is malformed. Expected a list.")
                    self.repositories_data = []
                    return

                new_repositories_data = []
                for entry in repos_config:
                    if not isinstance(entry, dict) or 'path' not in entry:
                        logging.warning(f"Malformed repository entry: {entry}. Skipping.")
                        continue

                    repo_path = entry['path']
                    
                    auto_pull = entry.get('auto_pull', False)
                    pull_interval_minutes = entry.get('pull_interval', 120) # Default 2 hours if not specified
                    auto_commit = entry.get('auto_commit', False)
                    commit_interval_minutes = entry.get('commit_interval', 20) # Default 20 minutes
                    commit_message_template = entry.get('commit_message_template', "Auto-commit from GitBuddy: {timestamp}")
                    auto_push = entry.get('auto_push', False)
                    push_interval_minutes = entry.get('push_interval', 60) # Default 1 hour

                    # Validate intervals and convert to seconds
                    pull_interval_seconds = max(60, pull_interval_minutes * 60) # Min 1 minute
                    commit_interval_seconds = max(60, commit_interval_minutes * 60) # Min 1 minute
                    push_interval_seconds = max(60, push_interval_minutes * 60) # Min 1 minute

                    # Preserve last_run timestamps if repository already exists in current data
                    # Initialize with datetime.min if not found
                    existing_repo = next((r for r in self.repositories_data if r['path'] == repo_path), None)
                    
                    new_repositories_data.append({
                        'path': repo_path,
                        'auto_pull': auto_pull,
                        'pull_interval': pull_interval_seconds,
                        'last_pulled_at': existing_repo['last_pulled_at'] if existing_repo else datetime.min,
                        'auto_commit': auto_commit,
                        'commit_interval': commit_interval_seconds,
                        'last_committed_at': existing_repo['last_committed_at'] if existing_repo else datetime.min,
                        'commit_message_template': commit_message_template,
                        'auto_push': auto_push,
                        'push_interval': push_interval_seconds,
                        'last_pushed_at': existing_repo['last_pushed_at'] if existing_repo else datetime.min
                    })
                self.repositories_data = new_repositories_data
                logging.info(f"Loaded {len(self.repositories_data)} repositories for periodic sync.")
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from {CONFIG_FILE}: {e}")
            self.repositories_data = []
        except Exception as e:
            logging.error(f"An unexpected error occurred while loading config for auto functions: {e}")
            self.repositories_data = []

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
        try:
            result = subprocess.run(
                full_command,
                cwd=repo_path,
                check=False, # Do not raise CalledProcessError automatically
                capture_output=True,
                text=True,
                timeout=timeout,
                stdin=subprocess.PIPE # Prevent interactive prompts by closing stdin
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
                "username for", # Direct prompt for username
                "password for", # Direct prompt for password
                "ssh: connect to host", # General SSH connection issue, often auth related
                "no supported authentication methods available" # SSH auth methods exhausted
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
                                     "Please go to the 'Git Settings' tab to configure your Git credentials or SSH keys for this repository's host.\n\n"
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
        commit_message = commit_message_template.format(timestamp=timestamp)
        logging.info(f"Attempting to commit {repo_path} with message: '{commit_message}'")
        success_commit, message_commit, is_auth_error = self.run_git_command(repo_path, ['commit', '-m', commit_message])
        # Commit itself usually doesn't need auth, but it's good to pass the flag just in case
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
            
            # Ensure the repository path is valid before attempting operations
            if not os.path.isdir(repo_path) or not os.path.isdir(os.path.join(repo_path, ".git")):
                logging.warning(f"Skipping invalid repository path: {repo_path}. Not a directory or not a Git repo.")
                continue # Skip to the next repository

            current_time = datetime.now()

            # --- Pull Logic ---
            if repo_data['auto_pull']:
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
                logging.debug(f"Auto-pull is disabled for {repo_path}.")

            # --- Commit Logic ---
            if repo_data['auto_commit']:
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
                logging.debug(f"Auto-commit is disabled for {repo_path}.")

            # --- Push Logic ---
            if repo_data['auto_push']:
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
                logging.debug(f"Auto-push is disabled for {repo_path}.")
