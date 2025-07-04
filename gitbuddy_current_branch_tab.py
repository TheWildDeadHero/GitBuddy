# gitbuddy_current_branch_tab.py

import os
import subprocess
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel,
    QFileDialog, QMessageBox, QFrame, QSizePolicy, QComboBox, QInputDialog,
    QTabWidget, QTextEdit
)
from PySide6.QtCore import Qt, QDir, QPointF, QRectF
from PySide6.QtGui import QPalette, QColor, QPainter, QPen, QBrush, QFontMetrics
from datetime import datetime # Import datetime for commit message timestamp

# Import the custom graph widget
from gitbuddy_git_graph_widget import GitGraphWidget

class CurrentBranchTab(QWidget): # Renamed class
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_selected_repo_path = "" # To store the path from the global selector
        # Removed initialization of self.current_branch_label as it's no longer needed
        self.init_ui()

    def init_ui(self):
        """Initializes the current branch tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Branch Selection/Creation Section
        branch_control_group = QFrame()
        branch_control_layout = QVBoxLayout(branch_control_group)
        branch_control_layout.addWidget(QLabel("Manage Branches:"))

        branch_selector_layout = QHBoxLayout()
        self.branch_selector_combobox = QComboBox()
        self.branch_selector_combobox.setMinimumWidth(200)
        self.branch_selector_combobox.addItem("Loading branches...")
        self.branch_selector_combobox.setEnabled(False) # Disable until repo is loaded
        self.branch_selector_combobox.currentIndexChanged.connect(self.on_branch_selected)
        branch_selector_layout.addWidget(self.branch_selector_combobox)

        self.new_branch_name_input = QLineEdit()
        self.new_branch_name_input.setPlaceholderText("Enter new branch name")
        self.new_branch_name_input.setVisible(False) # Hidden by default
        branch_selector_layout.addWidget(self.new_branch_name_input)

        self.go_create_branch_button = QPushButton("Go to Branch")
        self.go_create_branch_button.clicked.connect(self.go_or_create_branch)
        self.go_create_branch_button.setEnabled(False) # Disable until repo is loaded
        branch_selector_layout.addWidget(self.go_create_branch_button)
        branch_selector_layout.addStretch(1)
        branch_control_layout.addLayout(branch_selector_layout)
        layout.addWidget(branch_control_group)

        # Git Operations Section
        git_ops_group = QFrame()
        git_ops_layout = QVBoxLayout(git_ops_group)
        git_ops_layout.addWidget(QLabel("Git Operations:"))

        # Define a consistent button width
        button_width = 100 

        # Main horizontal layout to hold vertical columns of buttons
        # This will contain two sub-layouts: one for left-aligned buttons, one for right-aligned
        main_buttons_horizontal_layout = QHBoxLayout()
        main_buttons_horizontal_layout.setSpacing(20) # Spacing between main groups

        # Left-aligned button groups container
        left_buttons_container_layout = QHBoxLayout()
        left_buttons_container_layout.setContentsMargins(0, 0, 0, 0)
        left_buttons_container_layout.setSpacing(20) # Spacing between vertical columns on the left

        # Column 1: Remote Operations (Fetch, Pull)
        remote_ops_column_layout = QVBoxLayout()
        remote_ops_column_layout.setContentsMargins(0, 0, 0, 0) # No internal padding
        remote_ops_column_layout.setSpacing(5) # Reduced spacing between buttons in this column
        self.fetch_button = QPushButton("Fetch")
        self.fetch_button.clicked.connect(self.fetch_repository)
        self.fetch_button.setEnabled(False)
        self.fetch_button.setFixedWidth(button_width)
        remote_ops_column_layout.addWidget(self.fetch_button)

        self.pull_button = QPushButton("Pull")
        self.pull_button.clicked.connect(self.pull_repository)
        self.pull_button.setEnabled(False)
        self.pull_button.setFixedWidth(button_width)
        remote_ops_column_layout.addWidget(self.pull_button)
        left_buttons_container_layout.addLayout(remote_ops_column_layout)

        # Column 2: Staging Operations (Add, Add All)
        staging_ops_column_layout = QVBoxLayout()
        staging_ops_column_layout.setContentsMargins(0, 0, 0, 0)
        staging_ops_column_layout.setSpacing(5) # Reduced spacing between buttons in this column
        self.add_button = QPushButton("Add...")
        self.add_button.clicked.connect(self.add_file_to_stage)
        self.add_button.setEnabled(False)
        self.add_button.setFixedWidth(button_width)
        staging_ops_column_layout.addWidget(self.add_button)

        self.add_all_button = QPushButton("Add All")
        self.add_all_button.clicked.connect(self.add_all_to_stage)
        self.add_all_button.setEnabled(False)
        self.add_all_button.setFixedWidth(button_width)
        staging_ops_column_layout.addWidget(self.add_all_button)
        left_buttons_container_layout.addLayout(staging_ops_column_layout)

        # Column 3: Commit & Push Operations (Commit, Push)
        commit_push_ops_column_layout = QVBoxLayout()
        commit_push_ops_column_layout.setContentsMargins(0, 0, 0, 0)
        commit_push_ops_column_layout.setSpacing(5) # Reduced spacing between buttons in this column
        self.commit_button = QPushButton("Commit")
        self.commit_button.clicked.connect(self.commit_repository)
        self.commit_button.setEnabled(False)
        self.commit_button.setFixedWidth(button_width)
        commit_push_ops_column_layout.addWidget(self.commit_button)
        
        self.push_button = QPushButton("Push")
        self.push_button.clicked.connect(self.push_repository)
        self.push_button.setEnabled(False)
        self.push_button.setFixedWidth(button_width)
        commit_push_ops_column_layout.addWidget(self.push_button)
        left_buttons_container_layout.addLayout(commit_push_ops_column_layout)

        main_buttons_horizontal_layout.addLayout(left_buttons_container_layout)
        main_buttons_horizontal_layout.addStretch(1) # Stretch to push right-aligned buttons to the right

        # Right-aligned button groups container
        right_buttons_container_layout = QHBoxLayout()
        right_buttons_container_layout.setContentsMargins(0, 0, 0, 0)
        right_buttons_container_layout.setSpacing(20) # Spacing between vertical columns on the right
        right_buttons_container_layout.setAlignment(Qt.AlignRight) # Align this container to the right

        # Column 4: Stash Operations (Stash, Apply Stash)
        stash_ops_column_layout = QVBoxLayout()
        stash_ops_column_layout.setContentsMargins(0, 0, 0, 0)
        stash_ops_column_layout.setSpacing(5) # Reduced spacing between buttons in this column
        self.stash_button = QPushButton("Stash")
        self.stash_button.clicked.connect(self.stash_changes)
        self.stash_button.setEnabled(False)
        self.stash_button.setFixedWidth(button_width)
        stash_ops_column_layout.addWidget(self.stash_button)

        self.apply_stash_button = QPushButton("Apply Stash")
        self.apply_stash_button.clicked.connect(self.apply_stash)
        self.apply_stash_button.setEnabled(False)
        self.apply_stash_button.setFixedWidth(button_width)
        stash_ops_column_layout.addWidget(self.apply_stash_button)
        right_buttons_container_layout.addLayout(stash_ops_column_layout)

        # Column 5: History Manipulation (Reset, Revert)
        history_ops_column_layout = QVBoxLayout()
        history_ops_column_layout.setContentsMargins(0, 0, 0, 0)
        history_ops_column_layout.setSpacing(5) # Reduced spacing between buttons in this column
        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset_repository)
        self.reset_button.setEnabled(False)
        self.reset_button.setFixedWidth(button_width)
        history_ops_column_layout.addWidget(self.reset_button)

        self.revert_button = QPushButton("Revert")
        self.revert_button.clicked.connect(self.revert_repository)
        self.revert_button.setEnabled(False)
        self.revert_button.setFixedWidth(button_width)
        history_ops_column_layout.addWidget(self.revert_button)
        right_buttons_container_layout.addLayout(history_ops_column_layout)

        main_buttons_horizontal_layout.addLayout(right_buttons_container_layout)
        git_ops_layout.addLayout(main_buttons_horizontal_layout)

        layout.addWidget(git_ops_group)
        layout.addStretch(1)

        # Tab Widget for Commit Graph and Git Log
        self.info_tab_widget = QTabWidget()
        
        # Tab 1: Commit Graph
        commit_graph_tab = QWidget()
        commit_graph_layout = QVBoxLayout(commit_graph_tab)
        commit_graph_layout.setContentsMargins(0, 0, 0, 0) # Remove extra margins
        # Removed self.current_branch_label from this layout
        self.git_graph_widget = GitGraphWidget()
        commit_graph_layout.addWidget(self.git_graph_widget)
        self.info_tab_widget.addTab(commit_graph_tab, "Commit Graph")

        # Tab 2: Git Log
        git_log_tab = QWidget()
        git_log_layout = QVBoxLayout(git_log_tab)
        git_log_layout.setContentsMargins(0, 0, 0, 0) # Remove extra margins
        self.git_log_text_edit = QTextEdit()
        self.git_log_text_edit.setReadOnly(True)
        self.git_log_text_edit.setLineWrapMode(QTextEdit.NoWrap) # Prevent wrapping for log readability
        git_log_layout.addWidget(self.git_log_text_edit)
        self.info_tab_widget.addTab(git_log_tab, "Git Log")

        layout.addWidget(self.info_tab_widget)

        # Action Button to Load Info (still useful for manual refresh)
        load_button = QPushButton("Refresh Repository Info") # Renamed for clarity
        load_button.clicked.connect(self.load_repository_info)
        layout.addWidget(load_button)

    def set_selected_repo_path(self, path):
        """Called by GitBuddyApp to update the selected repository path."""
        self.current_selected_repo_path = path
        # Optionally, auto-load info if a valid path is provided
        if path and os.path.isdir(os.path.join(path, ".git")):
            self.load_repository_info()
            self.branch_selector_combobox.setEnabled(True)
            self.go_create_branch_button.setEnabled(True)
            self.fetch_button.setEnabled(True) # Enable Fetch button
            self.pull_button.setEnabled(True)
            self.commit_button.setEnabled(True)
            self.push_button.setEnabled(True)
            self.stash_button.setEnabled(True) # Enable Stash button
            self.apply_stash_button.setEnabled(True) # Enable Apply Stash button
            self.add_button.setEnabled(True) # Enable Add button
            self.add_all_button.setEnabled(True) # Enable Add All button
            self.reset_button.setEnabled(True) # Enable Reset button
            self.revert_button.setEnabled(True) # Enable Revert button
        else:
            self.git_graph_widget.set_commits_data([]) # Clear graph
            self.git_log_text_edit.clear() # Clear log
            self.branch_selector_combobox.clear()
            self.branch_selector_combobox.addItem("No repository selected")
            self.branch_selector_combobox.setEnabled(False)
            self.go_create_branch_button.setEnabled(False)
            self.new_branch_name_input.setVisible(False)
            self.fetch_button.setEnabled(False) # Disable Fetch button
            self.pull_button.setEnabled(False)
            self.commit_button.setEnabled(False)
            self.push_button.setEnabled(False)
            self.stash_button.setEnabled(False) # Disable Stash button
            self.apply_stash_button.setEnabled(False) # Disable Apply Stash button
            self.add_button.setEnabled(False) # Disable Add button
            self.add_all_button.setEnabled(False) # Disable Add All button
            self.reset_button.setEnabled(False) # Disable Reset button
            self.revert_button.setEnabled(False) # Disable Revert button


    def run_git_command(self, repo_path, command_args, timeout=60):
        """Helper function to run a git command in a specified repository."""
        if not os.path.isdir(repo_path):
            return False, "Error: Path is not a directory."
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            return False, "Error: Not a Git repository."

        full_command = ['git'] + command_args
        try:
            result = subprocess.run(
                full_command,
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return False, f"Git command failed: {e.stderr.strip()}"
        except FileNotFoundError:
            return False, "Error: 'git' command not found. Please ensure Git is installed and in your PATH."
        except subprocess.TimeoutExpired:
            return False, f"Error: Git command timed out after {timeout} seconds."
        except Exception as e:
            return False, f"An unexpected error occurred: {e}"

    def populate_branch_selector(self):
        """Populates the branch selector combobox with local branches."""
        self.branch_selector_combobox.clear()
        repo_path = self.current_selected_repo_path
        if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
            self.branch_selector_combobox.addItem("No repository selected")
            self.branch_selector_combobox.setEnabled(False)
            self.go_create_branch_button.setEnabled(False)
            return

        success, branches_output = self.run_git_command(repo_path, ['branch', '--list'])
        if success:
            branches = []
            current_branch = ""
            for line in branches_output.split('\n'):
                line = line.strip()
                if line.startswith('*'):
                    current_branch = line[1:].strip()
                    branches.insert(0, current_branch) # Put current branch at top
                elif line:
                    branches.append(line.strip())
            
            # Add current branch first, then others
            for branch in branches:
                self.branch_selector_combobox.addItem(branch)
            
            self.branch_selector_combobox.addItem("-- Create New Branch... --")
            self.branch_selector_combobox.setEnabled(True)
            self.go_create_branch_button.setEnabled(True)

            # Set the current branch in the combobox
            if current_branch:
                index = self.branch_selector_combobox.findText(current_branch)
                if index != -1:
                    self.branch_selector_combobox.setCurrentIndex(index)
            # Removed self.current_branch_label.setText(f"Current Branch: {current_branch}")
        else:
            QMessageBox.critical(self, "Git Error", f"Failed to list branches: {branches_output}")
            self.branch_selector_combobox.addItem("Error loading branches")
            self.branch_selector_combobox.setEnabled(False)
            self.go_create_branch_button.setEnabled(False)

    def on_branch_selected(self, index):
        """Handles selection in the branch combobox."""
        selected_text = self.branch_selector_combobox.currentText()
        if selected_text == "-- Create New Branch... --":
            self.new_branch_name_input.setVisible(True)
            self.new_branch_name_input.clear()
            self.new_branch_name_input.setFocus()
            self.go_create_branch_button.setText("Create Branch")
        else:
            self.new_branch_name_input.setVisible(False)
            self.go_create_branch_button.setText("Go to Branch")

    def go_or_create_branch(self):
        """Performs git checkout or git checkout -b based on selection."""
        repo_path = self.current_selected_repo_path
        if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
            QMessageBox.warning(self, "No Repository", "Please select a valid Git repository first.")
            return

        selected_text = self.branch_selector_combobox.currentText()

        if selected_text == "-- Create New Branch... --":
            new_branch_name = self.new_branch_name_input.text().strip()
            if not new_branch_name:
                QMessageBox.warning(self, "Input Error", "Please enter a name for the new branch.")
                return
            
            success, message = self.run_git_command(repo_path, ['checkout', '-b', new_branch_name])
            if success:
                QMessageBox.information(self, "Branch Created", f"Successfully created and switched to branch '{new_branch_name}'.")
                self.load_repository_info() # Refresh UI
            else:
                QMessageBox.critical(self, "Git Error", f"Failed to create branch '{new_branch_name}':\n{message}")
        else:
            # Check if already on the selected branch
            success_current, current_branch_name = self.run_git_command(repo_path, ['rev-parse', '--abbrev-ref', 'HEAD'])
            if success_current and current_branch_name == selected_text:
                QMessageBox.information(self, "Branch Status", f"Already on branch '{selected_text}'.")
                return

            success, message = self.run_git_command(repo_path, ['checkout', selected_text])
            if success:
                QMessageBox.information(self, "Branch Switched", f"Successfully switched to branch '{selected_text}'.")
                self.load_repository_info() # Refresh UI
            else:
                QMessageBox.critical(self, "Git Error", f"Failed to switch to branch '{selected_text}':\n{message}")


    def load_repository_info(self):
        """Loads and displays information about the selected Git repository."""
        repo_path = self.current_selected_repo_path # Use the globally selected path
        if not repo_path:
            self.git_graph_widget.set_commits_data([])
            self.git_log_text_edit.clear() # Clear log
            self.populate_branch_selector() # Clear/reset branch selector
            return

        # Validate if it's a valid git repository before proceeding
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            QMessageBox.warning(self, "Not a Git Repository",
                                f"The selected directory '{repo_path}' does not appear to be a Git repository (missing .git folder).")
            self.git_graph_widget.set_commits_data([])
            self.git_log_text_edit.clear() # Clear log
            self.populate_branch_selector() # Clear/reset branch selector
            return

        success, branch_output = self.run_git_command(repo_path, ['rev-parse', '--abbrev-ref', 'HEAD'])
        if success:
            pass # Removed self.current_branch_label.setText(f"Current Branch: {branch_output}")
        else:
            self.git_graph_widget.set_commits_data([])
            self.git_log_text_edit.clear() # Clear log
            QMessageBox.critical(self, "Git Error", branch_output)
            self.populate_branch_selector() # Clear/reset branch selector
            return

        self.populate_branch_selector() # Refresh branch selector after getting current branch

        # Get commit history for graph visualization (formatted for parsing)
        success_graph, log_output_graph = self.run_git_command(
            repo_path,
            ['log', '--pretty=format:%H|%P|%s', '-n', '20'] # Limit for graph readability
        )

        if success_graph:
            commits_data = []
            for line in log_output_graph.split('\n'):
                if not line.strip():
                    continue
                parts = line.split('|', 2) # Split into hash, parents, message
                if len(parts) == 3:
                    commit_hash = parts[0]
                    parent_hashes = parts[1].split() # Parents are space-separated
                    message = parts[2]
                    commits_data.append({
                        'hash': commit_hash,
                        'parents': parent_hashes,
                        'message': message
                    })
            self.git_graph_widget.set_commits_data(commits_data)
        else:
            self.git_graph_widget.set_commits_data([])
            QMessageBox.critical(self, "Git Log Graph Error", log_output_graph)


        # Get full commit log for text display
        success_log, full_log_output = self.run_git_command(
            repo_path,
            ['log', '--pretty=format:%h %s (%an, %ar)'] # More readable format for text display
        )

        if success_log:
            self.git_log_text_edit.setText(full_log_output)
        else:
            self.git_log_text_edit.clear()
            QMessageBox.critical(self, "Git Log Text Error", full_log_output)


    def fetch_repository(self):
        """Performs a git fetch on the selected repository."""
        repo_path = self.current_selected_repo_path
        if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
            QMessageBox.warning(self, "No Repository", "Please select a valid Git repository first.")
            return

        success, output = self.run_git_command(repo_path, ['fetch', '--all'])
        if success:
            QMessageBox.information(self, "Fetch Success", f"Successfully fetched changes:\n{output}")
            self.load_repository_info() # Refresh UI after fetch
        else:
            QMessageBox.critical(self, "Fetch Failed", f"Failed to fetch changes:\n{output}")

    def pull_repository(self):
        """Performs a git pull on the selected repository."""
        repo_path = self.current_selected_repo_path
        if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
            QMessageBox.warning(self, "No Repository", "Please select a valid Git repository first.")
            return

        success, output = self.run_git_command(repo_path, ['pull'])
        if success:
            if "Already up to date." in output or "Already up-to-date." in output:
                QMessageBox.information(self, "Pull Status", "Repository is already up to date.")
            else:
                QMessageBox.information(self, "Pull Success", f"Successfully pulled changes:\n{output}")
            self.load_repository_info() # Refresh UI after pull
        else:
            QMessageBox.critical(self, "Pull Failed", f"Failed to pull changes:\n{output}")

    def commit_repository(self):
        """Stages all changes and commits them with the provided message from a dialog."""
        repo_path = self.current_selected_repo_path
        if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
            QMessageBox.warning(self, "No Repository", "Please select a valid Git repository first.")
            return

        # Check for untracked files or modified files first
        success_status, status_output = self.run_git_command(repo_path, ['status', '--porcelain'])
        if not success_status:
            QMessageBox.critical(self, "Git Status Error", f"Failed to get git status: {status_output}")
            return

        if not status_output.strip():
            QMessageBox.information(self, "No Changes", "No changes detected to commit.")
            return

        # Get commit message from a dialog
        commit_message, ok = QInputDialog.getText(self, "Commit Message",
                                                  "Enter commit message:",
                                                  QLineEdit.Normal,
                                                  "Feature: Add new functionality")
        if not ok or not commit_message.strip():
            QMessageBox.warning(self, "Input Error", "Commit cancelled or no message entered.")
            return
        
        # Add a timestamp to the commit message for better tracking
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        final_commit_message = f"{commit_message.strip()} [GitBuddy: {timestamp}]"

        # Add all changes
        success_add, add_output = self.run_git_command(repo_path, ['add', '.'])
        if not success_add:
            QMessageBox.critical(self, "Commit Failed", f"Failed to stage changes:\n{add_output}")
            return

        # Commit changes
        success_commit, commit_output = self.run_git_command(repo_path, ['commit', '-m', final_commit_message])
        if success_commit:
            QMessageBox.information(self, "Commit Success", f"Successfully committed changes:\n{commit_output}")
            self.load_repository_info() # Refresh UI after commit
        else:
            QMessageBox.critical(self, "Commit Failed", f"Failed to commit changes:\n{commit_output}")

    def push_repository(self):
        """Performs a git push on the selected repository."""
        repo_path = self.current_selected_repo_path
        if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
            QMessageBox.warning(self, "No Repository", "Please select a valid Git repository first.")
            return

        # Determine current branch
        success_branch, branch_name = self.run_git_command(repo_path, ['rev-parse', '--abbrev-ref', 'HEAD'])
        if not success_branch:
            QMessageBox.critical(self, "Push Failed", f"Could not determine current branch:\n{branch_name}")
            return

        # Check if there's an upstream branch set
        success_upstream, upstream_info = self.run_git_command(repo_path, ['rev-parse', '--abbrev-ref', '@{upstream}'], timeout=10)
        
        push_command = ['push']
        if not success_upstream or "fatal" in upstream_info.lower():
            # No upstream set, try to set it to origin/current_branch
            reply = QMessageBox.question(self, "Set Upstream?",
                                         f"No upstream branch is set for '{branch_name}'. Do you want to set it to 'origin/{branch_name}'?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                push_command.extend(['--set-upstream', 'origin', branch_name])
            else:
                QMessageBox.warning(self, "Push Cancelled", "Push cancelled. Upstream branch not set.")
                return
        
        success, output = self.run_git_command(repo_path, push_command)

        if success:
            QMessageBox.information(self, "Push Success", f"Successfully pushed changes:\n{output}")
            self.load_repository_info() # Refresh UI after push
        else:
            QMessageBox.critical(self, "Push Failed", f"Failed to push changes:\n{output}")

    def stash_changes(self):
        """Stashes current changes in the repository."""
        repo_path = self.current_selected_repo_path
        if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
            QMessageBox.warning(self, "No Repository", "Please select a valid Git repository first.")
            return

        # Check if there are any changes to stash
        success_status, status_output = self.run_git_command(repo_path, ['status', '--porcelain'])
        if not success_status:
            QMessageBox.critical(self, "Git Status Error", f"Failed to get git status: {status_output}")
            return

        if not status_output.strip():
            QMessageBox.information(self, "No Changes", "No changes detected to stash.")
            return

        stash_message, ok = QInputDialog.getText(self, "Stash Message (Optional)",
                                                  "Enter a message for your stash (optional):",
                                                  QLineEdit.Normal,
                                                  "WIP: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        stash_command = ['stash', 'push']
        if ok and stash_message.strip():
            stash_command.extend(['-m', stash_message.strip()])

        success, output = self.run_git_command(repo_path, stash_command)
        if success:
            QMessageBox.information(self, "Stash Success", f"Successfully stashed changes:\n{output}")
            self.load_repository_info() # Refresh UI after stash
        else:
            QMessageBox.critical(self, "Stash Failed", f"Failed to stash changes:\n{output}")

    def apply_stash(self):
        """Applies the latest stash from the repository."""
        repo_path = self.current_selected_repo_path
        if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
            QMessageBox.warning(self, "No Repository", "Please select a valid Git repository first.")
            return
        
        # Check if there are any stashes
        success_list, list_output = self.run_git_command(repo_path, ['stash', 'list'])
        if not success_list:
            QMessageBox.critical(self, "Stash List Error", f"Failed to list stashes: {list_output}")
            return
        
        if not list_output.strip():
            QMessageBox.information(self, "No Stashes", "No stashes found to apply.")
            return

        # For simplicity, we'll apply the latest stash (stash@{0})
        # A more advanced feature would be to list stashes and let the user choose.
        reply = QMessageBox.question(self, "Apply Latest Stash",
                                     "Do you want to apply the latest stash (stash@{0})?\n"
                                     "This will reapply the stashed changes to your working directory.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.No:
            return

        success, output = self.run_git_command(repo_path, ['stash', 'apply'])
        if success:
            QMessageBox.information(self, "Apply Stash Success", f"Successfully applied stash:\n{output}")
            self.load_repository_info() # Refresh UI after applying stash
        else:
            QMessageBox.critical(self, "Apply Stash Failed", f"Failed to apply stash:\n{output}\n"
                                 "You might have conflicts. Resolve them manually or use 'git stash drop' if no longer needed.")

    def add_file_to_stage(self):
        """Opens a file dialog to select files to add to the staging area."""
        repo_path = self.current_selected_repo_path
        if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
            QMessageBox.warning(self, "No Repository", "Please select a valid Git repository first.")
            return

        # Get list of untracked/modified files to pre-select or suggest
        success_status, status_output = self.run_git_command(repo_path, ['status', '--porcelain'])
        if not success_status:
            QMessageBox.critical(self, "Git Status Error", f"Failed to get git status: {status_output}")
            return

        # Extract file paths from status output (ignoring directories for now)
        # This is a basic parsing, might need refinement for complex cases
        untracked_or_modified_files = []
        for line in status_output.split('\n'):
            if line.strip():
                # Lines typically look like " M file.txt" or "?? untracked.txt"
                # We want the path after the status codes
                parts = line.strip().split(' ', 1)
                if len(parts) > 1:
                    file_path = parts[1].strip()
                    # Exclude directories if they are listed, focus on files
                    if os.path.isfile(os.path.join(repo_path, file_path)):
                        untracked_or_modified_files.append(file_path)

        # Open file dialog to select files relative to the repository root
        # QFileDialog.getOpenFileNames returns a tuple (filenames, filter)
        selected_files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files to Add to Staging",
            repo_path, # Start browsing from the repository root
            "All Files (*);;Text Files (*.txt);;Python Files (*.py)", # Filters
            options=QFileDialog.DontUseNativeDialog # Important for consistent behavior
        )

        if not selected_files:
            return

        # Convert absolute paths back to paths relative to the repository for 'git add'
        relative_paths = []
        for file_path in selected_files:
            relative_path = os.path.relpath(file_path, repo_path)
            relative_paths.append(relative_path)
        
        if not relative_paths:
            QMessageBox.warning(self, "No Valid Files", "Selected files are not within the repository or could not be resolved.")
            return

        # Run git add for each selected file
        add_successful = True
        add_output_messages = []
        for rel_path in relative_paths:
            success, output = self.run_git_command(repo_path, ['add', rel_path])
            if not success:
                add_successful = False
                add_output_messages.append(f"Failed to add '{rel_path}': {output}")
            else:
                add_output_messages.append(f"Successfully added '{rel_path}'.")

        if add_successful:
            QMessageBox.information(self, "Add Success", "Successfully added selected files:\n" + "\n".join(add_output_messages))
        else:
            QMessageBox.critical(self, "Add Failed", "Some files failed to add:\n" + "\n".join(add_output_messages))
        
        self.load_repository_info() # Refresh UI after adding files

    def add_all_to_stage(self):
        """Adds all changes (tracked and untracked) to the staging area."""
        repo_path = self.current_selected_repo_path
        if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
            QMessageBox.warning(self, "No Repository", "Please select a valid Git repository first.")
            return

        reply = QMessageBox.question(self, "Confirm Add All",
                                     "Are you sure you want to add ALL modified and untracked files to the staging area?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        success, output = self.run_git_command(repo_path, ['add', '.'])
        if success:
            QMessageBox.information(self, "Add All Success", f"Successfully added all changes:\n{output}")
            self.load_repository_info() # Refresh UI after adding all
        else:
            QMessageBox.critical(self, "Add All Failed", f"Failed to add all changes:\n{output}")

    def reset_repository(self):
        """Performs a git reset operation based on user selection."""
        repo_path = self.current_selected_repo_path
        if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
            QMessageBox.warning(self, "No Repository", "Please select a valid Git repository first.")
            return

        reset_options = ["Soft (undo last commit, keep changes staged)",
                         "Mixed (undo last commit, keep changes unstaged)",
                         "Hard (undo last commit, discard all changes)"]
        
        reset_choice, ok = QInputDialog.getItem(self, "Git Reset Type",
                                                 "Select reset type:",
                                                 reset_options, 0, False)
        
        if not ok:
            QMessageBox.information(self, "Reset Cancelled", "Git reset operation cancelled.")
            return

        command_args = []
        confirmation_message = ""

        if reset_choice == reset_options[0]: # Soft
            command_args = ['reset', '--soft', 'HEAD~1']
            confirmation_message = "Are you sure you want to perform a SOFT reset (undo last commit, keep changes staged)?"
        elif reset_choice == reset_options[1]: # Mixed
            command_args = ['reset', '--mixed', 'HEAD~1']
            confirmation_message = "Are you sure you want to perform a MIXED reset (undo last commit, keep changes unstaged)?"
        elif reset_choice == reset_options[2]: # Hard
            command_args = ['reset', '--hard', 'HEAD~1']
            confirmation_message = "WARNING: Are you sure you want to perform a HARD reset (undo last commit, DISCARD ALL CHANGES)? This cannot be undone!"
            
        reply = QMessageBox.question(self, "Confirm Reset",
                                     confirmation_message,
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            QMessageBox.information(self, "Reset Cancelled", "Git reset operation cancelled.")
            return

        success, output = self.run_git_command(repo_path, command_args)
        if success:
            QMessageBox.information(self, "Reset Success", f"Successfully performed git reset:\n{output}")
            self.load_repository_info() # Refresh UI after reset
        else:
            QMessageBox.critical(self, "Reset Failed", f"Failed to perform git reset:\n{output}")

    def revert_repository(self):
        """Performs a git revert operation by prompting for a commit hash."""
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

        success, output = self.run_git_command(repo_path, ['revert', commit_hash.strip()])
        if success:
            QMessageBox.information(self, "Revert Success", f"Successfully reverted commit:\n{output}")
            self.load_repository_info() # Refresh UI after revert
        else:
            QMessageBox.critical(self, "Revert Failed", f"Failed to revert commit:\n{output}")
