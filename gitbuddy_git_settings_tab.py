# gitbuddy_git_settings_tab.py

import os
import subprocess
import json
import platform # Import platform to detect OS
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QMessageBox, QGroupBox, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QInputDialog, QFileDialog, QDialog, QRadioButton,
    QButtonGroup, QStackedWidget, QTextEdit, QApplication # Added QTextEdit, QApplication
)
from PySide6.QtCore import Qt, Signal # Import Signal
import logging # Import logging

# Define the path for Git accounts configuration
GIT_ACCOUNTS_FILE = os.path.join(os.path.expanduser("~/.config/git-buddy"), "git_accounts.json")

class AddAccountDialog(QDialog):
    def __init__(self, config_dir, run_command_func, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Git Account")
        self.config_dir = config_dir
        self.run_command = run_command_func # Pass the utility function
        self.generated_private_key_path = None # To store path of newly generated private key
        self.generated_public_key_path = None # To store path of newly generated public key

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Account Details Group
        account_details_group = QGroupBox("Account Details")
        account_details_layout = QVBoxLayout(account_details_group)

        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Username:"))
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("e.g., octocat")
        form_layout.addWidget(self.username_input)
        account_details_layout.addLayout(form_layout)

        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Email:"))
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("e.g., octocat@example.com")
        form_layout.addWidget(self.email_input)
        account_details_layout.addLayout(form_layout)

        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Host:"))
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("e.g., github.com, gitlab.com")
        form_layout.addWidget(self.host_input)
        account_details_layout.addLayout(form_layout)

        account_details_layout.addStretch(1)
        layout.addWidget(account_details_group)

        # SSH Key Management Group
        ssh_key_group = QGroupBox("SSH Key Management")
        ssh_key_layout = QVBoxLayout(ssh_key_group)

        # Key selection radio buttons
        self.key_selection_group = QButtonGroup(self)
        self.generate_new_key_radio = QRadioButton("Generate New SSH Key Pair")
        self.use_existing_key_radio = QRadioButton("Use Existing SSH Private Key")
        self.no_ssh_key_radio = QRadioButton("Do Not Use SSH Key (rely on HTTPS/credential helper)")

        self.key_selection_group.addButton(self.generate_new_key_radio)
        self.key_selection_group.addButton(self.use_existing_key_radio)
        self.key_selection_group.addButton(self.no_ssh_key_radio)

        ssh_key_layout.addWidget(self.generate_new_key_radio)
        ssh_key_layout.addWidget(self.use_existing_key_radio)
        ssh_key_layout.addWidget(self.no_ssh_key_radio)

        # Stacked widget for key options
        self.key_options_stacked_widget = QStackedWidget()

        # Page 0: Generate New Key
        generate_key_page = QWidget()
        generate_key_layout = QVBoxLayout(generate_key_page)
        generate_key_layout.setContentsMargins(0,0,0,0) # No extra margins
        generate_key_layout.setSpacing(5)

        key_path_layout = QHBoxLayout()
        key_path_layout.addWidget(QLabel("Key Save Path:"))
        self.new_key_path_input = QLineEdit()
        self.new_key_path_input.setPlaceholderText("e.g., ~/.ssh/id_rsa_octocat")
        # Set default path to ~/.ssh/id_rsa_username_host
        default_key_name = f"id_rsa_{self.username_input.text() or 'default'}_{self.host_input.text().split('.')[0] or 'host'}"
        self.new_key_path_input.setText(os.path.join(os.path.expanduser("~/.ssh"), default_key_name))
        
        self.username_input.textChanged.connect(self._update_default_key_path)
        self.host_input.textChanged.connect(self._update_default_key_path)

        key_path_layout.addWidget(self.new_key_path_input)
        self.browse_new_key_path_button = QPushButton("Browse...")
        self.browse_new_key_path_button.clicked.connect(self.browse_new_key_path)
        key_path_layout.addWidget(self.browse_new_key_path_button)
        generate_key_layout.addLayout(key_path_layout)
        
        passphrase_layout = QHBoxLayout()
        passphrase_layout.addWidget(QLabel("Passphrase (optional):"))
        self.new_key_passphrase_input = QLineEdit()
        self.new_key_passphrase_input.setEchoMode(QLineEdit.Password)
        passphrase_layout.addWidget(self.new_key_passphrase_input)
        generate_key_layout.addLayout(passphrase_layout)

        self.generate_key_button = QPushButton("Generate Key Pair")
        self.generate_key_button.clicked.connect(self.generate_ssh_key)
        generate_key_layout.addWidget(self.generate_key_button)

        self.key_options_stacked_widget.addWidget(generate_key_page)

        # Page 1: Use Existing Key
        existing_key_page = QWidget()
        existing_key_layout = QVBoxLayout(existing_key_page)
        existing_key_layout.setContentsMargins(0,0,0,0)
        existing_key_layout.setSpacing(5)

        existing_key_path_layout = QHBoxLayout()
        existing_key_path_layout.addWidget(QLabel("Private Key Path:"))
        self.existing_key_path_input = QLineEdit()
        self.existing_key_path_input.setPlaceholderText("Path to existing SSH private key")
        existing_key_path_layout.addWidget(self.existing_key_path_input)
        self.browse_existing_key_path_button = QPushButton("Browse...")
        self.browse_existing_key_path_button.clicked.connect(self.browse_existing_key_path)
        existing_key_path_layout.addWidget(self.browse_existing_key_path_button)
        existing_key_layout.addLayout(existing_key_path_layout)

        self.key_options_stacked_widget.addWidget(existing_key_page)

        # Page 2: No SSH Key (empty page)
        no_key_page = QWidget()
        self.key_options_stacked_widget.addWidget(no_key_page)

        ssh_key_layout.addWidget(self.key_options_stacked_widget)
        layout.addWidget(ssh_key_group)

        # Connect radio buttons to stacked widget
        self.generate_new_key_radio.toggled.connect(lambda: self.key_options_stacked_widget.setCurrentIndex(0))
        self.use_existing_key_radio.toggled.connect(lambda: self.key_options_stacked_widget.setCurrentIndex(1))
        self.no_ssh_key_radio.toggled.connect(lambda: self.key_options_stacked_widget.setCurrentIndex(2))

        # Dialog Buttons
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Add Account")
        self.add_button.clicked.connect(self.accept_dialog)
        button_layout.addWidget(self.add_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        # Set default selection
        self.generate_new_key_radio.setChecked(True) # Default to generating a new key

    def _update_default_key_path(self):
        """Updates the default new key path based on username and host inputs."""
        username = self.username_input.text() or 'default'
        host_prefix = self.host_input.text().split('.')[0] or 'host'
        default_key_name = f"id_rsa_{username}_{host_prefix}"
        self.new_key_path_input.setText(os.path.join(os.path.expanduser("~/.ssh"), default_key_name))

    def browse_new_key_path(self):
        """Opens a file dialog to select a save location for the new SSH key."""
        # Suggest a default file name based on username and host
        default_filename = f"id_rsa_{self.username_input.text() or 'new'}_{self.host_input.text().split('.')[0] or 'key'}"
        initial_dir = os.path.expanduser("~/.ssh")
        os.makedirs(initial_dir, exist_ok=True) # Ensure .ssh directory exists

        path, _ = QFileDialog.getSaveFileName(self, "Save New SSH Private Key As",
                                              os.path.join(initial_dir, default_filename),
                                              "All Files (*)")
        if path:
            self.new_key_path_input.setText(path)

    def browse_existing_key_path(self):
        """Opens a file dialog to select an existing SSH private key."""
        initial_dir = os.path.expanduser("~/.ssh")
        if not os.path.exists(initial_dir):
            initial_dir = QDir.homePath() # Fallback if .ssh doesn't exist

        path, _ = QFileDialog.getOpenFileName(self, "Select Existing SSH Private Key",
                                              initial_dir,
                                              "SSH Private Keys (id_rsa id_ecdsa id_ed25519 *.pem);;All Files (*)")
        if path:
            self.existing_key_path_input.setText(path)

    def generate_ssh_key(self):
        """Generates a new SSH key pair using ssh-keygen."""
        key_path = self.new_key_path_input.text().strip()
        passphrase = self.new_key_passphrase_input.text()

        if not key_path:
            QMessageBox.warning(self, "Input Error", "Please specify a path to save the new SSH key.")
            return

        # Ensure the directory exists
        key_dir = os.path.dirname(key_path)
        if key_dir and not os.path.exists(key_dir):
            try:
                os.makedirs(key_dir, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Directory Error", f"Failed to create directory '{key_dir}': {e}")
                return

        # Prepare ssh-keygen command
        command = ['ssh-keygen', '-t', 'rsa', '-b', '4096', '-f', key_path, '-N', passphrase]
        
        # On Windows, ssh-keygen might not be directly in PATH for some users.
        # This is a basic attempt to make it work, but a more robust solution
        # might involve checking for Git Bash's ssh-keygen.
        if platform.system() == "Windows":
            # Assuming git is installed and its bin directory is in PATH or known
            # This is a heuristic, may need adjustment based on user's Git installation
            git_bin = os.path.join(os.environ.get("ProgramFiles", ""), "Git", "usr", "bin")
            if os.path.exists(os.path.join(git_bin, "ssh-keygen.exe")):
                command[0] = os.path.join(git_bin, "ssh-keygen.exe")
            else:
                QMessageBox.warning(self, "SSH-keygen Not Found",
                                    "ssh-keygen not found in standard Windows Git installation path. "
                                    "Please ensure Git is installed and its 'usr/bin' is in your system PATH, "
                                    "or generate the key manually.")
                return

        success, output = self.run_command(command)

        if success:
            self.generated_private_key_path = key_path
            self.generated_public_key_path = f"{key_path}.pub"
            QMessageBox.information(self, "Key Generated", f"SSH key pair generated successfully:\n{key_path}\n{key_path}.pub")
        else:
            QMessageBox.critical(self, "Key Generation Failed", f"Failed to generate SSH key:\n{output}")

    def get_account_data(self):
        """Returns the collected account data."""
        username = self.username_input.text().strip()
        email = self.email_input.text().strip()
        host = self.host_input.text().strip()
        
        if not username or not email or not host:
            QMessageBox.warning(self, "Input Error", "Username, Email, and Host are required.")
            return None

        account_data = {
            'username': username,
            'email': email,
            'host': host,
            'private_key_path': None,
            'public_key_path': None
        }

        if self.generate_new_key_radio.isChecked():
            if not self.generated_private_key_path:
                QMessageBox.warning(self, "Key Generation Required", "Please generate the SSH key pair first.")
                return None
            account_data['private_key_path'] = self.generated_private_key_path
            account_data['public_key_path'] = self.generated_public_key_path
        elif self.use_existing_key_radio.isChecked():
            existing_key_path = self.existing_key_path_input.text().strip()
            if not existing_key_path:
                QMessageBox.warning(self, "Input Error", "Please provide the path to your existing private key.")
                return None
            if not os.path.exists(existing_key_path):
                QMessageBox.warning(self, "File Not Found", f"The specified private key file does not exist: {existing_key_path}")
                return None
            account_data['private_key_path'] = existing_key_path
            account_data['public_key_path'] = f"{existing_key_path}.pub" # Assume .pub extension
        # If no_ssh_key_radio is checked, private_key_path and public_key_path remain None

        return account_data

    def accept_dialog(self):
        """Validates input and accepts the dialog."""
        if self.get_account_data(): # get_account_data performs validation and shows messages
            self.accept()


class GitSettingsTab(QWidget):
    git_accounts_changed = Signal() # Signal to notify GitBuddyApp of account changes
    auto_start_ssh_agent_setting_changed = Signal(bool) # Signal for auto-start SSH agent setting

    def __init__(self, config_dir, git_accounts_initial, auto_start_ssh_agent_initial, parent=None):
        super().__init__(parent)
        self.config_dir = config_dir
        self.git_accounts_data = list(git_accounts_initial) # Make a mutable copy
        self.auto_start_ssh_agent = auto_start_ssh_agent_initial
        self.ssh_agent_pid = None # To store the PID of the running ssh-agent
        self.git_installed = False # Flag to check if Git is installed

        self.init_ui()
        self.check_git_installation()
        self.load_git_config() # Load global Git config (user.name, user.email)
        self.populate_accounts_table() # Populate table with initial data
        self.update_ssh_agent_status() # Update SSH agent status on startup

        # If auto-start SSH agent is enabled, attempt to start it
        if self.auto_start_ssh_agent and self.git_installed:
            self.start_ssh_agent()

    def init_ui(self):
        """Initializes the Git settings tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Git Installation Status
        git_status_group = QGroupBox("Git Installation Status")
        git_status_layout = QVBoxLayout(git_status_group)
        self.git_status_label = QLabel("Checking Git installation...")
        git_status_layout.addWidget(self.git_status_label)
        self.refresh_install_git_button = QPushButton("Refresh Git Status / Install Git")
        self.refresh_install_git_button.clicked.connect(self.check_git_installation)
        git_status_layout.addWidget(self.refresh_install_git_button)
        layout.addWidget(git_status_group)

        # Global Git Configuration
        global_config_group = QGroupBox("Global Git Configuration (git config --global)")
        global_config_layout = QVBoxLayout(global_config_group)

        # User Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("User Name:"))
        self.global_username_input = QLineEdit()
        self.global_username_input.setPlaceholderText("e.g., John Doe")
        name_layout.addWidget(self.global_username_input)
        global_config_layout.addLayout(name_layout)

        # User Email
        email_layout = QHBoxLayout()
        email_layout.addWidget(QLabel("User Email:"))
        self.global_email_input = QLineEdit()
        self.global_email_input.setPlaceholderText("e.g., john.doe@example.com")
        email_layout.addWidget(self.global_email_input)
        global_config_layout.addLayout(email_layout)

        # Credential Helper
        credential_helper_layout = QHBoxLayout()
        credential_helper_layout.addWidget(QLabel("Credential Helper:"))
        self.credential_helper_combo = QComboBox()
        self.credential_helper_combo.addItems(["", "store", "cache", "manager", "osxkeychain", "wincred"]) # Common helpers
        credential_helper_layout.addWidget(self.credential_helper_combo)
        credential_helper_layout.addStretch(1)
        global_config_layout.addLayout(credential_helper_layout)

        save_global_config_button = QPushButton("Save Global Git Config")
        save_global_config_button.clicked.connect(self.save_global_git_config)
        global_config_layout.addWidget(save_global_config_button)
        layout.addWidget(global_config_group)

        # Configured Git Accounts
        accounts_group = QGroupBox("Configured Git Accounts (for SSH keys)")
        accounts_layout = QVBoxLayout(accounts_group)

        self.accounts_table_widget = QTableWidget()
        self.accounts_table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.accounts_table_widget.setSelectionMode(QTableWidget.SingleSelection)
        self.accounts_table_widget.setColumnCount(4)
        self.accounts_table_widget.setHorizontalHeaderLabels(["Username", "Email", "Host", "Key Path"])
        self.accounts_table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.accounts_table_widget.verticalHeader().setVisible(False)
        accounts_layout.addWidget(self.accounts_table_widget)

        account_buttons_layout = QHBoxLayout()
        add_account_button = QPushButton("Add New Account")
        add_account_button.clicked.connect(self.add_git_account)
        account_buttons_layout.addWidget(add_account_button)

        remove_account_button = QPushButton("Remove Selected Account")
        remove_account_button.setObjectName("removeButton")
        remove_account_button.clicked.connect(self.remove_git_account)
        account_buttons_layout.addWidget(remove_account_button)

        view_public_key_button = QPushButton("View Public Key")
        view_public_key_button.clicked.connect(self.view_public_key)
        account_buttons_layout.addWidget(view_public_key_button)
        account_buttons_layout.addStretch(1)
        accounts_layout.addLayout(account_buttons_layout)
        layout.addWidget(accounts_group)

        # SSH Agent Management
        ssh_agent_group = QGroupBox("SSH Agent Management")
        ssh_agent_layout = QVBoxLayout(ssh_agent_group)

        self.ssh_agent_status_label = QLabel("SSH Agent Status: Checking...")
        ssh_agent_layout.addWidget(self.ssh_agent_status_label)

        ssh_agent_control_layout = QHBoxLayout()
        self.start_agent_button = QPushButton("Start SSH Agent")
        self.start_agent_button.clicked.connect(self.start_ssh_agent)
        ssh_agent_control_layout.addWidget(self.start_agent_button)

        self.stop_agent_button = QPushButton("Stop SSH Agent")
        self.stop_agent_button.clicked.connect(self.stop_ssh_agent)
        ssh_agent_control_layout.addWidget(self.stop_agent_button)

        refresh_agent_button = QPushButton("Refresh Agent Status")
        refresh_agent_button.clicked.connect(self.update_ssh_agent_status)
        ssh_agent_control_layout.addWidget(refresh_agent_button)
        ssh_agent_control_layout.addStretch(1)
        ssh_agent_layout.addLayout(ssh_agent_control_layout)

        self.auto_start_ssh_agent_checkbox = QCheckBox("Auto-start SSH Agent on GitBuddy Launch")
        self.auto_start_ssh_agent_checkbox.setChecked(self.auto_start_ssh_agent)
        self.auto_start_ssh_agent_checkbox.stateChanged.connect(self.on_auto_start_ssh_agent_changed)
        ssh_agent_layout.addWidget(self.auto_start_ssh_agent_checkbox)

        layout.addWidget(ssh_agent_group)
        layout.addStretch(1)

    def run_command(self, command_args, cwd=None, suppress_error_popup=False):
        """
        Helper function to run a shell command.
        Returns (success: bool, output: str).
        """
        try:
            # Set GIT_TERMINAL_PROMPT to 0 and GIT_ASKPASS to /bin/true to prevent Git from asking for credentials interactively
            # This is crucial for background operations.
            env = os.environ.copy()
            env['GIT_TERMINAL_PROMPT'] = '0'
            env['GIT_ASKPASS'] = '/bin/true' # Forces Git to use a non-interactive password helper

            result = subprocess.run(
                command_args,
                cwd=cwd,
                check=False, # Do not raise CalledProcessError automatically
                capture_output=True,
                text=True,
                env=env, # Pass the modified environment
                timeout=60 # Add a timeout to prevent hangs
            )
            
            if result.returncode != 0:
                error_message = result.stderr.strip() or result.stdout.strip()
                logging.error(f"Command failed: {' '.join(command_args)}\nError: {error_message}")
                if not suppress_error_popup:
                    QMessageBox.critical(self, "Command Error", f"Command failed: {' '.join(command_args)}\nError: {error_message}")
                return False, error_message
            
            logging.info(f"Command successful: {' '.join(command_args)}\nOutput: {result.stdout.strip()}")
            return True, result.stdout.strip()
        except FileNotFoundError:
            error_message = f"Command not found: {command_args[0]}. Please ensure it's installed and in your PATH."
            logging.error(error_message)
            if not suppress_error_popup:
                QMessageBox.critical(self, "Command Not Found", error_message)
            return False, error_message
        except subprocess.TimeoutExpired:
            error_message = f"Command timed out after 60 seconds: {' '.join(command_args)}"
            logging.error(error_message)
            if not suppress_error_popup:
                QMessageBox.critical(self, "Command Timeout", error_message)
            return False, error_message
        except Exception as e:
            error_message = f"An unexpected error occurred while running command: {e}"
            logging.error(error_message)
            if not suppress_error_popup:
                QMessageBox.critical(self, "Unexpected Error", error_message)
            return False, error_message

    def check_git_installation(self):
        """Checks if Git is installed and updates the status label."""
        success, output = self.run_command(['git', '--version'], suppress_error_popup=True)
        if success:
            self.git_status_label.setText(f"Git Status: Installed ({output})")
            self.git_status_label.setStyleSheet("color: green;")
            self.git_installed = True
            self.refresh_install_git_button.setText("Refresh Git Status")
            # Enable relevant sections if Git is installed
            self.global_username_input.setEnabled(True)
            self.global_email_input.setEnabled(True)
            self.credential_helper_combo.setEnabled(True)
            # Re-enable SSH agent buttons based on git installation
            self.start_agent_button.setEnabled(True)
            self.stop_agent_button.setEnabled(True)
            if hasattr(self, 'auto_start_ssh_agent_checkbox'): # Check if widget exists
                self.auto_start_ssh_agent_checkbox.setEnabled(True)
            self.accounts_table_widget.setEnabled(True) # Enable table
            # Re-connect the button's signal, ensuring it's only connected once
            try:
                self.refresh_install_git_button.clicked.disconnect(self.install_git_dialog)
            except RuntimeError:
                pass # Already disconnected or never connected
            self.refresh_install_git_button.clicked.connect(self.check_git_installation)

        else:
            self.git_status_label.setText("Git Status: Not Installed")
            self.git_status_label.setStyleSheet("color: red;")
            self.git_installed = False
            self.refresh_install_git_button.setText("Install Git")
            # Disable relevant sections if Git is not installed
            self.global_username_input.setEnabled(False)
            self.global_email_input.setEnabled(False)
            self.credential_helper_combo.setEnabled(False)
            # Disable SSH agent buttons
            self.start_agent_button.setEnabled(False)
            self.stop_agent_button.setEnabled(False)
            if hasattr(self, 'auto_start_ssh_agent_checkbox'): # Check if widget exists
                self.auto_start_ssh_agent_checkbox.setEnabled(False)
            self.accounts_table_widget.setEnabled(False) # Disable table
            # Change button action to install dialog
            try:
                self.refresh_install_git_button.clicked.disconnect(self.check_git_installation)
            except RuntimeError:
                pass # Already disconnected or never connected
            self.refresh_install_git_button.clicked.connect(self.install_git_dialog)

    def install_git_dialog(self):
        """Informs the user how to install Git based on their OS."""
        os_name = platform.system()
        message = ""
        if os_name == "Linux":
            message = ("To install Git on Linux, open your terminal and run:\n\n"
                       "  sudo apt update && sudo apt install git  (for Debian/Ubuntu)\n"
                       "  sudo dnf install git  (for Fedora)\n"
                       "  sudo pacman -S git  (for Arch Linux)\n\n"
                       "After installation, click 'Refresh Git Status' again.")
        elif os_name == "Windows":
            message = ("To install Git on Windows, download the installer from:\n"
                       "  https://git-scm.com/download/win\n\n"
                       "Follow the installation steps. After installation, restart GitBuddy and click 'Refresh Git Status' again.")
        elif os_name == "Darwin": # macOS
            message = ("To install Git on macOS, you can use Homebrew:\n\n"
                       "  /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"\n"
                       "  brew install git\n\n"
                       "Alternatively, install Xcode Command Line Tools: `xcode-select --install`\n\n"
                       "After installation, click 'Refresh Git Status' again.")
        else:
            message = ("To install Git, please refer to the official Git website for instructions specific to your operating system:\n"
                       "  https://git-scm.com/downloads\n\n"
                       "After installation, click 'Refresh Git Status' again.")
        
        QMessageBox.information(self, "Install Git", message)

    def load_git_config(self):
        """Loads global Git user.name, user.email, and credential.helper."""
        if not self.git_installed:
            return

        # Load user.name
        success, name = self.run_command(['git', 'config', '--global', 'user.name'], suppress_error_popup=True)
        if success:
            self.global_username_input.setText(name)
        else:
            self.global_username_input.clear()

        # Load user.email
        success, email = self.run_command(['git', 'config', '--global', 'user.email'], suppress_error_popup=True)
        if success:
            self.global_email_input.setText(email)
        else:
            self.global_email_input.clear()

        # Load credential.helper
        success, helper = self.run_command(['git', 'config', '--global', 'credential.helper'], suppress_error_popup=True)
        if success:
            index = self.credential_helper_combo.findText(helper)
            if index != -1:
                self.credential_helper_combo.setCurrentIndex(index)
            else:
                self.credential_helper_combo.setCurrentText("") # Clear if not in predefined list
        else:
            self.credential_helper_combo.setCurrentText("")

    def save_global_git_config(self):
        """Saves global Git user.name, user.email, and credential.helper."""
        if not self.git_installed:
            QMessageBox.warning(self, "Git Not Installed", "Git is not installed. Cannot save global config.")
            return

        username = self.global_username_input.text().strip()
        email = self.global_email_input.text().strip()
        credential_helper = self.credential_helper_combo.currentText().strip()

        if username:
            self.run_command(['git', 'config', '--global', 'user.name', username])
        else:
            # Unset if empty
            self.run_command(['git', 'config', '--global', '--unset', 'user.name'], suppress_error_popup=True)

        if email:
            self.run_command(['git', 'config', '--global', 'user.email', email])
        else:
            # Unset if empty
            self.run_command(['git', 'config', '--global', '--unset', 'user.email'], suppress_error_popup=True)

        if credential_helper:
            self.run_command(['git', 'config', '--global', 'credential.helper', credential_helper])
        else:
            # Unset if empty
            self.run_command(['git', 'config', '--global', '--unset', 'credential.helper'], suppress_error_popup=True)
        
        QMessageBox.information(self, "Global Config Saved", "Global Git configuration updated.")
        self.load_git_config() # Reload to confirm

    def populate_accounts_table(self):
        """Populates the accounts table with data from self.git_accounts_data."""
        self.accounts_table_widget.setRowCount(0) # Clear existing rows
        for row_idx, account in enumerate(self.git_accounts_data):
            self.accounts_table_widget.insertRow(row_idx)
            self.accounts_table_widget.setItem(row_idx, 0, QTableWidgetItem(account.get('username', '')))
            self.accounts_table_widget.setItem(row_idx, 1, QTableWidgetItem(account.get('email', '')))
            self.accounts_table_widget.setItem(row_idx, 2, QTableWidgetItem(account.get('host', '')))
            
            key_path = account.get('private_key_path', '')
            display_key_path = os.path.basename(key_path) if key_path else "N/A"
            self.accounts_table_widget.setItem(row_idx, 3, QTableWidgetItem(display_key_path))

    def save_git_accounts(self):
        """Saves the current git_accounts_data to a JSON file."""
        try:
            # Ensure the config directory exists
            os.makedirs(self.config_dir, exist_ok=True)
            with open(GIT_ACCOUNTS_FILE, 'w') as f:
                json.dump(self.git_accounts_data, f, indent=4)
            logging.info(f"Git accounts saved to {GIT_ACCOUNTS_FILE}")
            self.git_accounts_changed.emit() # Emit signal after saving
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save Git accounts: {e}")
            logging.error(f"Failed to save Git accounts: {e}")

    def add_git_account(self):
        """Opens a dialog to add a new Git account."""
        if not self.git_installed:
            QMessageBox.warning(self, "Git Not Installed", "Git is not installed. Cannot add accounts.")
            return

        dialog = AddAccountDialog(self.config_dir, self.run_command, self)
        if dialog.exec() == QDialog.Accepted:
            account_data = dialog.get_account_data()
            if account_data:
                # Check for duplicate accounts (username + host)
                is_duplicate = any(
                    acc['username'] == account_data['username'] and acc['host'] == account_data['host']
                    for acc in self.git_accounts_data
                )
                if is_duplicate:
                    QMessageBox.warning(self, "Duplicate Account", "An account with this username and host already exists.")
                    return

                self.git_accounts_data.append(account_data)
                self.populate_accounts_table()
                self.save_git_accounts()
                QMessageBox.information(self, "Account Added", "Git account added successfully.")
            else:
                QMessageBox.warning(self, "Account Not Added", "Account data incomplete or invalid.")

    def remove_git_account(self):
        """Removes the selected Git account from the table and data."""
        if not self.git_installed:
            QMessageBox.warning(self, "Git Not Installed", "Git is not installed. Cannot remove accounts.")
            return

        selected_rows = self.accounts_table_widget.selectedIndexes()
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select an account to remove.")
            return

        reply = QMessageBox.question(self, "Confirm Removal",
                                     "Are you sure you want to remove the selected Git account?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        selected_row_index = selected_rows[0].row()
        
        username_item = self.accounts_table_widget.item(selected_row_index, 0)
        host_item = self.accounts_table_widget.item(selected_row_index, 2)
        
        if username_item and host_item:
            username_to_remove = username_item.text()
            host_to_remove = host_item.text()
            
            self.git_accounts_data = [
                acc for acc in self.git_accounts_data 
                if not (acc['username'] == username_to_remove and acc['host'] == host_to_remove)
            ]
            
            self.save_git_accounts() # Save updated data (emits signal)
            self.populate_accounts_table() # Refresh table
        else:
            QMessageBox.critical(self, "Error", "Could not retrieve selected account data for removal.")

    def view_public_key(self):
        """Displays the public key for the selected Git account."""
        selected_rows = self.accounts_table_widget.selectedIndexes()
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select an account to view its public key.")
            return

        selected_row_index = selected_rows[0].row()
        account_data = self.git_accounts_data[selected_row_index]

        public_key_path = account_data.get('public_key_path')
        private_key_path = account_data.get('private_key_path') # Use private key path to derive public if .pub not explicitly saved

        if not public_key_path and private_key_path:
            # If public_key_path is not explicitly stored, assume it's private_key_path + ".pub"
            public_key_path = f"{private_key_path}.pub"
        
        if not public_key_path or not os.path.exists(public_key_path):
            QMessageBox.warning(self, "Public Key Not Found",
                                "Public key file not found for this account. "
                                "It might not have been generated, or the file has been moved or deleted. "
                                "Please generate a new key or update the account with a valid existing key.")
            return

        try:
            with open(public_key_path, 'r') as f:
                public_key_content = f.read().strip()

            key_dialog = QDialog(self)
            key_dialog.setWindowTitle(f"Public Key for {account_data['username']}@{account_data['host']}")
            key_dialog_layout = QVBoxLayout(key_dialog)

            key_dialog_layout.addWidget(QLabel("Copy this public key to your Git hosting service (e.g., GitHub, GitLab settings):"))
            
            key_text_edit = QTextEdit()
            key_text_edit.setReadOnly(True)
            key_text_edit.setText(public_key_content)
            key_text_edit.setMinimumHeight(100)
            key_dialog_layout.addWidget(key_text_edit)

            copy_button = QPushButton("Copy to Clipboard")
            copy_button.clicked.connect(lambda: QApplication.clipboard().setText(public_key_content))
            copy_button.clicked.connect(lambda: QMessageBox.information(key_dialog, "Copied!", "Public key copied to clipboard."))
            key_dialog_layout.addWidget(copy_button)

            close_button = QPushButton("Close")
            close_button.clicked.connect(key_dialog.accept)
            key_dialog_layout.addWidget(close_button)

            key_dialog.exec()

        except Exception as e:
            QMessageBox.critical(self, "Error Reading Key", f"Failed to read public key file: {e}")

    def ssh_agent_running(self):
        """Checks if the SSH agent is currently running based on environment variables."""
        if 'SSH_AUTH_SOCK' in os.environ and os.path.exists(os.environ['SSH_AUTH_SOCK']):
            # For more robust check, could try `ssh-add -l`
            return True
        return False

    def update_ssh_agent_status(self):
        """Updates the SSH agent status label and button states."""
        if self.ssh_agent_running():
            self.ssh_agent_status_label.setText("SSH Agent Status: Running")
            self.ssh_agent_status_label.setStyleSheet("color: green;")
            self.start_agent_button.setEnabled(False)
            self.stop_agent_button.setEnabled(True)
        else:
            self.ssh_agent_status_label.setText("SSH Agent Status: Not Running")
            self.ssh_agent_status_label.setStyleSheet("color: red;")
            self.start_agent_button.setEnabled(True)
            self.stop_agent_button.setEnabled(False)

        # Enable/disable based on git installation as well
        if not self.git_installed:
            self.start_agent_button.setEnabled(False)
            self.stop_agent_button.setEnabled(False)
        
        # Safely update the checkbox state if it exists
        if hasattr(self, 'auto_start_ssh_agent_checkbox'):
            self.auto_start_ssh_agent_checkbox.setChecked(self.auto_start_ssh_agent)


    def start_ssh_agent(self):
        """Starts the SSH agent if not already running."""
        if not self.git_installed:
            QMessageBox.warning(self, "Git Not Installed", "Git is not installed. Cannot start SSH agent.")
            return

        if self.ssh_agent_running():
            QMessageBox.information(self, "SSH Agent Status", "SSH agent is already running.")
            return

        try:
            # Start the ssh-agent
            # The output of ssh-agent needs to be parsed to set environment variables
            result = subprocess.run(['ssh-agent', '-s'], capture_output=True, text=True, check=True)
            output_lines = result.stdout.split('\n')
            env_vars = {}
            for line in output_lines:
                if line.startswith('SSH_AUTH_SOCK='):
                    env_vars['SSH_AUTH_SOCK'] = line.split('=')[1].split(';')[0]
                elif line.startswith('SSH_AGENT_PID='):
                    env_vars['SSH_AGENT_PID'] = line.split('=')[1].split(';')[0]

            if 'SSH_AUTH_SOCK' in env_vars and 'SSH_AGENT_PID' in env_vars:
                os.environ.update(env_vars)
                self.ssh_agent_pid = int(env_vars['SSH_AGENT_PID'])
                logging.info(f"SSH agent started successfully. PID: {self.ssh_agent_pid}")
                QMessageBox.information(self, "SSH Agent", "SSH agent started successfully.")
                self.update_ssh_agent_status()
                
                # --- NEW LOGIC: Automatically add all configured keys ---
                self.add_all_configured_ssh_keys()
                # --- END NEW LOGIC ---

            else:
                logging.error(f"Failed to parse ssh-agent output: {result.stdout}")
                QMessageBox.critical(self, "SSH Agent Error", "Failed to start SSH agent: Could not parse output.")
        except FileNotFoundError:
            QMessageBox.critical(self, "Error", "ssh-agent command not found. Please ensure OpenSSH is installed and in your PATH.")
        except subprocess.CalledProcessError as e:
            logging.error(f"Error starting ssh-agent: {e.stderr}")
            QMessageBox.critical(self, "SSH Agent Error", f"Failed to start SSH agent: {e.stderr.strip()}")
        except Exception as e:
            logging.error(f"An unexpected error occurred while starting SSH agent: {e}")
            QMessageBox.critical(self, "SSH Agent Error", f"An unexpected error occurred: {e}")

    def stop_ssh_agent(self):
        """Stops the SSH agent."""
        if not self.git_installed:
            QMessageBox.warning(self, "Git Not Installed", "Git is not installed. Cannot stop SSH agent.")
            return

        if not self.ssh_agent_running():
            QMessageBox.information(self, "SSH Agent Status", "SSH agent is not running.")
            return
        
        # Attempt to kill the agent using SSH_AGENT_PID if known
        if self.ssh_agent_pid:
            try:
                logging.info(f"Attempting to kill SSH agent with PID: {self.ssh_agent_pid}")
                os.kill(self.ssh_agent_pid, 15) # SIGTERM
                # Clear environment variables
                if 'SSH_AUTH_SOCK' in os.environ: del os.environ['SSH_AUTH_SOCK']
                if 'SSH_AGENT_PID' in os.environ: del os.environ['SSH_AGENT_PID']
                self.ssh_agent_pid = None
                QMessageBox.information(self, "SSH Agent", "SSH agent stopped successfully.")
                logging.info("SSH agent stopped successfully via PID.")
            except ProcessLookupError:
                logging.warning(f"SSH agent with PID {self.ssh_agent_pid} not found. It might have already stopped.")
                QMessageBox.information(self, "SSH Agent", "SSH agent not found or already stopped.")
            except Exception as e:
                logging.error(f"Error stopping SSH agent via PID: {e}")
                QMessageBox.critical(self, "SSH Agent Error", f"Failed to stop SSH agent via PID: {e}")
        else:
            # Fallback: try to stop using `ssh-agent -k` (less reliable if env vars are gone)
            logging.info("SSH_AGENT_PID not known, attempting to stop via ssh-agent -k.")
            success, output = self.run_command(['ssh-agent', '-k'], suppress_error_popup=True)
            if success and "killed ssh-agent" in output.lower():
                # Clear environment variables
                if 'SSH_AUTH_SOCK' in os.environ: del os.environ['SSH_AUTH_SOCK']
                if 'SSH_AGENT_PID' in os.environ: del os.environ['SSH_AGENT_PID']
                self.ssh_agent_pid = None
                QMessageBox.information(self, "SSH Agent", "SSH agent stopped successfully.")
                logging.info("SSH agent stopped successfully via ssh-agent -k.")
            else:
                QMessageBox.critical(self, "SSH Agent Error", f"Failed to stop SSH agent.\n{output}")
                logging.error(f"Failed to stop SSH agent via ssh-agent -k: {output}")

        self.update_ssh_agent_status()

    def add_all_configured_ssh_keys(self):
        """Adds all configured SSH private keys to the running ssh-agent."""
        if not self.ssh_agent_running():
            logging.warning("SSH agent not running. Cannot add keys.")
            return

        keys_added_count = 0
        keys_failed_count = 0

        for account in self.git_accounts_data:
            private_key_path = account.get('private_key_path')
            if private_key_path and os.path.exists(private_key_path):
                logging.info(f"Attempting to add SSH key: {private_key_path}")
                # Use run_command to execute ssh-add
                # ssh-add might prompt for passphrase, which run_command doesn't handle interactively.
                # It will likely fail if a passphrase is required and not provided via SSH_ASKPASS.
                success, output = self.run_command(['ssh-add', private_key_path], suppress_error_popup=True)
                if success:
                    logging.info(f"Successfully added key: {private_key_path}")
                    keys_added_count += 1
                else:
                    logging.warning(f"Failed to add key {private_key_path}: {output}")
                    keys_failed_count += 1
                    # Provide a more specific warning if it's likely a passphrase issue
                    if "bad passphrase" in output.lower() or "permission denied" in output.lower():
                        QMessageBox.warning(self, "Key Add Failed",
                                            f"Failed to add key '{os.path.basename(private_key_path)}' for '{account.get('username')}@{account.get('host')}'.\n"
                                            "This often happens if the key requires a passphrase. "
                                            "You may need to add it manually using 'ssh-add' in a terminal, or use a key without a passphrase.")
                    else:
                        QMessageBox.warning(self, "Key Add Failed",
                                            f"Failed to add key '{os.path.basename(private_key_path)}' for '{account.get('username')}@{account.get('host')}'.\n"
                                            f"Error: {output}")
            else:
                logging.warning(f"Private key path not found or invalid for account: {account.get('username')}@{account.get('host')}")

        if keys_added_count > 0:
            QMessageBox.information(self, "SSH Keys Added", f"Successfully added {keys_added_count} SSH key(s) to the agent.")
        if keys_failed_count > 0:
            QMessageBox.warning(self, "SSH Key Add Issues", f"Failed to add {keys_failed_count} SSH key(s). Check logs for details.")

    def on_auto_start_ssh_agent_changed(self, state):
        """Handles the state change of the auto-start SSH agent checkbox."""
        self.auto_start_ssh_agent = (state == Qt.CheckState.Checked)
        self.auto_start_ssh_agent_setting_changed.emit(self.auto_start_ssh_agent)
