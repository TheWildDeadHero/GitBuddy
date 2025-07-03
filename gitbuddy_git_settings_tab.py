# gitbuddy_git_settings_tab.py

import os
import subprocess
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QMessageBox, QGroupBox, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QInputDialog, QFileDialog, QDialog, QRadioButton,
    QButtonGroup, QStackedWidget
)
from PySide6.QtCore import Qt

class AddAccountDialog(QDialog):
    def __init__(self, config_dir, run_command_func, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Git Account")
        self.config_dir = config_dir
        self.run_command = run_command_func # Pass the utility function
        self.generated_key_path = None # To store path of newly generated key

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

        # Authentication Group
        auth_group = QGroupBox("Authentication Method")
        auth_layout = QVBoxLayout(auth_group)

        self.auth_type_combobox = QComboBox()
        self.auth_type_combobox.addItems(["Password", "SSH Key"])
        self.auth_type_combobox.currentIndexChanged.connect(self.update_auth_options_visibility)
        auth_layout.addWidget(self.auth_type_combobox)

        self.auth_options_stacked_widget = QStackedWidget()
        auth_layout.addWidget(self.auth_options_stacked_widget)

        # --- Password Page (Index 0) ---
        password_page = QWidget()
        password_layout = QVBoxLayout(password_page)
        password_layout.addWidget(QLabel("Password authentication will prompt when needed."))
        password_layout.addStretch(1)
        self.auth_options_stacked_widget.addWidget(password_page)

        # --- SSH Key Page (Index 1) ---
        ssh_key_page = QWidget()
        ssh_key_layout = QVBoxLayout(ssh_key_page)

        self.ssh_key_choice_group = QButtonGroup(self)
        self.generate_key_radio = QRadioButton("Generate New Key Pair")
        self.use_existing_key_radio = QRadioButton("Use Existing Key")
        self.ssh_key_choice_group.addButton(self.generate_key_radio)
        self.ssh_key_choice_group.addButton(self.use_existing_key_radio)
        
        self.generate_key_radio.setChecked(True) # Default to generate
        self.generate_key_radio.toggled.connect(self.update_ssh_key_options_visibility)

        ssh_key_layout.addWidget(self.generate_key_radio)

        # Generate Key Options
        self.generate_key_options_widget = QWidget()
        generate_key_options_layout = QVBoxLayout(self.generate_key_options_widget)
        generate_key_options_layout.setContentsMargins(20, 0, 0, 0) # Indent

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

        # Use Existing Key Options
        self.use_existing_key_options_widget = QWidget()
        use_existing_key_options_layout = QVBoxLayout(self.use_existing_key_options_widget)
        use_existing_key_options_layout.setContentsMargins(20, 0, 0, 0) # Indent

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

        # Dialog Buttons
        button_box = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setEnabled(False) # Initially disabled until key is generated/selected or password chosen
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
            self.ok_button.setEnabled(True) # Always allow OK for password
        elif self.auth_type_combobox.currentText() == "SSH Key":
            self.auth_options_stacked_widget.setCurrentIndex(1)
            self.update_ssh_key_options_visibility() # Re-evaluate SSH key specific options
        self.check_ok_button_state()

    def update_ssh_key_options_visibility(self):
        """Updates visibility of SSH key generation/selection options."""
        if self.generate_key_radio.isChecked():
            self.generate_key_options_widget.setVisible(True)
            self.use_existing_key_options_widget.setVisible(False)
            self.ok_button.setEnabled(self.generated_key_path is not None) # Only OK if key generated
        else: # Use existing key radio is checked
            self.generate_key_options_widget.setVisible(False)
            self.use_existing_key_options_widget.setVisible(True)
            self.ok_button.setEnabled(bool(self.existing_key_path_input.text().strip())) # Only OK if path entered
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
                self.ok_button.setEnabled(self.generated_key_path is not None and os.path.exists(self.generated_key_path))
            else: # Use existing key
                self.ok_button.setEnabled(bool(self.existing_key_path_input.text().strip()) and os.path.exists(self.existing_key_path_input.text().strip()))
        else:
            self.ok_button.setEnabled(False) # Should not happen

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
                '-b', '4096' if key_type == 'rsa' else '', # -b is not used for ed25519
                '-C', email_for_key,
                '-f', private_key_path,
                '-N', passphrase
            ]
            # Filter out empty string for -b if key_type is ed25519
            command = [arg for arg in command if arg] 

            success, message = self.run_command(command)

            if success:
                self.generated_key_path = private_key_path # Store the path
                os.chmod(private_key_path, 0o600)
                if os.path.exists(public_key_path):
                    os.chmod(public_key_path, 0o644)

                # Update SSH config file
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
                    QMessageBox.information(self, "SSH Key Generated & Configured",
                                            f"Successfully generated new SSH key at:\n'{private_key_path}'\n"
                                            f"Public key: '{public_key_path}'\n\n"
                                            f"SSH config updated at '{ssh_config_path}' for host '{host_for_config}'.\n\n"
                                            "Remember to add the public key to your Git hosting service (e.g., GitHub, GitLab) "
                                            "and consider adding the private key to your SSH agent.")
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
            self.check_ok_button_state() # Re-check OK button state after generation attempt

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
    def __init__(self, config_dir, parent=None):
        super().__init__(parent)
        self.config_dir = config_dir
        self.git_accounts_file = os.path.join(self.config_dir, "git_accounts.json")
        self.git_accounts_data = []
        self.last_generated_key_path = None

        self.init_ui()
        self.load_git_config()
        self.load_git_accounts()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # --- Git Credential Helper Section ---
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

        # --- SSH Key Management Section ---
        ssh_group = QGroupBox("SSH Key Management")
        ssh_layout = QVBoxLayout(ssh_group)

        # Configurable Default SSH Key Path
        ssh_key_path_layout = QHBoxLayout()
        ssh_key_path_layout.addWidget(QLabel("Default SSH Key Path:"))
        self.default_ssh_key_path_input = QLineEdit(os.path.expanduser("~/.ssh/id_rsa"))
        ssh_key_path_layout.addWidget(self.default_ssh_key_path_input)
        self.browse_ssh_key_path_button = QPushButton("Browse...")
        self.browse_ssh_key_path_button.clicked.connect(self.browse_default_ssh_key_path)
        ssh_key_path_layout.addWidget(self.browse_ssh_key_path_button)
        ssh_layout.addLayout(ssh_key_path_layout)

        # SSH Agent Status Label
        self.ssh_agent_status_label = QLabel("SSH Agent Status: Unknown")
        ssh_layout.addWidget(self.ssh_agent_status_label)

        # Informational label about SSH Agent scope
        self.ssh_agent_info_label = QLabel(
            "Note: The SSH Agent started here runs for this application session. "
            "Lingering for your user will be automatically enabled/checked for background services."
        )
        self.ssh_agent_info_label.setWordWrap(True)
        self.ssh_agent_info_label.setStyleSheet("font-size: 11px; color: gray;")
        ssh_layout.addWidget(self.ssh_agent_info_label)

        # Buttons for SSH Agent (moved below status label)
        ssh_agent_buttons_layout = QHBoxLayout()
        self.start_ssh_agent_button = QPushButton("Start SSH Agent")
        self.start_ssh_agent_button.clicked.connect(self.toggle_ssh_agent)
        ssh_agent_buttons_layout.addWidget(self.start_ssh_agent_button)
        self.add_key_to_agent_button = QPushButton("Add Key to Agent")
        self.add_key_to_agent_button.clicked.connect(self.add_ssh_key_to_agent)
        ssh_agent_buttons_layout.addWidget(self.add_key_to_agent_button)
        ssh_agent_buttons_layout.addStretch(1)
        ssh_layout.addLayout(ssh_agent_buttons_layout)

        ssh_layout.addStretch(1)
        layout.addWidget(ssh_group)
        
        # --- Git Accounts Section ---
        accounts_group = QGroupBox("Configured Git Accounts")
        accounts_layout = QVBoxLayout(accounts_group)

        # Table to display accounts
        self.accounts_table_widget = QTableWidget()
        self.accounts_table_widget.setColumnCount(3) # Only display Username, Email, Host in table
        self.accounts_table_widget.setHorizontalHeaderLabels(["Username", "Email", "Host"])
        
        self.accounts_table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.accounts_table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.accounts_table_widget.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)

        self.accounts_table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.accounts_table_widget.setSelectionMode(QTableWidget.SingleSelection)
        self.accounts_table_widget.verticalHeader().setVisible(False)
        accounts_layout.addWidget(self.accounts_table_widget)

        # Buttons below the table
        account_buttons_layout = QHBoxLayout()

        # Generate New SSH Key button (moved here, anchored left)
        # This button's functionality is now primarily handled by the dialog,
        # but keep it here as a direct access point for generating keys for *selected* accounts.
        # It will launch the dialog pre-filled with selected account's email.
        self.generate_ssh_key_button = QPushButton("Generate Key for Selected Account...")
        self.generate_ssh_key_button.clicked.connect(self.generate_ssh_key_for_selected_account)
        self.generate_ssh_key_button.setEnabled(False) # Disable until an item is selected
        self.accounts_table_widget.itemSelectionChanged.connect(
            lambda: self.generate_ssh_key_button.setEnabled(len(self.accounts_table_widget.selectedIndexes()) > 0)
        )
        account_buttons_layout.addWidget(self.generate_ssh_key_button)

        account_buttons_layout.addStretch(1) # Push remove button to the right

        # Add New Account button (moved here, next to remove button)
        self.add_account_button = QPushButton("Add New Account...")
        self.add_account_button.clicked.connect(self.open_add_account_dialog)
        account_buttons_layout.addWidget(self.add_account_button)

        # Remove Selected Account button (smaller, anchored right)
        self.remove_account_button = QPushButton("Remove Selected Account")
        self.remove_account_button.setObjectName("removeButton")
        self.remove_account_button.clicked.connect(self.remove_selected_account)
        self.remove_account_button.setEnabled(False) # Disable until an item is selected
        self.accounts_table_widget.itemSelectionChanged.connect(
            lambda: self.remove_account_button.setEnabled(len(self.accounts_table_widget.selectedIndexes()) > 0)
        )
        self.remove_account_button.setFixedWidth(180)
        account_buttons_layout.addWidget(self.remove_account_button)

        accounts_layout.addLayout(account_buttons_layout)

        layout.addWidget(accounts_group)
        # --- End Git Accounts Section ---

        layout.addStretch(1)

        # Refresh button
        refresh_button = QPushButton("Refresh Git Settings")
        refresh_button.clicked.connect(self.load_git_config)
        layout.addWidget(refresh_button)

    def run_git_command(self, command_args, cwd=None, timeout=60):
        """Helper function to run a git command."""
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
            return False, "Error: 'git' command not found. Please ensure Git is installed and in your PATH."
        except subprocess.TimeoutExpired:
            return False, f"Error: Git command timed out after {timeout} seconds."
        except Exception as e:
            return False, f"An unexpected error occurred: {e}"

    def run_command(self, command_args, timeout=60):
        """Generic helper function to run any shell command."""
        try:
            result = subprocess.run(
                command_args,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False
            )
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return False, f"Command failed: {e.stderr.strip()}"
        except FileNotFoundError:
            return False, f"Error: Command '{command_args[0]}' not found. Please ensure it's installed and in your PATH."
        except subprocess.TimeoutExpired:
            return False, f"Error: Command timed out after {timeout} seconds."
        except Exception as e:
            return False, f"An unexpected error occurred: {e}"

    def load_git_config(self):
        """Loads current Git credential helper and SSH agent status."""
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
        self.load_git_accounts()

    def apply_credential_helper(self):
        """Applies the selected Git credential helper."""
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
            QMessageBox.information(self, "Success", f"Git credential helper set to '{selected_helper}' globally.")
        else:
            QMessageBox.critical(self, "Error", f"Failed to set credential helper: {message}")
        self.load_git_config()

    def check_ssh_agent_status(self):
        """Checks and updates the SSH agent status label and button text."""
        if "SSH_AUTH_SOCK" in os.environ and os.path.exists(os.environ["SSH_AUTH_SOCK"]):
            success, output = self.run_command(['ssh-add', '-l'], timeout=5)
            if success:
                self.ssh_agent_status_label.setText("SSH Agent Status: Running (Keys Loaded)")
                self.start_ssh_agent_button.setText("Stop SSH Agent")
                self.start_ssh_agent_button.setEnabled(True)
                self.add_key_to_agent_button.setEnabled(True)
            else:
                self.ssh_agent_status_label.setText(f"SSH Agent Status: Running (Error: {output or 'No keys loaded'})")
                self.start_ssh_agent_button.setText("Stop SSH Agent")
                self.start_ssh_agent_button.setEnabled(True)
                self.add_key_to_agent_button.setEnabled(True)
        else:
            self.ssh_agent_status_label.setText("SSH Agent Status: Not Running")
            self.start_ssh_agent_button.setText("Start SSH Agent")
            self.start_ssh_agent_button.setEnabled(True)
            self.add_key_to_agent_button.setEnabled(False)

    def toggle_ssh_agent(self):
        """Toggles the SSH agent state (start/stop)."""
        if "SSH_AUTH_SOCK" in os.environ and os.path.exists(os.environ["SSH_AUTH_SOCK"]):
            self.stop_ssh_agent()
        else:
            self.start_ssh_agent_process()

    def start_ssh_agent_process(self):
        """Starts the SSH agent, sets its environment variables, and enables lingering."""
        try:
            result = subprocess.run(['ssh-agent', '-s'], capture_output=True, text=True, check=True)
            output_lines = result.stdout.strip().split('\n')

            ssh_auth_sock = None
            ssh_agent_pid = None

            for line in output_lines:
                if line.startswith('SSH_AUTH_SOCK='):
                    ssh_auth_sock = line.split('=')[1].split(';')[0]
                elif line.startswith('SSH_AGENT_PID='):
                    ssh_agent_pid = line.split('=')[1].split(';')[0]

            if ssh_auth_sock and ssh_agent_pid:
                os.environ['SSH_AUTH_SOCK'] = ssh_auth_sock
                os.environ['SSH_AGENT_PID'] = ssh_agent_pid
                
                current_user = os.getenv('USER')
                if current_user:
                    linger_command = ['loginctl', 'enable-linger', current_user]
                    linger_success, linger_message = self.run_command(linger_command)
                    if linger_success:
                        QMessageBox.information(self, "SSH Agent Started",
                                                "SSH Agent started successfully for this application session.\n"
                                                f"Lingering enabled for user '{current_user}'. "
                                                "This allows background services to use the SSH agent after logout.")
                    else:
                        QMessageBox.warning(self, "Lingering Error",
                                            f"SSH Agent started, but failed to enable lingering for user '{current_user}': {linger_message}\n"
                                            "You may need to run `loginctl enable-linger YOUR_USERNAME` manually in your terminal.")
                else:
                    QMessageBox.warning(self, "User Not Found",
                                        "SSH Agent started, but could not determine current user to enable lingering. "
                                        "Please run `loginctl enable-linger YOUR_USERNAME` manually in your terminal.")
            else:
                QMessageBox.critical(self, "SSH Agent Error", f"Failed to parse SSH Agent output. Output:\n{result.stdout}")

        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "SSH Agent Error", f"Failed to start SSH Agent: {e.stderr.strip()}")
        except FileNotFoundError:
            QMessageBox.critical(self, "Error", "ssh-agent or loginctl command not found. Please ensure OpenSSH and systemd are installed and in your PATH.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")

        self.check_ssh_agent_status()

    def stop_ssh_agent(self):
        """Stops the currently running SSH agent."""
        if "SSH_AGENT_PID" not in os.environ:
            QMessageBox.warning(self, "SSH Agent Not Running", "SSH Agent is not running or its PID is not known to this application.")
            return

        pid = os.environ['SSH_AGENT_PID']
        reply = QMessageBox.question(self, "Stop SSH Agent",
                                     f"Are you sure you want to stop the SSH Agent (PID: {pid})?\n"
                                     "This will remove all loaded keys and might affect other applications using this agent.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        try:
            success, message = self.run_command(['kill', pid])
            if success:
                QMessageBox.information(self, "SSH Agent Stopped", f"SSH Agent (PID: {pid}) stopped successfully.")
                del os.environ['SSH_AUTH_SOCK']
                del os.environ['SSH_AGENT_PID']
            else:
                QMessageBox.critical(self, "SSH Agent Stop Error", f"Failed to stop SSH Agent: {message}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred while stopping SSH Agent: {e}")
        
        self.check_ssh_agent_status()

    def browse_default_ssh_key_path(self):
        """Opens a file dialog to select the default SSH private key path."""
        initial_path = self.default_ssh_key_path_input.text()
        file_path, ok = QFileDialog.getOpenFileName(self, "Select Default SSH Private Key",
                                                    initial_path,
                                                    "All Files (*);;Private Key Files (*id_rsa*)")
        if ok and file_path:
            self.default_ssh_key_path_input.setText(file_path)

    def add_ssh_key_to_agent(self):
        """Adds a selected SSH key to the SSH agent."""
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

        success, message = self.run_command(['ssh-add', key_path])
        if success:
            QMessageBox.information(self, "Success", f"SSH key '{key_path}' added to agent.")
        else:
            QMessageBox.critical(self, "Error", f"Failed to add SSH key to agent: {message}\n"
                                 "Ensure SSH agent is running and you have entered your passphrase if prompted in the terminal.")
        self.check_ssh_agent_status()

    def generate_ssh_key_for_selected_account(self):
        """Launches the AddAccountDialog pre-filled for generating a key for a selected account."""
        selected_rows = self.accounts_table_widget.selectedIndexes()
        if not selected_rows:
            QMessageBox.warning(self, "No Account Selected", "Please select a Git account from the table to generate an SSH key for it.")
            return

        selected_row_index = selected_rows[0].row()
        selected_account_data = self.git_accounts_data[selected_row_index]

        dialog = AddAccountDialog(self.config_dir, self.run_command, self)
        dialog.username_input.setText(selected_account_data['username'])
        dialog.email_input.setText(selected_account_data['email'])
        dialog.host_combobox.setCurrentText(selected_account_data['host'])
        dialog.auth_type_combobox.setCurrentText("SSH Key") # Force SSH Key selection
        dialog.generate_key_radio.setChecked(True) # Force generate new key
        dialog.username_input.setReadOnly(True) # Make fields read-only if pre-filled
        dialog.email_input.setReadOnly(True)
        dialog.host_combobox.setEnabled(False) # Disable host combobox

        if dialog.exec() == QDialog.Accepted:
            new_account_data = dialog.get_account_data()
            # If a key was generated, update the last_generated_key_path
            if new_account_data.get('auth_type') == 'SSH Key' and new_account_data.get('ssh_key_path'):
                self.last_generated_key_path = new_account_data['ssh_key_path']
            # No need to add/update account here, as this function is specifically for key generation for *existing* accounts.
            # The SSH config update happens within the dialog's generate_key_pair_in_dialog.
            QMessageBox.information(self, "Key Generation Complete", "SSH key generation process finished.")
        self.load_git_accounts() # Refresh table in case something changed (e.g., if we allowed updating existing entry)


    def open_add_account_dialog(self):
        """Opens the dialog to add a new Git account."""
        dialog = AddAccountDialog(self.config_dir, self.run_command, self)
        if dialog.exec() == QDialog.Accepted:
            new_account_data = dialog.get_account_data()
            
            username = new_account_data['username']
            email = new_account_data['email']
            host = new_account_data['host']
            auth_type = new_account_data['auth_type']
            ssh_key_path = new_account_data.get('ssh_key_path')

            # Check for duplicates before adding
            if any(acc['username'] == username and acc['host'] == host for acc in self.git_accounts_data):
                QMessageBox.information(self, "Duplicate Account", f"An account for '{username}' on '{host}' already exists. Please update it instead.")
                return

            # Add the new account data to our list
            account_to_save = {
                'username': username,
                'email': email,
                'host': host,
                'auth_type': auth_type
            }
            if auth_type == 'SSH Key':
                account_to_save['ssh_key_path'] = ssh_key_path
                self.last_generated_key_path = ssh_key_path # Update last generated key path

            self.git_accounts_data.append(account_to_save)
            self._add_account_to_table(account_to_save) # Add to UI table
            self.save_git_accounts() # Save to file
            QMessageBox.information(self, "Account Added", f"Git account for '{username}' on '{host}' added successfully.")
        self.load_git_accounts() # Refresh table to show new entry


    def load_git_accounts(self):
        """Loads Git account data from the git_accounts.json file and populates the table."""
        self.accounts_table_widget.setRowCount(0)
        self.git_accounts_data = []

        if not os.path.exists(self.git_accounts_file):
            return

        try:
            with open(self.git_accounts_file, 'r') as f:
                accounts_config = json.load(f)
                if not isinstance(accounts_config, list):
                    QMessageBox.warning(self, "Configuration Error",
                                        f"Git accounts file '{self.git_accounts_file}' is malformed. Expected a list of objects.")
                    return
                
                for entry in accounts_config:
                    # Ensure all expected keys are present with defaults for older configs
                    account_data = {
                        'username': entry.get('username', ''),
                        'email': entry.get('email', ''),
                        'host': entry.get('host', 'Other'),
                        'auth_type': entry.get('auth_type', 'Password'), # Default to Password for old entries
                        'ssh_key_path': entry.get('ssh_key_path', None)
                    }
                    if account_data['username'] and account_data['email'] and account_data['host']:
                        self.git_accounts_data.append(account_data)
                        self._add_account_to_table(account_data)
                    else:
                        QMessageBox.warning(self, "Configuration Warning",
                                            f"Skipping malformed or incomplete account entry in config file: {entry}")
        except json.JSONDecodeError:
            QMessageBox.warning(self, "Configuration Error",
                                f"Error reading Git accounts file '{self.git_accounts_file}'. It might be corrupted.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred while loading Git accounts: {e}")

    def _add_account_to_table(self, account_data):
        """Helper to add a single account's data to the QTableWidget."""
        row_position = self.accounts_table_widget.rowCount()
        self.accounts_table_widget.insertRow(row_position)

        self.accounts_table_widget.setItem(row_position, 0, QTableWidgetItem(account_data['username']))
        self.accounts_table_widget.setItem(row_position, 1, QTableWidgetItem(account_data['email']))
        self.accounts_table_widget.setItem(row_position, 2, QTableWidgetItem(account_data['host']))
        # Note: auth_type and ssh_key_path are stored in self.git_accounts_data but not displayed in the main table for brevity.

    def save_git_accounts(self):
        """Saves the current list of Git accounts to the git_accounts.json file."""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.git_accounts_file, 'w') as f:
                json.dump(self.git_accounts_data, f, indent=4)
            QMessageBox.information(self, "Accounts Saved", "Git accounts saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save Git accounts: {e}")

    def add_git_account(self):
        """Deprecated: This function is replaced by open_add_account_dialog."""
        pass # This function is now replaced by open_add_account_dialog

    def remove_selected_account(self):
        """Removes the selected Git account from the table and data."""
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
            
            # Remove from internal data list
            self.git_accounts_data = [
                acc for acc in self.git_accounts_data 
                if not (acc['username'] == username_to_remove and acc['host'] == host_to_remove)
            ]
            
            self.accounts_table_widget.removeRow(selected_row_index)
            self.save_git_accounts()
            QMessageBox.information(self, "Account Removed", f"Git account for '{username_to_remove}' on '{host_to_remove}' removed successfully.")
        else:
            QMessageBox.critical(self, "Error", "Could not retrieve selected account data for removal.")
