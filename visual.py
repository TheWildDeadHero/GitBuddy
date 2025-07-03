# git_branch_viewer.py

import sys
import os
import subprocess
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QTextEdit, QFileDialog, QMessageBox,
    QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QDir, QPointF, QRectF
from PySide6.QtGui import QPalette, QColor, QPainter, QPen, QBrush, QFontMetrics

# --- Custom Widget for Git Graph Visualization ---
class GitGraphWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.commits_data = [] # Stores parsed commit objects for drawing
        self.commit_positions = {} # Maps commit hash to its (x, y) drawing position
        self.setMinimumHeight(200) # Ensure some initial height
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Drawing parameters
        self.COMMIT_RADIUS = 5
        self.COMMIT_SPACING_Y = 30
        self.LANE_SPACING_X = 20
        self.TEXT_OFFSET_X = 15 # Offset for commit message from the graph line

    def set_commits_data(self, data):
        """Sets the commit data to be visualized."""
        self.commits_data = data
        self.update_commit_positions()
        self.update() # Request a repaint

    def update_commit_positions(self):
        """Calculates the drawing positions for each commit."""
        self.commit_positions = {}
        if not self.commits_data:
            return

        # Simple linear layout for now. For complex graphs, a lane-finding algorithm is needed.
        # This approach will stack commits vertically and try to draw parents.
        y_pos = self.COMMIT_SPACING_Y / 2
        for i, commit in enumerate(self.commits_data):
            # Assign a temporary lane for simple drawing
            commit['lane'] = 0 # All commits start in lane 0 for simplicity
            x_pos = self.LANE_SPACING_X # Start at the first lane
            self.commit_positions[commit['hash']] = QPointF(x_pos, y_pos)
            y_pos += self.COMMIT_SPACING_Y
        
        # Adjust widget size based on content
        self.setMinimumHeight(int(y_pos))
        self.setMaximumHeight(int(y_pos)) # Fix height to content for simple layout

    def paintEvent(self, event):
        """Draws the Git graph."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if not self.commits_data:
            painter.drawText(self.rect(), Qt.AlignCenter, "No Git history to display.")
            return

        # Get system palette for colors
        palette = self.palette()
        text_color = palette.color(QPalette.WindowText)
        line_color = palette.color(QPalette.Mid) # A neutral color for lines
        commit_dot_color = palette.color(QPalette.Highlight) # A prominent color for commit dots

        painter.setPen(QPen(line_color, 1))
        painter.setBrush(QBrush(commit_dot_color))

        # Draw commits and lines
        for i, commit in enumerate(self.commits_data):
            commit_hash = commit['hash']
            commit_message = commit['message']
            commit_pos = self.commit_positions.get(commit_hash)

            if not commit_pos:
                continue

            # Draw commit dot
            painter.drawEllipse(commit_pos, self.COMMIT_RADIUS, self.COMMIT_RADIUS)

            # Draw commit message
            painter.setPen(QPen(text_color))
            # Calculate text rectangle to avoid overlap and align
            text_rect = QRectF(commit_pos.x() + self.COMMIT_RADIUS + self.TEXT_OFFSET_X,
                               commit_pos.y() - self.COMMIT_SPACING_Y / 2,
                               self.width() - (commit_pos.x() + self.COMMIT_RADIUS + self.TEXT_OFFSET_X) - 10, # 10px right margin
                               self.COMMIT_SPACING_Y)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, f"{commit_hash[:7]} {commit_message}")

            # Draw lines to parents
            painter.setPen(QPen(line_color, 1))
            for parent_hash in commit['parents']:
                parent_pos = self.commit_positions.get(parent_hash)
                if parent_pos:
                    # Draw a simple vertical line to the parent's position
                    # This is a very basic visualization and won't handle complex merges perfectly
                    start_point = commit_pos
                    end_point = parent_pos
                    
                    # For a more "graph-like" look, draw from current commit's dot to parent's dot
                    # This simplified approach draws a straight line.
                    painter.drawLine(start_point, end_point)

# --- Main Application Window ---
class GitBranchViewerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Git Branch Viewer")
        self.setGeometry(100, 100, 800, 600) # x, y, width, height

        self.init_ui()

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
                border-radius: 12px;
            }
            QLineEdit {
                border: 1px solid; /* Use system's default border color */
                border-radius: 8px;
                padding: 8px;
                font-size: 14px;
            }
            QPushButton {
                border: none;
                padding: 10px 20px;
                text-align: center;
                text-decoration: none;
                font-size: 14px;
                margin: 4px 2px;
                border-radius: 8px;
                box-shadow: 2px 2px 5px rgba(0, 0, 0, 0.2);
                min-width: 120px;
            }
            QPushButton:hover {
                /* Let system theme handle hover effects */
            }
            QPushButton:pressed {
                box-shadow: inset 1px 1px 3px rgba(0, 0, 0, 0.3);
            }
            QLabel {
                font-size: 15px;
                font-weight: bold;
            }
            QFrame#infoFrame {
                border: 1px solid;
                border-radius: 10px;
                padding: 10px;
            }
            QLabel#branchLabel {
                font-size: 16px;
                font-weight: bold;
            }
        """)

        # Repository Path Selection
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Repository Path:"))
        self.repo_path_input = QLineEdit()
        self.repo_path_input.setPlaceholderText("Select a local Git repository directory...")
        self.repo_path_input.setReadOnly(True) # Make it read-only, only allow selection via browse button
        path_layout.addWidget(self.repo_path_input)

        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_for_repository)
        path_layout.addWidget(browse_button)
        main_layout.addLayout(path_layout)

        # Display Area for Branch Info
        info_frame = QFrame()
        info_frame.setObjectName("infoFrame")
        info_layout = QVBoxLayout(info_frame)
        
        self.current_branch_label = QLabel("Current Branch: N/A")
        self.current_branch_label.setObjectName("branchLabel")
        info_layout.addWidget(self.current_branch_label)

        info_layout.addWidget(QLabel("Commit Graph:"))
        self.git_graph_widget = GitGraphWidget() # Instantiate our custom graph widget
        info_layout.addWidget(self.git_graph_widget)
        
        main_layout.addWidget(info_frame)

        # Action Button to Load Info
        load_button = QPushButton("Load Repository Info")
        load_button.clicked.connect(self.load_repository_info)
        main_layout.addWidget(load_button)

    def browse_for_repository(self):
        """Opens a file dialog to select a Git repository directory."""
        initial_path = self.repo_path_input.text() if self.repo_path_input.text() else QDir.homePath()
        directory = QFileDialog.getExistingDirectory(self, "Select Git Repository Directory", initial_path)
        if directory:
            # Basic check to see if it looks like a Git repo
            if os.path.isdir(os.path.join(directory, ".git")):
                self.repo_path_input.setText(directory)
                self.load_repository_info() # Automatically load info after selection
            else:
                QMessageBox.warning(self, "Not a Git Repository",
                                    f"The selected directory '{directory}' does not appear to be a Git repository (missing .git folder).")
                self.repo_path_input.clear() # Clear invalid path

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

    def load_repository_info(self):
        """Loads and displays information about the selected Git repository."""
        repo_path = self.repo_path_input.text().strip()
        if not repo_path:
            QMessageBox.information(self, "No Repository Selected", "Please select a Git repository directory first.")
            return

        # Get current branch
        success, branch_output = self.run_git_command(repo_path, ['rev-parse', '--abbrev-ref', 'HEAD'])
        if success:
            self.current_branch_label.setText(f"Current Branch: {branch_output}")
        else:
            self.current_branch_label.setText("Current Branch: Error")
            self.git_graph_widget.set_commits_data([]) # Clear graph on error
            QMessageBox.critical(self, "Git Error", branch_output)
            return

        # Get commit history for graph visualization
        # Using --pretty=format:"%H|%P|%s" to get hash, parent hashes, and subject
        # --graph for ASCII graph, but we'll parse the data ourselves for drawing
        # -n 20 to limit to the last 20 commits for performance and readability
        success, log_output = self.run_git_command(
            repo_path,
            ['log', '--pretty=format:%H|%P|%s', '-n', '20']
        )

        if success:
            commits_data = []
            for line in log_output.split('\n'):
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
            self.git_graph_widget.set_commits_data([]) # Clear graph on error
            QMessageBox.critical(self, "Git Log Error", log_output)

        QMessageBox.information(self, "Info Loaded", "Repository information loaded successfully!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GitBranchViewerApp()
    window.show()
    sys.exit(app.exec())
