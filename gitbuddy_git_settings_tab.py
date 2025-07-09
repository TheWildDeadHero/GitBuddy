# gitbuddy_git_settings_tab.py

import os
import subprocess
import json
import platform # Import platform to detect OS
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QMessageBox, QGroupBox, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QInputDialog, QFileDialog, QDialog, QRadioButton,
    QButtonGroup, QStackedWidget, QTextEdit, QApplication, QCheckBox
)
from PySide6.QtCore import Qt, Signal # Import Signal
import logging # Import logging

# Define the path for Git accounts configuration (still needed for AddAccountDialog)
# This is a local reference for the dialog, the main app manages the actual file.
# Removed: GIT_ACCOUNTS_FILE = os.path.join(os.path.expanduser("~/.config/git-buddy"), "git_accounts.json")


class AddAccountDialog(QDialog):
    def __init__(self, run_command_func, parent=None): # Removed config_dir
        super().__init__(parent)
        # self.config_dir = config_dir # Removed
        self.run_command = run_command_func
        self.generated_key_path = None

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

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
        self.email_input.setPlaceholderText("e.g., octocat@github.com")
        form_layout.addWidget(self.email_input)
        account_details_layout.addLayout(form_layout)

        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Host:"))
        self.host_combobox = QComboBox()
        self.host_combobox.addItems(["GitHub", "GitLab", "Bitbucket", "Azure DevOps", "Other"])
        form_layout.addWidget(self.host_combobox)
        account_details_layout.addLayout(form_layout)
        
        layout.addWidget(account_details_group)

        auth_group = QGroupBox("Authentication Method")
        auth_layout = QVBoxLayout(auth_group)

        self.auth_type_combobox = QComboBox()
        self.auth_type_combobox.addItems(["Password", "SSH Key"])
        self.auth_type_combobox.currentIndexChanged.connect(self.update_auth_options_visibility)
        auth_layout.addWidget(self.auth_type_combobox)

        self.auth_options_stacked_widget = QStackedWidget()
        auth_layout.addWidget(self.auth_options_stacked_widget)

        password_page = QWidget()
        password_layout = QVBoxLayout(password_page)
        password_layout.addWidget(QLabel("Password authentication will prompt when needed."))
        password_layout.addStretch(1)
        self.auth_options_stacked_widget.addWidget(password_page)

        ssh_key_page = QWidget()
        ssh_key_layout = QVBoxLayout(ssh_key_page)

        self.ssh_key_choice_group = QButtonGroup(self)
        self.generate_key_radio = QRadioButton("Generate New Key Pair")
        self.use_existing_key_radio = QRadioButton("Use Existing Key")
        self.ssh_key_choice_group.addButton(self.generate_key_radio)
        self.ssh_key_choice_group.addButton(self.use_existing_key_radio)
        
        self.generate_key_radio.setChecked(True)
        self.generate_key_radio.toggled.connect(self.update_ssh_key_options_visibility)

        ssh_key_layout.addWidget(self.generate_key_radio)

        self.generate_key_options_widget = QWidget()
        generate_key_options_layout = QVBoxLayout(self.generate_key_options_widget)
        generate_key_options_layout.setContentsMargins(20, 0, 0, 0)

        key_type_layout = QHBoxLayout()
        key_type_layout.addWidget(QLabel("Key Type:"))
        self.key_type_combobox = QComboBox()
        self.key_type_combobox.addItems(["rsa", "ed25519"])
        key_type_layout.addWidget(self.key_type_combobox)
        key_type_layout.addStretch(1)
        generate_key_options_layout.addLayout(key_type_layout)

        self.generate_key_button = QPushButton("Generate Key Pair")
        self.generate_key_button.clicked.connect(self.generate_key_pair_in_dialog)
        generate_key_options_layout.addWidget(self.generate_key_button)
        
        ssh_key_layout.addWidget(self.generate_key_options_widget)

        ssh_key_layout.addWidget(self.use_existing_key_radio)

        self.use_existing_key_options_widget = QWidget()
        use_existing_key_options_layout = QVBoxLayout(self.use_existing_key_options_widget)
        use_existing_key_options_layout.setContentsMargins(20, 0, 0, 0)

        existing_key_path_layout = QHBoxLayout()
        existing_key_path_layout.addWidget(QLabel("Key Path:"))
        self.existing_key_path_input = QLineEdit()
        self.existing_key_path_input.setPlaceholderText("Path to your private SSH key")
        existing_key_path_layout.addWidget(self.existing_key_path_input)
        self.browse_existing_key_button = QPushButton("Browse...")
        self.browse_existing_key_button.clicked.connect(self.browse_existing_key)
        existing_key_path_layout.addWidget(self.browse_existing_key_button)
        use_existing_key_options_layout.addLayout(existing_key_path_layout)

        ssh_key_layout.addWidget(self.use_existing_key_options_widget)
        ssh_key_layout.addStretch(1)
        self.auth_options_stacked_widget.addWidget(ssh_key_page)

        layout.addWidget(auth_group)

        button_box = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setEnabled(False)
        button_box.addWidget(self.ok_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_box.addWidget(self.cancel_button)
        button_box.addStretch(1)
        layout.addLayout(button_box)

        self.update_auth_options_visibility()
        self.update_ssh_key_options_visibility()
        self.username_input.textChanged.connect(self.check_ok_button_state)
        self.email_input.textChanged.connect(self.check_ok_button_state)
        self.existing_key_path_input.textChanged.connect(self.check_ok_button_state)
        self.auth_type_combobox.currentIndexChanged.connect(self.check_ok_button_state)


    def update_auth_options_visibility(self):
        """Updates visibility of authentication options based on combobox selection."""
        if self.auth_type_combobox.currentText() == "Password":
            self.auth_options_stacked_widget.setCurrentIndex(0)
            self.ok_button.setEnabled(True)
        elif self.auth_type_combobox.currentText() == "SSH Key":
            self.auth_options_stacked_widget.setCurrentIndex(1)
            self.update_ssh_key_options_visibility()
        self.check_ok_button_state()

    def update_ssh_key_options_visibility(self):
        """Updates visibility of SSH key generation/selection options."""
        if self.generate_key_radio.isChecked():
            self.generate_key_options_widget.setVisible(True)
            self.use_existing_key_options_widget.setVisible(False)
            self.ok_button.setEnabled(self.generated_key_path is not None)
        else:
            self.generate_key_options_widget.setVisible(False)
            self.use_existing_key_options_widget.setVisible(True)
            self.ok_button.setEnabled(bool(self.existing_key_path_input.text().strip()))
        self.check_ok_button_state()

    def check_ok_button_state(self):
        """Checks if the OK button should be enabled."""
        username_ok = bool(self.username_input.text().strip())
        email_ok = bool(self.email_input.text().strip())
        host_ok = bool(self.host_combobox.currentText().strip())

        if not (username_ok and email_ok and host_ok):
            self.ok_button.setEnabled(False)
            return

        if self.auth_type_combobox.currentText() == "Password":
            self.ok_button.setEnabled(True)
        elif self.auth_type_combobox.currentText() == "SSH Key":
            if self.generate_key_radio.isChecked():
                self.ok_button.setEnabled(self.generated_key_path is not None and os.path.exists(str(self.generated_key_path)))
            else:
                self.ok_button.setEnabled(bool(self.existing_key_path_input.text().strip()) and os.path.exists(self.existing_key_path_input.text().strip()))
        else:
            self.ok_button.setEnabled(False)

    def browse_existing_key(self):
        """Opens a file dialog to select an existing SSH private key."""
        initial_path = os.path.expanduser("~/.ssh")
        file_path, ok = QFileDialog.getOpenFileName(self, "Select Existing SSH Private Key",
                                                    initial_path,
                                                    "All Files (*);;Private Key Files (*id_rsa* *id_ed25519*)")
        if ok and file_path:
            self.existing_key_path_input.setText(file_path)
            self.check_ok_button_state()

    def generate_key_pair_in_dialog(self):
        """Generates a new SSH key pair and updates the dialog state."""
        email_for_key = self.email_input.text().strip()
        username_for_config = self.username_input.text().strip()
        host_for_config = self.host_combobox.currentText().strip()
        key_type = self.key_type_combobox.currentText()

        if not email_for_key or not username_for_config or not host_for_config:
            QMessageBox.warning(self, "Input Error", "Please fill in Username, Email, and Host before generating a key.")
            return

        default_key_filename = f"id_{key_type}_{username_for_config.replace(' ', '_').lower()}_{host_for_config.replace('.', '_').lower()}"
        key_file_path, ok = QFileDialog.getSaveFileName(self, "Save SSH Private Key As",
                                                        os.path.join(os.path.expanduser("~/.ssh"), default_key_filename),
                                                        "All Files (*);;Private Key Files (*)")
        if not ok or not key_file_path:
            return

        private_key_path = key_file_path
        public_key_path = private_key_path + ".pub"

        if os.path.exists(private_key_path) or os.path.exists(public_key_path):
            reply = QMessageBox.question(self, "Overwrite Existing Key?",
                                         f"An SSH key pair already exists at '{private_key_path}' and '{public_key_path}'. Do you want to overwrite it?\n"
                                         "This action cannot be undone.",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return

        passphrase, ok = QInputDialog.getText(self, "SSH Key Passphrase",
                                              "Enter a passphrase for your new SSH key (leave empty for no passphrase):",
                                              QLineEdit.Password)
        if not ok:
            return

        if passphrase:
            confirm_passphrase, ok = QInputDialog.getText(self, "Confirm SSH Key Passphrase",
                                                          "Confirm passphrase:",
                                                          QLineEdit.Password)
            if not ok:
                return
            if passphrase != confirm_passphrase:
                QMessageBox.critical(self, "Passphrase Mismatch", "Passphrases do not match. Key generation cancelled.")
                return

        try:
            ssh_dir = os.path.dirname(private_key_path)
            os.makedirs(ssh_dir, exist_ok=True)
            os.chmod(ssh_dir, 0o700)

            command = [
                'ssh-keygen',
                '-t', key_type,
                '-b', '4096' if key_type == 'rsa' else '',
                '-C', email_for_key,
                '-f', private_key_path,
                '-N', passphrase
            ]
            command = [arg for arg in command if arg] 

            success, message = self.run_command(command)

            if success:
                self.generated_key_path = private_key_path
                os.chmod(private_key_path, 0o600)
                if os.path.exists(public_key_path):
                    os.chmod(public_key_path, 0o644)

                ssh_config_path = os.path.expanduser("~/.ssh/config")
                ssh_config_entry = f"""
Host {host_for_config}
  HostName {host_for_config}
  User {username_for_config}
  IdentityFile {private_key_path}
"""
                try:
                    with open(ssh_config_path, 'a') as f:
                        f.write(ssh_config_entry.strip() + "\n\n")
                except Exception as config_e:
                    QMessageBox.warning(self, "SSH Config Update Failed",
                                        f"SSH key generated successfully, but failed to update SSH config file '{ssh_config_path}': {config_e}\n"
                                        "You may need to manually add the following entry:\n\n"
                                        f"{ssh_config_entry.strip()}")
            else:
                QMessageBox.critical(self, "SSH Key Generation Failed", f"Failed to generate SSH key: {message}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred during SSH key generation: {e}")
        finally:
            self.check_ok_button_state()

    def get_account_data(self):
        """Returns the collected account data."""
        auth_type = self.auth_type_combobox.currentText()
        account_data = {
            'username': self.username_input.text().strip(),
            'email': self.email_input.text().strip(),
            'host': self.host_combobox.currentText().strip(),
            'auth_type': auth_type
        }
        if auth_type == "SSH Key":
            if self.generate_key_radio.isChecked():
                account_data['ssh_key_path'] = self.generated_key_path
            else:
                account_data['ssh_key_path'] = self.existing_key_path_input.text().strip()
        return account_data

class GitSettingsTab(QWidget):
    git_accounts_changed = Signal(list) # New signal to emit updated accounts data
    auto_start_ssh_agent_setting_changed = Signal(bool) # Signal for auto-start SSH agent setting

    def __init__(self, git_accounts_initial, auto_start_ssh_agent_initial, parent=None): # Accept initial data
        super().__init__(parent)
        self.git_accounts_data = git_accounts_initial # Initialize with data from central state
        self.auto_start_ssh_agent = auto_start_ssh_agent_initial # Initialize auto-start setting
        self.last_generated_key_path = None
        self.git_installed = False
        self.ssh_agent_pid = None # To store the PID of the running ssh-agent
        self.ssh_auth_sock = None # To store the SSH_AUTH_SOCK environment variable

        self.ui_elements_to_disable = []

        self.init_ui()
        self.check_git_installation() # This will call load_git_config, populate_accounts_table, update_ssh_agent_status
        # The auto-start logic is now in GitBuddyApp, which calls start_ssh_agent if needed after this tab is ready.

    def init_ui(self):
        """Initializes the Git settings tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        credential_group = QGroupBox("Git Credential Helper")
        credential_layout = QVBoxLayout(credential_group)

        credential_helper_layout = QHBoxLayout()
        credential_helper_layout.addWidget(QLabel("Credential Helper:"))
        self.credential_helper_combobox = QComboBox()
        self.credential_helper_combobox.addItems(["", "store", "cache", "manager", "osxkeychain", "wincred", "libsecret"])
        self.credential_helper_combobox.setToolTip(
            "Select a Git credential helper.\n"
            "  - 'store': Stores credentials indefinitely in a plain text file (less secure).\n"
            "  - 'cache': Stores credentials in memory for a short period (default 15 minutes).\n"
            "  - 'manager': Uses an external credential manager (e.g., Git Credential Manager Core).\n"
            "  - 'osxkeychain': macOS Keychain.\n"
            "  - 'wincred': Windows Credential Manager.\n"
            "  - 'libsecret': GNOME Keyring/KWallet (Linux)."
        )
        credential_helper_layout.addWidget(self.credential_helper_combobox)
        self.apply_credential_helper_button = QPushButton("Apply")
        self.apply_credential_helper_button.clicked.connect(self.apply_credential_helper)
        credential_helper_layout.addWidget(self.apply_credential_helper_button)
        credential_helper_layout.addStretch(1)
        credential_layout.addLayout(credential_helper_layout)

        credential_layout.addStretch(1)
        layout.addWidget(credential_group)
        self.ui_elements_to_disable.extend([
            self.credential_helper_combobox, self.apply_credential_helper_button
        ])

        ssh_group = QGroupBox("SSH Key Management")
        ssh_layout = QVBoxLayout(ssh_group)

        ssh_key_path_layout = QHBoxLayout()
        ssh_key_path_layout.addWidget(QLabel("Default SSH Key Path:"))
        self.default_ssh_key_path_input = QLineEdit(os.path.expanduser("~/.ssh/id_rsa"))
        ssh_key_path_layout.addWidget(self.default_ssh_key_path_input)
        self.browse_ssh_key_path_button = QPushButton("Browse...")
        self.browse_ssh_key_path_button.clicked.connect(self.browse_default_ssh_key_path)
        ssh_key_path_layout.addWidget(self.browse_ssh_key_path_button)
        ssh_layout.addLayout(ssh_key_path_layout)
        self.ui_elements_to_disable.extend([
            self.default_ssh_key_path_input, self.browse_ssh_key_path_button
        ])

        self.ssh_agent_status_label = QLabel("SSH Agent Status: Unknown")
        ssh_layout.addWidget(self.ssh_agent_status_label)

        self.ssh_agent_info_label = QLabel(
            "Note: The SSH Agent started here runs for this application session. "
            "Lingering for your user will be automatically enabled/checked for background services."
        )
        self.ssh_agent_info_label.setWordWrap(True)
        self.ssh_agent_info_label.setStyleSheet("font-size: 11px; color: gray;")
        ssh_layout.addWidget(self.ssh_agent_info_label)

        ssh_agent_buttons_layout = QHBoxLayout()
        self.start_ssh_agent_button = QPushButton("Start SSH Agent")
        self.start_ssh_agent_button.clicked.connect(self.toggle_ssh_agent)
        ssh_agent_buttons_layout.addWidget(self.start_ssh_agent_button)
        self.add_key_to_agent_button = QPushButton("Add Key to Agent")
        self.add_key_to_agent_button.clicked.connect(self.add_ssh_key_to_agent)
        ssh_agent_buttons_layout.addWidget(self.add_key_to_agent_button)
        ssh_agent_buttons_layout.addStretch(1)
        ssh_layout.addLayout(ssh_agent_buttons_layout)
        self.ui_elements_to_disable.extend([
            self.start_ssh_agent_button, self.add_key_to_agent_button
        ])

        # Add the auto-start SSH agent checkbox
        self.auto_start_ssh_agent_checkbox = QCheckBox("Auto-start SSH Agent on GitBuddy Launch")
        self.auto_start_ssh_agent_checkbox.setChecked(self.auto_start_ssh_agent)
        self.auto_start_ssh_agent_checkbox.stateChanged.connect(self.on_auto_start_ssh_agent_changed)
        ssh_layout.addWidget(self.auto_start_ssh_agent_checkbox)
        self.ui_elements_to_disable.append(self.auto_start_ssh_agent_checkbox)


        ssh_layout.addStretch(1)
        layout.addWidget(ssh_group)
        
        accounts_group = QGroupBox("Configured Git Accounts")
        accounts_layout = QVBoxLayout(accounts_group)

        self.accounts_table_widget = QTableWidget()
        self.accounts_table_widget.setColumnCount(4) 
        self.accounts_table_widget.setHorizontalHeaderLabels(["Username", "Email", "Host", "Authentication"])
        
        self.accounts_table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.accounts_table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.accounts_table_widget.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.accounts_table_widget.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)

        self.accounts_table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.accounts_table_widget.setSelectionMode(QTableWidget.SingleSelection)
        self.accounts_table_widget.verticalHeader().setVisible(False)
        accounts_layout.addWidget(self.accounts_table_widget)
        self.ui_elements_to_disable.append(self.accounts_table_widget)

        account_buttons_layout = QHBoxLayout()

        self.generate_ssh_key_button = QPushButton("Generate Key for Selected Account...")
        self.generate_ssh_key_button.clicked.connect(self.generate_ssh_key_for_selected_account)
        self.generate_ssh_key_button.setEnabled(False)
        self.accounts_table_widget.itemSelectionChanged.connect(
            lambda: self.generate_ssh_key_button.setEnabled(len(self.accounts_table_widget.selectedIndexes()) > 0) and self.git_installed
        )
        account_buttons_layout.addWidget(self.generate_ssh_key_button)
        self.ui_elements_to_disable.append(self.generate_ssh_key_button)

        account_buttons_layout.addStretch(1)

        self.remove_account_button = QPushButton("Remove Selected Account")
        self.remove_account_button.setObjectName("removeButton")
        self.remove_account_button.clicked.connect(self.remove_selected_account)
        self.remove_account_button.setEnabled(False)
        self.accounts_table_widget.itemSelectionChanged.connect(
            lambda: self.remove_account_button.setEnabled(len(self.accounts_table_widget.selectedIndexes()) > 0)
        )
        self.remove_account_button.setFixedWidth(180)
        account_buttons_layout.addWidget(self.remove_account_button)
        self.ui_elements_to_disable.append(self.remove_account_button)

        self.add_account_button = QPushButton("Add New Account...")
        self.add_account_button.clicked.connect(self.open_add_account_dialog)
        account_buttons_layout.addWidget(self.add_account_button)
        self.ui_elements_to_disable.append(self.add_account_button)

        accounts_layout.addLayout(account_buttons_layout)

        layout.addWidget(accounts_group)

        layout.addStretch(1)

        self.refresh_install_git_button = QPushButton("Refresh Git Settings")
        self.refresh_install_git_button.clicked.connect(self.check_git_installation)
        layout.addWidget(self.refresh_install_git_button)

        # Assign save_global_config_button as an instance attribute
        self.save_global_config_button = QPushButton("Save Global Git Config")
        self.save_global_config_button.clicked.connect(self.save_global_git_config)
        layout.addWidget(self.save_global_config_button)
        self.ui_elements_to_disable.append(self.save_global_config_button) # Add to list

        self.update_ui_state()

    def set_git_accounts_data(self, data):
        """
        Updates the internal git accounts data and refreshes the table.
        Called by the parent (GitBuddyApp) when data changes.
        """
        self.git_accounts_data = data
        self.load_git_accounts() # Reload the table with the new data

    def set_auto_start_ssh_agent_setting(self, enable: bool):
        """
        Updates the internal auto_start_ssh_agent setting and the checkbox state.
        Called by the parent (GitBuddyApp) when data changes.
        """
        self.auto_start_ssh_agent = enable
        # Disconnect to prevent recursive signal emission
        try:
            self.auto_start_ssh_agent_checkbox.stateChanged.disconnect(self.on_auto_start_ssh_agent_changed)
        except TypeError: # Handle case where it's not connected yet
            pass
        self.auto_start_ssh_agent_checkbox.setChecked(enable)
        self.auto_start_ssh_agent_checkbox.stateChanged.connect(self.on_auto_start_ssh_agent_changed)


    def check_git_installation(self):
        """Checks if Git is installed and updates the UI state accordingly."""
        try:
            subprocess.run(['git', '--version'], check=True, capture_output=True, text=True, timeout=5)
            self.git_installed = True
            self.load_git_config()
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            self.git_installed = False
            QMessageBox.warning(self, "Git Status", "Git is not found or not working correctly. Please install Git.")
        finally:
            self.update_ui_state()

    def update_ui_state(self):
        """Enables/disables UI elements based on Git installation status."""
        for element in self.ui_elements_to_disable:
            element.setEnabled(self.git_installed)
        
        self.generate_ssh_key_button.setEnabled(
            self.git_installed and len(self.accounts_table_widget.selectedIndexes()) > 0
        )
        self.remove_account_button.setEnabled(
            len(self.accounts_table_widget.selectedIndexes()) > 0
        )

        if self.git_installed:
            self.refresh_install_git_button.setText("Refresh Git Settings")
            try:
                self.refresh_install_git_button.clicked.disconnect()
            except TypeError:
                pass
            self.refresh_install_git_button.clicked.connect(self.load_git_config)
        else:
            self.refresh_install_git_button.setText("Install Git")
            try:
                self.refresh_install_git_button.clicked.disconnect()
            except TypeError:
                pass
            self.refresh_install_git_button.clicked.connect(self.install_git)

    def install_git(self):
        """Attempts to install Git based on the detected operating system."""
        os_name = platform.system()
        install_command = []
        message = ""

        if os_name == "Linux":
            # Using freedesktop_os_release for more robust distro detection
            try:
                with open("/etc/os-release", "r") as f:
                    os_release_info = dict(line.strip().split("=", 1) for line in f if "=" in line)
                distro_id = os_release_info.get('ID', '').lower()
            except FileNotFoundError:
                distro_id = "" # Fallback if file not found

            if "debian" in distro_id or "ubuntu" in distro_id:
                install_command = ['sudo', 'apt-get', 'update', '&&', 'sudo', 'apt-get', 'install', '-y', 'git']
                message = "Attempting to install Git using apt-get. This may require your sudo password."
            elif "fedora" in distro_id or "centos" in distro_id or "rhel" in distro_id:
                install_command = ['sudo', 'yum', 'install', '-y', 'git']
                message = "Attempting to install Git using yum. This may require your sudo password."
            elif "arch" in distro_id:
                install_command = ['sudo', 'pacman', '-S', '--noconfirm', 'git']
                message = "Attempting to install Git using pacman. This may require your sudo password."
            else:
                QMessageBox.warning(self, "Install Git",
                                    "Unsupported Linux distribution. Please install Git manually via your package manager.")
                return
        elif os_name == "Darwin":
            # For macOS, recommend Homebrew. If Homebrew not installed, provide install command.
            if subprocess.run(['which', 'brew'], capture_output=True).returncode != 0:
                reply = QMessageBox.question(self, "Install Homebrew",
                                             "Homebrew is not installed. Git is typically installed via Homebrew on macOS. "
                                             "Do you want to install Homebrew now? This will open a terminal and may require your password.",
                                             QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.No:
                    return
                # Command to install Homebrew
                install_command = ['/bin/bash', '-c', "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"]
                message = "Installing Homebrew. Please follow the prompts in the terminal."
            else:
                install_command = ['brew', 'install', 'git']
                message = "Attempting to install Git using Homebrew."
            QMessageBox.information(self, "Install Git", message)
        elif os_name == "Windows":
            QMessageBox.information(self, "Install Git",
                                    "On Windows, it's recommended to download and run the Git installer from git-scm.com.\n"
                                    "Alternatively, you can use Chocolatey (if installed) by running:\n"
                                    "`choco install git -y` in an administrator PowerShell/CMD.")
            return
        else:
            QMessageBox.warning(self, "Install Git",
                                f"Unsupported operating system: {os_name}. Please install Git manually.")
            return

        if install_command:
            try:
                # For Linux/macOS, run the command in a new terminal window if possible for user interaction
                if os_name == "Linux" and os.environ.get("XDG_CURRENT_DESKTOP"):
                    # Try to open a terminal (e.g., gnome-terminal, konsole, xterm)
                    terminal_commands = {
                        "gnome": ["gnome-terminal", "--", "bash", "-c", " ".join(install_command) + "; echo 'Press Enter to close'; read"],
                        "kde": ["konsole", "-e", "bash", "-c", " ".join(install_command) + "; echo 'Press Enter to close'; read"],
                        "xfce": ["xfce4-terminal", "-e", "bash", "-c", " ".join(install_command) + "; echo 'Press Enter to close'; read"],
                        "lxde": ["lxterminal", "-e", "bash", "-c", " ".join(install_command) + "; echo 'Press Enter to close'; read"],
                        "mate": ["mate-terminal", "-e", "bash", "-c", " ".join(install_command) + "; echo 'Press Enter to close'; read"],
                        "cinnamon": ["gnome-terminal", "--", "bash", "-c", " ".join(install_command) + "; echo 'Press Enter to close'; read"],
                    }
                    desktop_env = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
                    chosen_terminal_command = None
                    for key, cmd in terminal_commands.items():
                        if key in desktop_env:
                            chosen_terminal_command = cmd
                            break
                    
                    if chosen_terminal_command:
                        subprocess.Popen(chosen_terminal_command)
                    else:
                        # Fallback to xterm if no specific terminal found
                        subprocess.Popen(['xterm', '-e', "bash", "-c", " ".join(install_command) + "; echo 'Press Enter to close'; read"])
                elif os_name == "Darwin":
                    # Open a new Terminal.app window
                    subprocess.Popen(['osascript', '-e', f'tell application "Terminal" to do script "{ " ".join(install_command) }"'])
                else:
                    # For other cases, just run directly (might block GUI or require console)
                    process = subprocess.Popen(install_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    stdout, stderr = process.communicate()
                    if process.returncode != 0:
                        QMessageBox.critical(self, "Install Git Failed", f"Git installation command failed with error:\n{stderr}")
                        return

                # Give user time to complete installation in terminal
                QMessageBox.information(self, "Installation in Progress", 
                                        "Please follow the prompts in the terminal window to complete the Git installation. "
                                        "Click 'OK' here once the terminal process is finished.")
                
            except FileNotFoundError as e:
                QMessageBox.critical(self, "Install Git Error", f"Installation command or terminal emulator not found: {e.filename}. Make sure it's in your PATH.")
            except Exception as e:
                QMessageBox.critical(self, "Install Git Error", f"An unexpected error occurred during Git installation: {e}")
            finally:
                # Re-check installation status after user acknowledges
                self.check_git_installation()

    def run_git_command(self, command_args, cwd=None, timeout=60):
        """Helper function to run a git command."""
        if not self.git_installed:
            return False, "Git is not installed."

        full_command = ['git'] + command_args
        try:
            result = subprocess.run(
                full_command,
                cwd=cwd,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return False, f"Git command failed: {e.stderr.strip()}"
        except FileNotFoundError:
            return False, "Error: 'git' command not found. (This should not happen if git_installed is True)"
        except subprocess.TimeoutExpired:
            return False, f"Error: Git command timed out after {timeout} seconds."
        except Exception as e:
            return False, f"An unexpected error occurred: {e}"

    def run_command(self, command_args, timeout=60, env=None, suppress_errors=False):
        """Generic helper function to run any shell command."""
        # Use the provided environment or a copy of current environment
        current_env = os.environ.copy()
        if env:
            current_env.update(env)

        try:
            result = subprocess.run(
                command_args,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
                env=current_env # Pass the environment
            )
            if not suppress_errors and result.returncode != 0:
                logging.error(f"Command failed: {' '.join(command_args)}\nOutput: {result.stderr.strip()}")
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            if not suppress_errors:
                logging.error(f"Command failed: {e.stderr.strip()}")
            return False, f"Command failed: {e.stderr.strip()}"
        except FileNotFoundError:
            if not suppress_errors:
                logging.error(f"Error: Command '{command_args[0]}' not found. Please ensure it's in your PATH.")
            return False, f"Error: Command '{command_args[0]}' not found. Please ensure it's in your PATH."
        except subprocess.TimeoutExpired:
            if not suppress_errors:
                logging.error(f"Error: Command timed out after {timeout} seconds.")
            return False, f"Error: Command timed out after {timeout} seconds."
        except Exception as e:
            if not suppress_errors:
                logging.error(f"An unexpected error occurred: {e}")
            return False, f"An unexpected error occurred: {e}"

    def load_git_config(self):
        """Loads current Git credential helper and SSH agent status. Only runs if Git is installed."""
        if not self.git_installed:
            return

        success, output = self.run_git_command(['config', '--global', 'credential.helper'])
        if success:
            index = self.credential_helper_combobox.findText(output)
            if index != -1:
                self.credential_helper_combobox.setCurrentIndex(index)
            else:
                self.credential_helper_combobox.setEditText(output)
        else:
            self.credential_helper_combobox.setCurrentIndex(0)
            self.credential_helper_combobox.setEditText("")

        self.check_ssh_agent_status()
        self.load_git_accounts() # This now calls the internal load_git_accounts

    def save_global_git_config(self):
        """Saves global Git user.name, user.email, and credential.helper."""
        if not self.git_installed:
            QMessageBox.warning(self, "Git Not Installed", "Git is not installed. Cannot save global config.")
            return

        credential_helper = self.credential_helper_combobox.currentText().strip()

        if credential_helper:
            success, message = self.run_git_command(['config', '--global', 'credential.helper', credential_helper])
        else:
            success, message = self.run_git_command(['config', '--global', '--unset', 'credential.helper'])
        
        if success:
            QMessageBox.information(self, "Global Config Saved", "Global Git configuration updated.")
        else:
            QMessageBox.critical(self, "Error", f"Failed to set credential helper: {message}")
        self.load_git_config() # Reload to confirm changes


    def apply_credential_helper(self):
        """Applies the selected Git credential helper."""
        if not self.git_installed:
            QMessageBox.warning(self, "Git Not Installed", "Git is not installed. Cannot apply credential helper.")
            return

        selected_helper = self.credential_helper_combobox.currentText().strip()
        if selected_helper == "":
            reply = QMessageBox.question(self, "Unset Credential Helper",
                                         "Are you sure you want to unset the global Git credential helper?\n"
                                         "This may cause Git to prompt for credentials for every operation.",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return
            success, message = self.run_git_command(['config', '--global', '--unset', 'credential.helper'])
        else:
            success, message = self.run_git_command(['config', '--global', 'credential.helper', selected_helper])
        
        if success:
            pass
        else:
            QMessageBox.critical(self, "Error", f"Failed to set credential helper: {message}")
        self.load_git_config()

    def check_ssh_agent_status(self):
        """Checks and updates the SSH agent status label and button text."""
        if not self.git_installed:
            self.ssh_agent_status_label.setText("SSH Agent Status: Git Not Installed")
            self.start_ssh_agent_button.setEnabled(False)
            self.add_key_to_agent_button.setEnabled(False)
            return

        # Check if SSH_AUTH_SOCK is set and points to a valid socket
        if "SSH_AUTH_SOCK" in os.environ and os.path.exists(os.environ["SSH_AUTH_SOCK"]):
            self.ssh_auth_sock = os.environ["SSH_AUTH_SOCK"]
            self.ssh_agent_pid = int(os.environ.get("SSH_AGENT_PID", 0)) # Get PID if available

            # Try to list keys to confirm agent is truly functional
            success, output = self.run_command(['ssh-add', '-l'], timeout=5, env=os.environ, suppress_errors=True)
            if success:
                self.ssh_agent_status_label.setText("SSH Agent Status: Running (Keys Loaded)")
                self.start_ssh_agent_button.setText("Stop SSH Agent")
                self.start_ssh_agent_button.setEnabled(True)
                self.add_key_to_agent_button.setEnabled(True)
            else:
                # Agent socket exists but ssh-add failed (e.g., no keys, or agent died)
                self.ssh_agent_status_label.setText(f"SSH Agent Status: Running (Error: {output or 'No keys loaded'})")
                self.start_ssh_agent_button.setText("Stop SSH Agent")
                self.start_ssh_agent_button.setEnabled(True)
                self.add_key_to_agent_button.setEnabled(True)
        else:
            self.ssh_agent_status_label.setText("SSH Agent Status: Not Running")
            self.start_ssh_agent_button.setText("Start SSH Agent")
            self.start_ssh_agent_button.setEnabled(True)
            self.add_key_to_agent_button.setEnabled(False)
        
        # Ensure auto-start checkbox reflects the current setting
        # Disconnect/reconnect to avoid triggering signal during initial load
        try:
            self.auto_start_ssh_agent_checkbox.stateChanged.disconnect(self.on_auto_start_ssh_agent_changed)
        except TypeError:
            pass # Already disconnected or never connected
        self.auto_start_ssh_agent_checkbox.setChecked(self.auto_start_ssh_agent)
        self.auto_start_ssh_agent_checkbox.stateChanged.connect(self.on_auto_start_ssh_agent_changed)
        self.auto_start_ssh_agent_checkbox.setEnabled(True) # Always enable if Git is installed

    def toggle_ssh_agent(self):
        """Toggles the SSH agent state (start/stop)."""
        if not self.git_installed:
            QMessageBox.warning(self, "Git Not Installed", "Git is not installed. Cannot manage SSH Agent.")
            return

        if "SSH_AUTH_SOCK" in os.environ and os.path.exists(os.environ["SSH_AUTH_SOCK"]):
            self.stop_ssh_agent()
        else:
            self.start_ssh_agent() # Call the method that handles environment setup

    def start_ssh_agent(self):
        """Starts the SSH agent process and sets environment variables for the current process."""
        if not self.git_installed:
            logging.warning("Git not installed. Cannot start SSH Agent.")
            return False

        if "SSH_AUTH_SOCK" in os.environ and os.path.exists(os.environ["SSH_AUTH_SOCK"]):
            logging.info("SSH Agent already appears to be running.")
            self.check_ssh_agent_status()
            return True # Already running

        logging.info("Attempting to start SSH Agent...")
        try:
            # Use 'ssh-agent -s' for sh/bash compatible output
            result = subprocess.run(['ssh-agent', '-s'], capture_output=True, text=True, check=True)
            output_lines = result.stdout.strip().split('\n')

            new_ssh_auth_sock = None
            new_ssh_agent_pid = None

            for line in output_lines:
                if line.startswith('SSH_AUTH_SOCK='):
                    new_ssh_auth_sock = line.split('=')[1].split(';')[0]
                elif line.startswith('SSH_AGENT_PID='):
                    new_ssh_agent_pid = line.split('=')[1].split(';')[0]

            if new_ssh_auth_sock and new_ssh_agent_pid:
                os.environ['SSH_AUTH_SOCK'] = new_ssh_auth_sock
                os.environ['SSH_AGENT_PID'] = new_ssh_agent_pid
                self.ssh_agent_pid = int(new_ssh_agent_pid)
                self.ssh_auth_sock = new_ssh_auth_sock
                logging.info(f"SSH Agent started successfully. PID: {self.ssh_agent_pid}, Socket: {self.ssh_auth_sock}")

                # Enable lingering for the current user to keep agent running across sessions
                current_user = os.getenv('USER')
                if current_user:
                    linger_command = ['loginctl', 'enable-linger', current_user]
                    linger_success, linger_message = self.run_command(linger_command, suppress_errors=True)
                    if linger_success:
                        logging.info(f"Lingering enabled for user '{current_user}'.")
                    else:
                        logging.warning(f"Failed to enable lingering for user '{current_user}': {linger_message}")
                        QMessageBox.warning(self, "Lingering Warning",
                                            f"SSH Agent started, but failed to enable lingering for user '{current_user}'.\n"
                                            "The agent might not persist across sessions. You may need to run:\n"
                                            f"`loginctl enable-linger {current_user}` manually in your terminal.")
                else:
                    logging.warning("Could not determine current user to enable lingering.")
                    QMessageBox.warning(self, "Lingering Warning",
                                        "SSH Agent started, but could not determine current user to enable lingering. "
                                        "Please run `loginctl enable-linger YOUR_USERNAME` manually in your terminal "
                                        "if you want the SSH agent to persist across logins.")
                self.check_ssh_agent_status()
                return True
            else:
                logging.error(f"Failed to parse SSH Agent output. Output:\n{result.stdout}\n{result.stderr}")
                QMessageBox.critical(self, "SSH Agent Error", "Failed to parse SSH Agent output. Check logs for details.")
                self.check_ssh_agent_status()
                return False
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to start SSH Agent: {e.stderr.strip()}")
            QMessageBox.critical(self, "SSH Agent Error", f"Failed to start SSH Agent: {e.stderr.strip()}")
            self.check_ssh_agent_status()
            return False
        except FileNotFoundError:
            logging.error("ssh-agent command not found. Please ensure OpenSSH client is installed and in your PATH.")
            QMessageBox.critical(self, "Error", "ssh-agent command not found. Please ensure OpenSSH client is installed and in your PATH.")
            self.check_ssh_agent_status()
            return False
        except Exception as e:
            logging.error(f"An unexpected error occurred while starting SSH Agent: {e}")
            QMessageBox.critical(self, "Error", f"An unexpected error occurred while starting SSH Agent: {e}")
            self.check_ssh_agent_status()
            return False

    def stop_ssh_agent(self):
        """Stops the currently running SSH agent."""
        if not self.git_installed:
            QMessageBox.warning(self, "Git Not Installed", "Git is not installed. Cannot stop SSH Agent.")
            return False

        # Use the stored PID if available, otherwise try environment variable
        pid_to_kill = self.ssh_agent_pid if self.ssh_agent_pid else (int(os.environ.get("SSH_AGENT_PID", 0)) if os.environ.get("SSH_AGENT_PID") else None)

        if not pid_to_kill:
            QMessageBox.warning(self, "SSH Agent Not Running", "SSH Agent is not running or its PID is not known to this application.")
            return False

        reply = QMessageBox.question(self, "Stop SSH Agent",
                                     f"Are you sure you want to stop the SSH Agent (PID: {pid_to_kill})?\n"
                                     "This will remove all loaded keys and might affect other applications using this agent.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return False

        try:
            success, message = self.run_command(['kill', str(pid_to_kill)], suppress_errors=True)
            if success:
                # Clear environment variables for this process
                if 'SSH_AUTH_SOCK' in os.environ:
                    del os.environ['SSH_AUTH_SOCK']
                if 'SSH_AGENT_PID' in os.environ:
                    del os.environ['SSH_AGENT_PID']
                self.ssh_agent_pid = None
                self.ssh_auth_sock = None
                logging.info(f"SSH Agent (PID: {pid_to_kill}) stopped successfully.")
                self.check_ssh_agent_status()
                return True
            else:
                logging.error(f"Failed to stop SSH Agent (PID: {pid_to_kill}): {message}")
                QMessageBox.critical(self, "SSH Agent Stop Error", f"Failed to stop SSH Agent: {message}")
                self.check_ssh_agent_status()
                return False
        except Exception as e:
            logging.error(f"An unexpected error occurred while stopping SSH Agent: {e}")
            QMessageBox.critical(self, "Error", f"An unexpected error occurred while stopping SSH Agent: {e}")
            self.check_ssh_agent_status()
            return False

    def browse_default_ssh_key_path(self):
        """Opens a file dialog to select the default SSH private key path."""
        if not self.git_installed:
            QMessageBox.warning(self, "Git Not Installed", "Git is not installed. Cannot browse for SSH keys.")
            return

        initial_path = self.default_ssh_key_path_input.text()
        file_path, ok = QFileDialog.getOpenFileName(self, "Select Default SSH Private Key",
                                                    initial_path,
                                                    "All Files (*);;Private Key Files (*id_rsa*)")
        if ok and file_path:
            self.default_ssh_key_path_input.setText(file_path)

    def add_ssh_key_to_agent(self):
        """Adds a selected SSH key to the SSH agent."""
        if not self.git_installed:
            QMessageBox.warning(self, "Git Not Installed", "Git is not installed. Cannot add key to agent.")
            return

        if "SSH_AUTH_SOCK" not in os.environ or not os.path.exists(os.environ["SSH_AUTH_SOCK"]):
            QMessageBox.warning(self, "SSH Agent Not Running",
                                "The SSH Agent is not running for this session. "
                                "Please start the SSH Agent first using the 'Start SSH Agent' button.")
            return

        initial_file_path = self.last_generated_key_path if self.last_generated_key_path else self.default_ssh_key_path_input.text()
        
        key_path, ok = QFileDialog.getOpenFileName(self, "Select SSH Private Key to Add",
                                                    initial_file_path,
                                                    "All Files (*);;Private Key Files (*id_rsa* *id_ed25519*)")
        
        if not ok or not key_path:
            return

        if not os.path.exists(key_path):
            QMessageBox.warning(self, "Key Not Found", f"The selected SSH key not found at '{key_path}'.")
            return

        # Pass the current environment including SSH_AUTH_SOCK to ssh-add
        success, message = self.run_command(['ssh-add', key_path], env=os.environ)
        if success:
            QMessageBox.information(self, "Key Added", f"Successfully added key '{os.path.basename(key_path)}' to SSH Agent.")
        else:
            QMessageBox.critical(self, "Error", f"Failed to add SSH key to agent: {message}\n"
                                 "Ensure SSH agent is running and you have entered your passphrase if prompted in the terminal.")
        self.check_ssh_agent_status()

    def on_auto_start_ssh_agent_changed(self, state):
        """Handles the state change of the auto-start SSH agent checkbox."""
        is_checked = (state == Qt.CheckState.Checked)
        self.auto_start_ssh_agent = is_checked
        self.auto_start_ssh_agent_setting_changed.emit(is_checked) # Emit signal to parent

    def generate_ssh_key_for_selected_account(self):
        """Launches the AddAccountDialog pre-filled for generating a key for a selected account."""
        if not self.git_installed:
            QMessageBox.warning(self, "Git Not Installed", "Git is not installed. Cannot generate SSH key.")
            return

        selected_rows = self.accounts_table_widget.selectedIndexes()
        if not selected_rows:
            QMessageBox.warning(self, "No Account Selected", "Please select a Git account from the table to generate an SSH key for it.")
            return

        selected_row_index = selected_rows[0].row()
        selected_account_data = self.git_accounts_data[selected_row_index]

        dialog = AddAccountDialog(self.run_command, self) # Removed config_dir
        dialog.username_input.setText(selected_account_data['username'])
        dialog.email_input.setText(selected_account_data['email'])
        dialog.host_combobox.setCurrentText(selected_account_data['host'])
        dialog.auth_type_combobox.setCurrentText("SSH Key")
        dialog.generate_key_radio.setChecked(True)
        dialog.username_input.setReadOnly(True)
        dialog.email_input.setReadOnly(True)
        dialog.host_combobox.setEnabled(False)

        if dialog.exec() == QDialog.Accepted:
            new_account_data = dialog.get_account_data()
            if new_account_data.get('auth_type') == 'SSH Key' and new_account_data.get('ssh_key_path'):
                self.last_generated_key_path = new_account_data['ssh_key_path']
            
            # Update the existing account with the new SSH key path
            self.git_accounts_data[selected_row_index]['ssh_key_path'] = new_account_data['ssh_key_path']
            self.git_accounts_data[selected_row_index]['auth_type'] = 'SSH Key' # Ensure type is updated
            self.save_git_accounts() # Save updated data
        self.load_git_accounts()

    def open_add_account_dialog(self):
        """Opens the dialog to add a new Git account."""
        if not self.git_installed:
            QMessageBox.warning(self, "Git Not Installed", "Git is not installed. Cannot add new account.")
            return

        dialog = AddAccountDialog(self.run_command, self) # Removed config_dir
        if dialog.exec() == QDialog.Accepted:
            new_account_data = dialog.get_account_data()
            
            username = new_account_data['username']
            host = new_account_data['host']

            if any(acc['username'] == username and acc['host'] == host for acc in self.git_accounts_data):
                QMessageBox.information(self, "Duplicate Account", f"An account for '{username}' on '{host}' already exists. Please update it instead.")
                return

            account_to_save = {
                'username': username,
                'email': new_account_data['email'],
                'host': host,
                'auth_type': new_account_data['auth_type']
            }
            if new_account_data['auth_type'] == 'SSH Key':
                account_to_save['ssh_key_path'] = new_account_data['ssh_key_path']
                self.last_generated_key_path = new_account_data['ssh_key_path']

            self.git_accounts_data.append(account_to_save)
            self.save_git_accounts() # Save to file (emits signal)
        self.load_git_accounts()

    def load_git_accounts(self):
        """Populates the table using the internal self.git_accounts_data."""
        if not self.git_installed:
            self.accounts_table_widget.setRowCount(0)
            # self.git_accounts_data is already set by set_git_accounts_data from parent
            return

        self.accounts_table_widget.setRowCount(0)
        # self.git_accounts_data is already set by set_git_accounts_data from parent

        for account_data in self.git_accounts_data:
            self._add_account_to_table(account_data)

    def _add_account_to_table(self, account_data):
        """Helper to add a single account's data to the QTableWidget."""
        row_position = self.accounts_table_widget.rowCount()
        self.accounts_table_widget.insertRow(row_position)

        self.accounts_table_widget.setItem(row_position, 0, QTableWidgetItem(account_data['username']))
        self.accounts_table_widget.setItem(row_position, 1, QTableWidgetItem(account_data['email']))
        self.accounts_table_widget.setItem(row_position, 2, QTableWidgetItem(account_data['host']))
        
        auth_display_text = ""
        if account_data.get('auth_type') == "SSH Key":
            auth_display_text = f"SSH Key: {os.path.basename(account_data.get('ssh_key_path', 'N/A'))}"
        else:
            auth_display_text = "Password (managed by Git)"
        self.accounts_table_widget.setItem(row_position, 3, QTableWidgetItem(auth_display_text))

    def save_git_accounts(self):
        """
        Emits the current list of Git accounts to the parent (GitBuddyApp)
        for centralized saving. This tab no longer writes to the file directly.
        """
        if not self.git_installed:
            QMessageBox.warning(self, "Git Not Installed", "Git is not installed. Cannot save accounts.")
            return

        # Emit the current state of git_accounts_data
        self.git_accounts_changed.emit(self.git_accounts_data)

    def remove_selected_account(self):
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
        else:
            QMessageBox.critical(self, "Error", "Could not retrieve selected account data for removal.")
