# gitbuddy_service_manager_tab.py

import subprocess
import os
import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPalette, QColor
import time # Import time for sleep

class ServiceManagerTab(QWidget):
    def __init__(self, config_dir, parent=None):
        super().__init__(parent)
        self.config_dir = config_dir
        self.systemd_user_dir = os.path.expanduser("~/.config/systemd/user/")
        
        # Determine the application's root directory (where gitbuddy_app.py is located)
        # This assumes git_puller_service.py is in the same directory as the main app script
        self.app_root_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

        # Paths for existing units
        self.service_file_path = os.path.join(self.systemd_user_dir, "gitbuddy.service")
        self.timer_file_path = os.path.join(self.systemd_user_dir, "gitbuddy.timer")

        # Paths for new units
        self.logout_sync_service_file_path = os.path.join(self.systemd_user_dir, "gitbuddy-logout-sync.service")
        self.login_pull_service_file_path = os.path.join(self.systemd_user_dir, "gitbuddy-login-pull.service")

        self.init_ui()
        self.update_service_status() # Initial status update

        # Set up a timer to periodically update service status
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_service_status)
        self.status_timer.start(5000) # Update every 5 seconds

    def init_ui(self):
        """Initializes the service manager tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Service Status Section
        status_frame = QFrame()
        status_frame.setObjectName("statusFrame")
        status_layout = QHBoxLayout(status_frame)
        self.status_label = QLabel("GitBuddy Service Status: Checking...")
        self.status_label.setObjectName("statusLabel")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch(1)
        layout.addWidget(status_frame)

        # Service Control Buttons
        service_control_layout = QHBoxLayout()
        self.start_service_button = QPushButton("Start Service")
        self.start_service_button.setObjectName("startButton")
        self.start_service_button.clicked.connect(self.start_service)
        service_control_layout.addWidget(self.start_service_button)

        self.stop_service_button = QPushButton("Stop Service")
        self.stop_service_button.setObjectName("stopButton")
        self.stop_service_button.clicked.connect(self.stop_service)
        service_control_layout.addWidget(self.stop_service_button)

        refresh_status_button = QPushButton("Refresh Status")
        refresh_status_button.clicked.connect(self.update_service_status)
        service_control_layout.addWidget(refresh_status_button)
        service_control_layout.addStretch(1)
        layout.addLayout(service_control_layout)

        # Installation Section
        installation_frame = QFrame()
        installation_frame.setObjectName("installationFrame")
        installation_layout = QVBoxLayout(installation_frame)
        installation_layout.addWidget(QLabel("Service Installation/Uninstallation:"))

        install_buttons_layout = QHBoxLayout()
        self.install_button = QPushButton("Install All Services")
        self.install_button.clicked.connect(self.install_all_services)
        install_buttons_layout.addWidget(self.install_button)

        self.uninstall_button = QPushButton("Uninstall All Services")
        self.uninstall_button.setObjectName("removeButton")
        self.uninstall_button.clicked.connect(self.uninstall_all_services)
        install_buttons_layout.addWidget(self.uninstall_button)
        install_buttons_layout.addStretch(1)
        
        installation_layout.addLayout(install_buttons_layout)

        layout.addWidget(installation_frame)
        layout.addStretch(1)

    def run_systemctl_command(self, command, service_name="", suppress_errors=False):
        """
        Helper to run systemctl commands and return output/error.
        Conditionally appends service_name only if it's not empty.
        Added suppress_errors to avoid popups for commands that might fail expectedly (e.g., stopping non-existent service).
        """
        cmd_list = ['systemctl', '--user', command]
        if service_name:
            cmd_list.append(service_name)

        try:
            result = subprocess.run(
                cmd_list,
                capture_output=True,
                text=True,
                check=False
            )
            if not suppress_errors and not result.returncode == 0:
                QMessageBox.critical(self, "Systemctl Error", f"Command failed: {' '.join(cmd_list)}\nOutput: {result.stderr.strip()}")
            return result.stdout.strip(), result.stderr.strip(), result.returncode == 0
        except FileNotFoundError:
            if not suppress_errors:
                QMessageBox.critical(self, "Error", "systemctl command not found. Please ensure systemd is installed and in your PATH.")
            return "", "systemctl not found", False
        except Exception as e:
            if not suppress_errors:
                QMessageBox.critical(self, "Error", f"An unexpected error occurred while running systemctl: {e}")
            return "", str(e), False

    def _unit_file_exists(self, path):
        """Checks if a systemd unit file exists at the given path."""
        return os.path.exists(path)

    def _is_unit_loaded(self, unit_name):
        """Checks if a systemd unit is loaded (known to systemd)."""
        stdout, _, _ = self.run_systemctl_command("list-unit-files", suppress_errors=True)
        # Check if the unit name appears in the list of unit files known to systemd
        return f"{unit_name} " in stdout or f"{unit_name}\t" in stdout

    def _is_unit_enabled(self, unit_name):
        """Checks if a systemd unit is enabled."""
        stdout, _, success = self.run_systemctl_command("is-enabled", unit_name, suppress_errors=True)
        return success and "enabled" in stdout # Only true if command succeeds and output contains "enabled"

    def _is_unit_active(self, unit_name):
        """Checks if a systemd unit is active (running)."""
        stdout, _, success = self.run_systemctl_command("is-active", unit_name, suppress_errors=True)
        return success and "active" in stdout # Only true if command succeeds and output contains "active"

    def are_all_services_installed(self):
        """Checks if all GitBuddy systemd units are installed and enabled."""
        # Check if files exist
        main_service_file_exists = self._unit_file_exists(self.service_file_path)
        timer_file_exists = self._unit_file_exists(self.timer_file_path)
        logout_service_file_exists = self._unit_file_exists(self.logout_sync_service_file_path)
        login_service_file_exists = self._unit_file_exists(self.login_pull_service_file_path)

        all_files_exist = (main_service_file_exists and timer_file_exists and
                           logout_service_file_exists and login_service_file_exists)
        
        if not all_files_exist:
            return False

        # Check if all are enabled
        main_service_enabled = self._is_unit_enabled("gitbuddy.service")
        timer_enabled = self._is_unit_enabled("gitbuddy.timer")
        logout_service_enabled = self._is_unit_enabled("gitbuddy-logout-sync.service")
        login_service_enabled = self._is_unit_enabled("gitbuddy-login-pull.service")

        return (main_service_enabled and timer_enabled and 
                logout_service_enabled and login_service_enabled)


    def install_all_services(self):
        """Installs (creates and enables) all GitBuddy systemd units."""
        if self.are_all_services_installed():
            QMessageBox.information(self, "Installation Status", "All GitBuddy services are already installed and enabled.")
            return

        python_executable = sys.executable
        # Service script path is now relative to the application's root directory
        service_script_path = os.path.join(self.app_root_dir, "git_puller_service.py")

        # --- CRITICAL CHECK: Ensure the Python service script exists ---
        if not os.path.exists(service_script_path):
            QMessageBox.critical(self, "Installation Error",
                                 f"The GitBuddy service script was not found!\n"
                                 f"Please ensure '{os.path.basename(service_script_path)}' is located in:\n"
                                 f"'{self.app_root_dir}'\n\n"
                                 "Installation aborted.")
            return
        # --- END CRITICAL CHECK ---

        os.makedirs(self.systemd_user_dir, exist_ok=True)

        # 1. gitbuddy.service (Main periodic service)
        service_content = f"""
[Unit]
Description=GitBuddy Repository Sync Service
Documentation=https://github.com/yourusername/git-buddy
After=network-online.target

[Service]
Type=simple
ExecStart={python_executable} {service_script_path}
WorkingDirectory={self.app_root_dir}
StandardOutput=journal
StandardError=journal
# Restart=on-failure

# [Install]
# WantedBy=default.target
# Removed WantedBy from service as it's primarily started by the timer
"""
        # 2. gitbuddy.timer (Timer for main periodic service)
        timer_content = f"""
[Unit]
Description=Start GitBuddy Periodic Service

[Timer]
OnBootSec=1min
OnUnitActiveSec=1h

[Install]
WantedBy=timers.target
"""
        # 3. gitbuddy-logout-sync.service (One-shot for commit/push on logout/shutdown)
        logout_sync_content = f"""
[Unit]
Description=GitBuddy Logout/Shutdown Sync
After=multi-user.target graphical-session-pre.target

[Service]
Type=oneshot
ExecStart={python_executable} {service_script_path} --commit-push-on-exit
WorkingDirectory={self.app_root_dir}
RemainAfterExit=yes
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"""
        # 4. gitbuddy-login-pull.service (One-shot for pull on login)
        login_pull_content = f"""
[Unit]
Description=GitBuddy Login Pull
After=graphical-session.target

[Service]
Type=oneshot
ExecStart={python_executable} {service_script_path} --pull-on-login
WorkingDirectory={self.app_root_dir}
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical-session.target
"""

        try:
            # Write all service files
            with open(self.service_file_path, 'w') as f: f.write(service_content.strip())
            with open(self.timer_file_path, 'w') as f: f.write(timer_content.strip())
            with open(self.logout_sync_service_file_path, 'w') as f: f.write(logout_sync_content.strip())
            with open(self.login_pull_service_file_path, 'w') as f: f.write(login_pull_content.strip())

            # Reload systemd daemon
            stdout, stderr, success = self.run_systemctl_command("daemon-reload", "")
            if not success:
                QMessageBox.critical(self, "Installation Error", f"Failed to reload systemd daemon:\n{stderr}")
                return
            time.sleep(1) # Small delay after daemon-reload

            # Enable and start all units
            success_enable_service, _, _ = self.run_systemctl_command("enable", "gitbuddy.service")
            if not success_enable_service:
                QMessageBox.warning(self, "Installation Warning", "Failed to enable gitbuddy.service.")

            success_enable_timer, _, _ = self.run_systemctl_command("enable", "gitbuddy.timer")
            if not success_enable_timer:
                QMessageBox.warning(self, "Installation Warning", "Failed to enable gitbuddy.timer.")

            success_start_timer, stderr_start_timer, success_start_timer_cmd = self.run_systemctl_command("start", "gitbuddy.timer")
            if not success_start_timer_cmd:
                QMessageBox.warning(self, "Installation Warning", f"Failed to start gitbuddy.timer:\n{stderr_start_timer}")
            else:
                # Give it a moment to activate the service
                time.sleep(2) # Increased sleep
                if not self._is_unit_active("gitbuddy.service"):
                    QMessageBox.warning(self, "Installation Warning", "gitbuddy.service did not become active after timer start. Check 'journalctl --user -u gitbuddy.service'.")


            success_enable_logout, _, _ = self.run_systemctl_command("enable", "gitbuddy-logout-sync.service")
            if not success_enable_logout:
                QMessageBox.warning(self, "Installation Warning", "Failed to enable gitbuddy-logout-sync.service.")

            success_enable_login, _, _ = self.run_systemctl_command("enable", "gitbuddy-login-pull.service")
            if not success_enable_login:
                QMessageBox.warning(self, "Installation Warning", "Failed to enable gitbuddy-login-pull.service.")

            # Add a final check to see if all are truly enabled
            if self.are_all_services_installed():
                QMessageBox.information(self, "Installation Success",
                                        "All GitBuddy services and timers installed and configured successfully!\n"
                                        "The periodic service is running. Logout/Shutdown sync and Login pull will run automatically.\n\n"
                                        "IMPORTANT: For services to run after you log out or before you log in, you might need to enable lingering for your user:\n"
                                        f"  loginctl enable-linger {os.getenv('USER') or 'your_username'}\n"
                                        "This command only needs to be run once per user.")
            else:
                QMessageBox.warning(self, "Installation Warning", "Some services might not have been fully installed or enabled. Please check 'journalctl --user' for details.")

        except Exception as e:
            QMessageBox.critical(self, "Installation Error", f"An error occurred during installation: {e}")
        finally:
            self.update_service_status()

    def uninstall_all_services(self):
        """Uninstalls (stops, disables, and removes) all GitBuddy systemd units."""
        reply = QMessageBox.question(self, "Confirm Uninstall",
                                     "Are you sure you want to uninstall ALL GitBuddy services and timers?\n"
                                     "This will stop all services, disable them from starting on boot, and remove their systemd unit files.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        try:
            # Stop all services (suppress errors if they're not running)
            self.run_systemctl_command("stop", "gitbuddy.timer", suppress_errors=True)
            self.run_systemctl_command("stop", "gitbuddy.service", suppress_errors=True)
            self.run_systemctl_command("stop", "gitbuddy-logout-sync.service", suppress_errors=True)
            self.run_systemctl_command("stop", "gitbuddy-login-pull.service", suppress_errors=True)

            # Disable all services (suppress errors if they're not enabled)
            self.run_systemctl_command("disable", "gitbuddy.timer", suppress_errors=True)
            self.run_systemctl_command("disable", "gitbuddy.service", suppress_errors=True)
            self.run_systemctl_command("disable", "gitbuddy-logout-sync.service", suppress_errors=True)
            self.run_systemctl_command("disable", "gitbuddy-login-pull.service", suppress_errors=True)

            # Remove the unit files
            files_to_remove = [
                self.service_file_path,
                self.timer_file_path,
                self.logout_sync_service_file_path,
                self.login_pull_service_file_path
            ]
            for f_path in files_to_remove:
                if os.path.exists(f_path):
                    os.remove(f_path)
                    logging.info(f"Removed unit file: {f_path}")

            # Reload systemd daemon to unregister the units
            stdout, stderr, success = self.run_systemctl_command("daemon-reload", "")
            if not success:
                QMessageBox.critical(self, "Uninstall Error", f"Failed to reload systemd daemon during uninstall:\n{stderr}")
                QMessageBox.information(self, "Uninstall Success (Partial)",
                                        "GitBuddy service files removed, but daemon-reload failed. You may need to manually reload systemd.")
            else:
                QMessageBox.information(self, "Uninstall Success",
                                        "All GitBuddy services and timers uninstalled successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Uninstall Error", f"An error occurred during uninstallation: {e}")
        finally:
            self.update_service_status()

    def start_service(self):
        """Starts the main periodic systemd service."""
        # Start the timer unit; it will activate the service
        stdout, stderr, success = self.run_systemctl_command("start", "gitbuddy.timer")
        if success:
            QMessageBox.information(self, "Service Control", "GitBuddy periodic service started successfully.")
        else:
            QMessageBox.warning(self, "Service Control", f"Failed to start periodic service:\n{stderr}")
        self.update_service_status()

    def stop_service(self):
        """Stops the main periodic systemd service."""
        # Stop the timer unit; it will also stop the service it manages
        stdout, stderr, success = self.run_systemctl_command("stop", "gitbuddy.timer")
        if success:
            QMessageBox.information(self, "Service Control", "GitBuddy periodic service stopped successfully.")
        else:
            QMessageBox.warning(self, "Service Control", f"Failed to stop periodic service:\n{stderr}")
        self.update_service_status()

    def update_service_status(self):
        """Updates the status label based on systemd service status and installation status."""
        palette = self.palette()
        text_color = palette.color(QPalette.WindowText)

        all_installed = self.are_all_services_installed()

        if not all_installed:
            service_display_text = "Not Installed"
            text_color = palette.color(QPalette.BrightText) if palette.color(QPalette.BrightText).isValid() else QColor("red")
            self.install_button.setEnabled(True)
            self.uninstall_button.setEnabled(False)
            self.start_service_button.setEnabled(False)
            self.stop_service_button.setEnabled(False)
        else:
            # Check status of the main periodic service
            stdout, stderr, success = self.run_systemctl_command("is-active", "gitbuddy.service", suppress_errors=True)
            if "active" in stdout:
                service_display_text = "Running"
                text_color = palette.color(QPalette.Highlight) if palette.color(QPalette.Highlight).isValid() else QColor("#4CAF50")
                self.start_service_button.setEnabled(False)
                self.stop_service_button.setEnabled(True)
            elif "inactive" in stdout:
                service_display_text = "Stopped"
                text_color = palette.color(QPalette.WindowText)
                self.start_service_button.setEnabled(True)
                self.stop_service_button.setEnabled(False)
            elif "failed" in stdout:
                service_display_text = "Failed"
                text_color = palette.color(QPalette.BrightText) if palette.color(QPalette.BrightText).isValid() else QColor("#f44336")
                self.start_service_button.setEnabled(True)
                self.stop_service_button.setEnabled(False)
            else:
                service_display_text = f"Unknown ({stdout})"
                text_color = palette.color(QPalette.ToolTipBase) if palette.color(QPalette.ToolTipBase).isValid() else QColor("orange")
                self.start_service_button.setEnabled(True)
                self.stop_service_button.setEnabled(True)

            self.install_button.setEnabled(False)
            self.uninstall_button.setEnabled(True)

        self.status_label.setText(f"GitBuddy Service Status: <span style='color:{text_color.name()};'>{service_display_text}</span>")
