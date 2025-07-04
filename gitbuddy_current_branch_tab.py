# gitbuddy_current_branch_tab.py

import os
import subprocess
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel,
    QFileDialog, QMessageBox, QFrame, QSizePolicy, QComboBox, QInputDialog # Added QInputDialog
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

        # Git Operations Section (Fetch, Pull, Commit, Push)
        git_ops_group = QFrame()
        git_ops_layout = QVBoxLayout(git_ops_group)
        git_ops_layout.addWidget(QLabel("Git Operations:"))

        # Define a consistent button width
        button_width = 150 # This width should accommodate "Commit All Changes"

        # First row: Fetch, Commit Button
        top_row_layout = QHBoxLayout()

        # Fetch Button
        self.fetch_button = QPushButton("Fetch")
        self.fetch_button.clicked.connect(self.fetch_repository)
        self.fetch_button.setEnabled(False)
        self.fetch_button.setFixedWidth(button_width) # Set fixed width
        top_row_layout.addWidget(self.fetch_button)

        # Commit Button (now triggers dialog)
        self.commit_button = QPushButton("Commit") # Changed text to "Commit"
        self.commit_button.clicked.connect(self.commit_repository)
        self.commit_button.setEnabled(False)
        self.commit_button.setFixedWidth(button_width) # Set fixed width
        top_row_layout.addWidget(self.commit_button)

        top_row_layout.addStretch(1) # Add stretch to push elements to the left

        git_ops_layout.addLayout(top_row_layout)

        # Second row: Pull, Push
        bottom_row_layout = QHBoxLayout()

        # Pull Button
        self.pull_button = QPushButton("Pull")
        self.pull_button.clicked.connect(self.pull_repository)
        self.pull_button.setEnabled(False)
        self.pull_button.setFixedWidth(button_width) # Set fixed width
        bottom_row_layout.addWidget(self.pull_button)

        # Push Button
        self.push_button = QPushButton("Push")
        self.push_button.clicked.connect(self.push_repository)
        self.push_button.setEnabled(False)
        self.push_button.setFixedWidth(button_width) # Set fixed width
        bottom_row_layout.addWidget(self.push_button)
        bottom_row_layout.addStretch(1) # Add stretch to push elements to the left

        git_ops_layout.addLayout(bottom_row_layout)

        layout.addWidget(git_ops_group)

        layout.addStretch(1)

        # Display Area for Branch Info
        info_frame = QFrame()
        info_frame.setObjectName("infoFrame")
        info_layout = QVBoxLayout(info_frame)
        
        info_layout.addWidget(QLabel("Commit Graph:"))
        self.git_graph_widget = GitGraphWidget()
        info_layout.addWidget(self.git_graph_widget)
        
        layout.addWidget(info_frame)

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
        else:
            self.git_graph_widget.set_commits_data([]) # Clear graph
            self.branch_selector_combobox.clear()
            self.branch_selector_combobox.addItem("No repository selected")
            self.branch_selector_combobox.setEnabled(False)
            self.go_create_branch_button.setEnabled(False)
            self.new_branch_name_input.setVisible(False)
            self.fetch_button.setEnabled(False) # Disable Fetch button
            self.pull_button.setEnabled(False)
            self.commit_button.setEnabled(False)
            self.push_button.setEnabled(False)


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
                self.load_repository_info() # Refresh UI
            else:
                QMessageBox.critical(self, "Git Error", f"Failed to create branch '{new_branch_name}':\n{message}")
        else:
            # Check if already on the selected branch
            success_current, current_branch_name = self.run_git_command(repo_path, ['rev-parse', '--abbrev-ref', 'HEAD'])
            if success_current and current_branch_name == selected_text:
                return

            success, message = self.run_git_command(repo_path, ['checkout', selected_text])
            if success:
                self.load_repository_info() # Refresh UI
            else:
                QMessageBox.critical(self, "Git Error", f"Failed to switch to branch '{selected_text}':\n{message}")


    def load_repository_info(self):
        """Loads and displays information about the selected Git repository."""
        repo_path = self.current_selected_repo_path # Use the globally selected path
        if not repo_path:
            self.git_graph_widget.set_commits_data([])
            self.populate_branch_selector() # Clear/reset branch selector
            return

        # Validate if it's a valid git repository before proceeding
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            QMessageBox.warning(self, "Not a Git Repository",
                                f"The selected directory '{repo_path}' does not appear to be a Git repository (missing .git folder).")
            self.git_graph_widget.set_commits_data([])
            self.populate_branch_selector() # Clear/reset branch selector
            return

        success, branch_output = self.run_git_command(repo_path, ['rev-parse', '--abbrev-ref', 'HEAD'])
        if success:
            pass # Keep this pass to indicate intentional removal
        else:
            self.git_graph_widget.set_commits_data([])
            QMessageBox.critical(self, "Git Error", branch_output)
            self.populate_branch_selector() # Clear/reset branch selector
            return

        self.populate_branch_selector() # Refresh branch selector after getting current branch

        success, log_output = self.run_git_command(
            repo_path,
            ['log', '--pretty=format:%H|%P|%s', '-n', '20']
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
            QMessageBox.critical(self, "Git Log Error", log_output)

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
