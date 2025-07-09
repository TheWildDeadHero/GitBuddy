# gitbuddy_current_branch_tab.py

import os
import subprocess
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel,
    QFileDialog, QMessageBox, QFrame, QSizePolicy, QComboBox, QInputDialog,
    QTabWidget, QTextEdit, QScrollArea, QGroupBox # Added QGroupBox
)
from PySide6.QtCore import Qt, QDir, QPointF, QRectF, QTimer # Import QTimer
from PySide6.QtGui import QPalette, QColor, QPainter, QPen, QBrush, QFontMetrics
from datetime import datetime

# Import the custom graph widget
from gitbuddy_git_graph_widget import GitGraphWidget

class CurrentBranchTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_selected_repo_path = "" # To store the path from the global selector
        # This tab will receive repositories_data from GitBuddyApp, not load it directly
        self.repositories_data = [] 
        
        # Setup a timer for periodic updates of repository info
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(5000) # Refresh every 5 seconds
        self.refresh_timer.timeout.connect(self.load_repository_info)

        self.init_ui()

    def init_ui(self):
        """Initializes the current branch tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Repository Path Label (updated by global selector)
        self.repo_path_label = QLabel("Selected Repository: N/A")
        self.repo_path_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self.repo_path_label)

        # Branch Selection/Creation Section
        branch_section_group = QGroupBox("Branch Management")
        branch_section_layout = QVBoxLayout(branch_section_group)

        # Current Branch Display
        self.current_branch_display_label = QLabel("Current Branch: N/A")
        self.current_branch_display_label.setStyleSheet("font-weight: bold;")
        branch_section_layout.addWidget(self.current_branch_display_label)

        # Branch Selector
        branch_select_layout = QHBoxLayout()
        branch_select_layout.addWidget(QLabel("Switch to Branch:"))
        self.branch_combobox = QComboBox()
        self.branch_combobox.setMinimumWidth(150)
        branch_select_layout.addWidget(self.branch_combobox)
        self.switch_branch_button = QPushButton("Switch Branch")
        self.switch_branch_button.clicked.connect(self.switch_branch)
        branch_select_layout.addWidget(self.switch_branch_button)
        branch_select_layout.addStretch(1)
        branch_section_layout.addLayout(branch_select_layout)

        # New Branch Creation
        new_branch_layout = QHBoxLayout()
        new_branch_layout.addWidget(QLabel("New Branch Name:"))
        self.new_branch_input = QLineEdit()
        self.new_branch_input.setPlaceholderText("e.g., feature/my-new-feature")
        new_branch_layout.addWidget(self.new_branch_input)
        self.create_branch_button = QPushButton("Create Branch")
        self.create_branch_button.clicked.connect(self.create_branch)
        new_branch_layout.addWidget(self.create_branch_button)
        new_branch_layout.addStretch(1)
        branch_section_layout.addLayout(new_branch_layout)

        branch_section_layout.addStretch(1)
        layout.addWidget(branch_section_group)

        # Commit Operations Section
        commit_section_group = QGroupBox("Commit Operations")
        commit_section_layout = QVBoxLayout(commit_section_group)

        # Commit Message Input
        commit_section_layout.addWidget(QLabel("Commit Message:"))
        self.commit_message_input = QLineEdit()
        self.commit_message_input.setPlaceholderText("Enter your commit message here...")
        commit_section_layout.addWidget(self.commit_message_input)

        # Commit Button
        commit_buttons_layout = QHBoxLayout()
        self.commit_all_button = QPushButton("Commit All Changes")
        self.commit_all_button.clicked.connect(self.commit_all_changes)
        commit_buttons_layout.addWidget(self.commit_all_button)

        self.revert_commit_button = QPushButton("Revert Commit")
        self.revert_commit_button.clicked.connect(self.revert_commit)
        commit_buttons_layout.addWidget(self.revert_commit_button)
        commit_buttons_layout.addStretch(1)
        commit_section_layout.addLayout(commit_buttons_layout)

        commit_section_layout.addStretch(1)
        layout.addWidget(commit_section_group)

        # Pull/Push Operations Section
        sync_section_group = QGroupBox("Synchronization Operations")
        sync_section_layout = QVBoxLayout(sync_section_group)

        sync_buttons_layout = QHBoxLayout()
        self.pull_button = QPushButton("Pull")
        self.pull_button.clicked.connect(self.pull_repository)
        sync_buttons_layout.addWidget(self.pull_button)

        self.push_button = QPushButton("Push")
        self.push_button.clicked.connect(self.push_repository)
        sync_buttons_layout.addWidget(self.push_button)
        sync_buttons_layout.addStretch(1)
        sync_section_layout.addLayout(sync_buttons_layout)

        sync_section_layout.addStretch(1)
        layout.addWidget(sync_section_group)

        # Git Graph Visualization
        graph_section_group = QGroupBox("Git Commit History (Last 20 Commits)")
        graph_section_layout = QVBoxLayout(graph_section_group)

        self.git_graph_widget = GitGraphWidget()
        # Wrap the graph widget in a QScrollArea
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.git_graph_widget)
        graph_section_layout.addWidget(scroll_area)
        
        layout.addWidget(graph_section_group)

        # Initialize button states (disabled until a repo is selected)
        self.set_ui_enabled_state(False)

    def set_ui_enabled_state(self, enable: bool):
        """Enables or disables UI elements based on whether a valid repo is selected."""
        self.branch_combobox.setEnabled(enable)
        self.switch_branch_button.setEnabled(enable)
        self.new_branch_input.setEnabled(enable)
        self.create_branch_button.setEnabled(enable)
        self.commit_message_input.setEnabled(enable)
        self.commit_all_button.setEnabled(enable)
        self.revert_commit_button.setEnabled(enable)
        self.pull_button.setEnabled(enable)
        self.push_button.setEnabled(enable)
        # The graph widget itself doesn't need to be disabled, just cleared/updated

    def set_selected_repo_path(self, path):
        """
        Called by GitBuddyApp to update the selected repository path.
        Triggers loading of repository info if a valid path is provided.
        """
        self.current_selected_repo_path = path
        if path and os.path.isdir(os.path.join(path, ".git")):
            self.repo_path_label.setText(f"Selected Repository: {path}")
            self.set_ui_enabled_state(True)
            self.load_repository_info()
            self.refresh_timer.start() # Start the timer for this repo
        else:
            self.repo_path_label.setText("Selected Repository: N/A (Not a Git Repo or No Selection)")
            self.set_ui_enabled_state(False)
            self.current_branch_display_label.setText("Current Branch: N/A")
            self.branch_combobox.clear()
            self.git_graph_widget.set_commits_data([]) # Clear graph
            self.refresh_timer.stop() # Stop the timer when no valid repo

    def set_repositories_data(self, data):
        """
        Receives the full repositories data from GitBuddyApp.
        This tab primarily uses the currently selected repo's data,
        but this method is here for completeness if needed later.
        """
        self.repositories_data = data
        # No direct UI update needed here, as set_selected_repo_path is the primary trigger.

    def run_git_command(self, repo_path, command_args, timeout=300):
        """
        Helper function to run a git command in a specified repository.
        Returns (success: bool, output: str, is_auth_error: bool).
        """
        if not os.path.isdir(repo_path):
            return False, "Error: Path is not a directory.", False
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            return False, "Error: Not a Git repository.", False

        full_command = ['git'] + command_args
        
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
                return False, stderr_output, is_auth_error
            
            return True, stdout_output, False # No authentication error if successful return code
        
        except FileNotFoundError:
            return False, "Error: 'git' command not found. Please ensure Git is installed and in your PATH.", False
        except subprocess.TimeoutExpired:
            return False, f"Error: Git command timed out after {timeout} seconds.", False
        except Exception as e:
            return False, f"An unexpected error occurred: {e}", False

    def handle_git_operation_result(self, operation_name, success, message, is_auth_error):
        """
        Handles the result of a Git operation, showing appropriate messages.
        """
        repo_base_name = os.path.basename(self.current_selected_repo_path)
        if success:
            QMessageBox.information(self, f"{operation_name.capitalize()} Success", f"{operation_name.capitalize()} for '{repo_base_name}' completed successfully.")
        else:
            if is_auth_error:
                QMessageBox.critical(self, f"Authentication Required for {operation_name.capitalize()}",
                                     f"GitBuddy failed to {operation_name} repository '{repo_base_name}' due to an authentication error.\n\n"
                                     "**The application is configured to suppress interactive Git prompts.**\n\n"
                                     "To resolve this, please go to the 'Git Settings' tab and:\n"
                                     "1. Configure a **Credential Helper** (e.g., 'store' or 'manager') to save your username/password.\n"
                                     "2. Or, set up **SSH Keys** for password-less authentication (and ensure SSH Agent is running).\n\n"
                                     f"Error details: {message}")
            else:
                QMessageBox.critical(self, f"{operation_name.capitalize()} Failed", f"Failed to {operation_name} for '{repo_base_name}':\n{message}")
        return success

    def load_repository_info(self):
        """Loads and displays information about the selected Git repository."""
        repo_path = self.current_selected_repo_path
        if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
            self.current_branch_display_label.setText("Current Branch: N/A")
            self.branch_combobox.clear()
            self.git_graph_widget.set_commits_data([])
            self.set_ui_enabled_state(False)
            return

        # Get current branch
        success, branch_output, _ = self.run_git_command(repo_path, ['rev-parse', '--abbrev-ref', 'HEAD'])
        if success:
            self.current_branch_display_label.setText(f"Current Branch: {branch_output}")
        else:
            self.current_branch_display_label.setText("Current Branch: Error")
            # QMessageBox.critical(self, "Git Error", branch_output) # Suppress frequent popups from timer
            
        # Populate branch combobox
        self.branch_combobox.clear()
        success, branches_output, _ = self.run_git_command(repo_path, ['branch', '--list'])
        if success:
            branches = [b.strip().replace('* ', '') for b in branches_output.split('\n') if b.strip()]
            self.branch_combobox.addItems(branches)
            current_branch_index = self.branch_combobox.findText(branch_output)
            if current_branch_index != -1:
                self.branch_combobox.setCurrentIndex(current_branch_index)

        # Get commit history for graph visualization
        success, log_output, _ = self.run_git_command(
            repo_path,
            ['log', '--pretty=format:%H|%P|%s', '-n', '20'] # Limit to last 20 commits
        )

        if success:
            commits_data = []
            for line in log_output.split('\n'):
                if not line.strip():
                    continue
                parts = line.split('|', 2)
                if len(parts) == 3:
                    commit_hash = parts[0]
                    parent_hashes = parts[1].split()
                    message = parts[2]
                    commits_data.append({
                        'hash': commit_hash,
                        'parents': parent_hashes,
                        'message': message
                    })
            self.git_graph_widget.set_commits_data(commits_data)
        else:
            self.git_graph_widget.set_commits_data([])
            # QMessageBox.critical(self, "Git Log Error", log_output) # Suppress frequent popups

    def switch_branch(self):
        """Switches to the selected branch."""
        repo_path = self.current_selected_repo_path
        if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
            QMessageBox.warning(self, "No Repository", "Please select a valid Git repository first.")
            return

        selected_branch = self.branch_combobox.currentText()
        if not selected_branch:
            QMessageBox.information(self, "No Branch Selected", "Please select a branch to switch to.")
            return

        reply = QMessageBox.question(self, "Confirm Switch Branch",
                                     f"Are you sure you want to switch to branch '{selected_branch}'?\n"
                                     "Uncommitted changes might be stashed or lost.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        success, output, is_auth_error = self.run_git_command(repo_path, ['checkout', selected_branch])
        if self.handle_git_operation_result("switch branch", success, output, is_auth_error):
            self.load_repository_info() # Refresh UI after successful switch

    def create_branch(self):
        """Creates a new branch from the current HEAD."""
        repo_path = self.current_selected_repo_path
        if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
            QMessageBox.warning(self, "No Repository", "Please select a valid Git repository first.")
            return

        new_branch_name = self.new_branch_input.text().strip()
        if not new_branch_name:
            QMessageBox.warning(self, "Input Error", "Please enter a name for the new branch.")
            return

        success, output, is_auth_error = self.run_git_command(repo_path, ['checkout', '-b', new_branch_name])
        if self.handle_git_operation_result("create branch", success, output, is_auth_error):
            self.new_branch_input.clear()
            self.load_repository_info() # Refresh UI after successful creation

    def commit_all_changes(self):
        """Stages all changes and performs a commit."""
        repo_path = self.current_selected_repo_path
        if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
            QMessageBox.warning(self, "No Repository", "Please select a valid Git repository first.")
            return

        commit_message = self.commit_message_input.text().strip()
        if not commit_message:
            # Try to get the default commit message template from repositories_data
            repo_config = next((r for r in self.repositories_data if r['path'] == repo_path), None)
            if repo_config and repo_config.get('auto_commit', False) and repo_config.get('commit_message_template'):
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                commit_message = repo_config['commit_message_template'].format(timestamp=timestamp)
            else:
                QMessageBox.warning(self, "Input Error", "Please enter a commit message.")
                return

        # Check for changes first
        success_status, status_output, _ = self.run_git_command(repo_path, ['status', '--porcelain'], timeout=60)
        if not success_status:
            QMessageBox.critical(self, "Commit Failed", f"Failed to get repository status:\n{status_output}")
            return
        
        if not status_output.strip():
            QMessageBox.information(self, "No Changes", "No changes to commit in the current repository.")
            return

        # Stage all changes
        success_add, add_output, _ = self.run_git_command(repo_path, ['add', '.'])
        if not success_add:
            QMessageBox.critical(self, "Commit Failed", f"Failed to stage changes:\n{add_output}")
            return

        # Perform commit
        success_commit, commit_output, is_auth_error = self.run_git_command(repo_path, ['commit', '-m', commit_message])
        if self.handle_git_operation_result("commit", success_commit, commit_output, is_auth_error):
            self.commit_message_input.clear()
            self.load_repository_info() # Refresh UI after successful commit

    def revert_commit(self):
        """Initiates a revert operation by prompting for a commit hash."""
        repo_path = self.current_selected_repo_path
        if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
            QMessageBox.warning(self, "No Repository", "Please select a valid Git repository first.")
            return

        commit_hash, ok = QInputDialog.getText(self, "Revert Commit",
                                               "Enter the commit hash to revert:",
                                               QLineEdit.Normal, "")
        
        if not ok or not commit_hash.strip():
            QMessageBox.warning(self, "Input Error", "Revert cancelled or no commit hash entered.")
            return

        reply = QMessageBox.question(self, "Confirm Revert",
                                     f"Are you sure you want to revert commit '{commit_hash.strip()}'?\n"
                                     "This will create a new commit that undoes the changes from the specified commit.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        success, output, is_auth_error = self.run_git_command(repo_path, ['revert', commit_hash.strip()])
        if self.handle_git_operation_result("revert", success, output, is_auth_error):
            self.load_repository_info()

    def pull_repository(self):
        """Performs a git pull on the selected repository."""
        repo_path = self.current_selected_repo_path
        if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
            QMessageBox.warning(self, "No Repository", "Please select a valid Git repository first.")
            return

        success, output, is_auth_error = self.run_git_command(repo_path, ['pull'])
        self.handle_git_operation_result("pull", success, output, is_auth_error)
        self.load_repository_info() # Refresh UI after pull

    def push_repository(self):
        """Performs a git push on the selected repository."""
        repo_path = self.current_selected_repo_path
        if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
            QMessageBox.warning(self, "No Repository", "Please select a valid Git repository first.")
            return

        # Determine current branch
        success_branch, branch_name, _ = self.run_git_command(repo_path, ['rev-parse', '--abbrev-ref', 'HEAD'])
        if not success_branch:
            QMessageBox.critical(self, "Push Failed", f"Could not determine current branch:\n{branch_name}")
            return

        # Check if there's an upstream branch set
        # Using a short timeout for this check as it should be quick
        success_upstream, upstream_info, _ = self.run_git_command(repo_path, ['rev-parse', '--abbrev-ref', '@{upstream}'], timeout=10)
        
        push_command = ['push']
        if not success_upstream or "fatal" in upstream_info.lower():
            # No upstream set, try to set it to origin/current_branch
            reply = QMessageBox.question(self, "Set Upstream Branch",
                                         f"No upstream branch is set for '{branch_name}'. Do you want to set 'origin/{branch_name}' as upstream?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.No:
                QMessageBox.information(self, "Push Cancelled", "Push cancelled. Upstream branch not set.")
                return

            push_command.extend(['--set-upstream', 'origin', branch_name])
        
        success, output, is_auth_error = self.run_git_command(repo_path, push_command)
        self.handle_git_operation_result("push", success, output, is_auth_error)
        self.load_repository_info() # Refresh UI after push
