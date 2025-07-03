# git_puller_service.py

import json
import subprocess
import os
import logging
import time
import signal
import sys
from datetime import datetime, timedelta
import argparse # Import argparse for command-line argument parsing

# Define the configuration file path
CONFIG_DIR = os.path.expanduser("~/.config/git-buddy")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
LOG_FILE = os.path.join(CONFIG_DIR, "git_buddy.log")

# Ensure the configuration directory exists
os.makedirs(CONFIG_DIR, exist_ok=True)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler() # This sends logs to stderr, which systemd captures
    ]
)

# Global flag to control the main loop
running = True

def signal_handler(signum, frame):
    """
    Handles termination signals (e.g., SIGTERM from systemd) to gracefully stop the service.
    For the main periodic loop, this sets 'running' to False.
    One-shot services handle their own exit.
    """
    global running
    logging.info(f"Received signal {signum}. Shutting down GitBuddy service gracefully...")
    running = False

# Register the signal handler for SIGTERM for the main loop
signal.signal(signal.SIGTERM, signal_handler)

def send_notification(title, message):
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

def load_repositories():
    """
    Loads the list of Git repository configurations from the configuration file.
    Each entry is expected to be a dictionary with 'path' and other optional keys.
    Initializes 'last_pulled_at', 'last_committed_at', and 'last_pushed_at' for internal tracking.
    Converts intervals from minutes to seconds.
    Returns an empty list if the file does not exist or is malformed.
    """
    if not os.path.exists(CONFIG_FILE):
        logging.warning(f"Configuration file not found: {CONFIG_FILE}. Returning empty list.")
        return []
    try:
        with open(CONFIG_FILE, 'r') as f:
            repos_config = json.load(f)
            if not isinstance(repos_config, list):
                logging.error(f"Configuration file {CONFIG_FILE} is malformed. Expected a list.")
                return []

            repositories = []
            for entry in repos_config:
                if not isinstance(entry, dict) or 'path' not in entry:
                    logging.warning(f"Malformed repository entry: {entry}. Skipping.")
                    continue

                repo_path = entry['path']
                
                auto_pull = entry.get('auto_pull', True)
                pull_interval_minutes = entry.get('pull_interval', 5)
                auto_commit = entry.get('auto_commit', False)
                commit_interval_minutes = entry.get('commit_interval', 60)
                commit_message_template = entry.get('commit_message_template', "Auto-commit from GitBuddy: {timestamp}")
                auto_push = entry.get('auto_push', False)
                push_interval_minutes = entry.get('push_interval', 60)

                # Validate intervals and convert to seconds
                if not isinstance(pull_interval_minutes, (int, float)) or pull_interval_minutes <= 0:
                    logging.warning(f"Invalid pull_interval for {repo_path}. Using default 5 minutes.")
                    pull_interval_minutes = 5
                pull_interval_seconds = pull_interval_minutes * 60

                if not isinstance(commit_interval_minutes, (int, float)) or commit_interval_minutes <= 0:
                    logging.warning(f"Invalid commit_interval for {repo_path}. Using default 60 minutes.")
                    commit_interval_minutes = 60
                commit_interval_seconds = commit_interval_minutes * 60

                if not isinstance(push_interval_minutes, (int, float)) or push_interval_minutes <= 0:
                    logging.warning(f"Invalid push_interval for {repo_path}. Using default 60 minutes.")
                    push_interval_minutes = 60
                push_interval_seconds = push_interval_minutes * 60

                repositories.append({
                    'path': repo_path,
                    'auto_pull': auto_pull,
                    'pull_interval': pull_interval_seconds,
                    'last_pulled_at': datetime.min,
                    'auto_commit': auto_commit,
                    'commit_interval': commit_interval_seconds,
                    'last_committed_at': datetime.min,
                    'commit_message_template': commit_message_template,
                    'auto_push': auto_push,
                    'push_interval': push_interval_seconds,
                    'last_pushed_at': datetime.min
                })
            return repositories
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from {CONFIG_FILE}: {e}")
        return []
    except Exception as e:
        logging.error(f"An unexpected error occurred while loading config: {e}")
        return []

def run_git_command(repo_path, command_args, timeout=300):
    """
    Helper function to run a git command in a specified repository.
    """
    if not os.path.isdir(repo_path):
        logging.error(f"Path is not a directory: {repo_path}. Cannot run git command.")
        return False, "Not a directory"

    git_dir = os.path.join(repo_path, ".git")
    if not os.path.isdir(git_dir):
        logging.error(f"Not a Git repository: {repo_path}. Missing .git directory.")
        return False, "Not a Git repository"

    full_command = ['git'] + command_args
    logging.info(f"Executing '{' '.join(full_command)}' in {repo_path}")
    try:
        result = subprocess.run(
            full_command,
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        logging.info(f"Command success for {repo_path}: {result.stdout.strip()}")
        if result.stderr:
            logging.warning(f"Command for {repo_path} had stderr output:\n{result.stderr.strip()}")
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed for {repo_path}. Error: {e}")
        logging.error(f"stdout: {e.stdout.strip()}")
        logging.error(f"stderr: {e.stderr.strip()}")
        return False, e.stderr.strip()
    except FileNotFoundError:
        logging.error("Git command not found. Please ensure Git is installed and in your PATH.")
        return False, "Git command not found"
    except subprocess.TimeoutExpired:
        logging.error(f"Command for {repo_path} timed out after {timeout} seconds.")
        return False, "Command timed out"
    except Exception as e:
        logging.error(f"An unexpected error occurred while running git command in {repo_path}: {e}")
        return False, str(e)

def pull_repository(repo_path):
    """Attempts to perform a 'git pull'."""
    logging.info(f"Attempting to pull repository: {repo_path}")
    success, message = run_git_command(repo_path, ['pull'])
    if success:
        logging.info(f"Successfully pulled {repo_path}")
        send_notification("GitBuddy: Pull Complete", f"Repository: {os.path.basename(repo_path)}\nOperation: Pull")
    else:
        logging.error(f"Failed to pull {repo_path}: {message}")
        send_notification("GitBuddy: Pull Failed", f"Repository: {os.path.basename(repo_path)}\nError: {message}")
    return success

def commit_repository(repo_path, commit_message_template):
    """
    Stages all changes and performs a 'git commit'.
    Uses a human-readable timestamp in the commit message.
    """
    # First, check if there are any changes to commit
    # 'git status --porcelain' returns a non-empty string if there are changes
    success_status, output_status = run_git_command(repo_path, ['status', '--porcelain'], timeout=60)
    if not success_status:
        logging.error(f"Failed to get git status for {repo_path}. Skipping commit.")
        send_notification("GitBuddy: Commit Failed", f"Repository: {os.path.basename(repo_path)}\nError: Failed to get status.")
        return False
    
    if not output_status.strip():
        logging.info(f"No changes to commit in {repo_path}. Skipping commit.")
        return False

    logging.info(f"Staging changes in {repo_path}...")
    success_add, message_add = run_git_command(repo_path, ['add', '.'])
    if not success_add:
        logging.error(f"Failed to stage changes in {repo_path}: {message_add}")
        send_notification("GitBuddy: Commit Failed", f"Repository: {os.path.basename(repo_path)}\nError: Failed to stage changes.")
        return False

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    commit_message = commit_message_template.format(timestamp=timestamp)
    logging.info(f"Attempting to commit {repo_path} with message: '{commit_message}'")
    success_commit, message_commit = run_git_command(repo_path, ['commit', '-m', commit_message])
    if success_commit:
        logging.info(f"Successfully committed {repo_path}")
        send_notification("GitBuddy: Commit Complete", f"Repository: {os.path.basename(repo_path)}\nOperation: Commit")
    else:
        logging.error(f"Failed to commit {repo_path}: {message_commit}")
        send_notification("GitBuddy: Commit Failed", f"Repository: {os.path.basename(repo_path)}\nError: {message_commit}")
    return success_commit

def push_repository(repo_path):
    """Attempts to perform a 'git push'."""
    logging.info(f"Attempting to push repository: {repo_path}")
    success, message = run_git_command(repo_path, ['push'])
    if success:
        logging.info(f"Successfully pushed {repo_path}")
        send_notification("GitBuddy: Push Complete", f"Repository: {os.path.basename(repo_path)}\nOperation: Push")
    else:
        logging.error(f"Failed to push {repo_path}: {message}")
        send_notification("GitBuddy: Push Failed", f"Repository: {os.path.basename(repo_path)}\nError: {message}")
    return success

def perform_commit_push_for_all_repos():
    """
    Performs commit and push operations for all configured repositories
    where auto_commit and auto_push are enabled.
    Intended for one-shot execution (e.g., on logout/shutdown).
    """
    logging.info("Initiating one-shot commit and push for all enabled repositories.")
    repositories = load_repositories()
    if not repositories:
        logging.info("No repositories configured for one-shot commit/push.")
        return

    for repo_data in repositories:
        repo_path = repo_data['path']
        repo_name = os.path.basename(repo_path)
        
        if repo_data['auto_commit']:
            logging.info(f"Attempting one-shot commit for {repo_name}...")
            if commit_repository(repo_path, repo_data['commit_message_template']):
                logging.info(f"One-shot commit successful for {repo_name}.")
            else:
                logging.warning(f"One-shot commit failed for {repo_name}.")
        else:
            logging.debug(f"Auto-commit disabled for {repo_name}. Skipping one-shot commit.")

        if repo_data['auto_push']:
            logging.info(f"Attempting one-shot push for {repo_name}...")
            if push_repository(repo_path):
                logging.info(f"One-shot push successful for {repo_name}.")
            else:
                logging.warning(f"One-shot push failed for {repo_name}.")
        else:
            logging.debug(f"Auto-push disabled for {repo_name}. Skipping one-shot push.")
    logging.info("One-shot commit and push operations completed.")

def perform_pull_for_all_repos():
    """
    Performs pull operations for all configured repositories
    where auto_pull is enabled.
    Intended for one-shot execution (e.g., on login).
    """
    logging.info("Initiating one-shot pull for all enabled repositories.")
    repositories = load_repositories()
    if not repositories:
        logging.info("No repositories configured for one-shot pull.")
        return

    for repo_data in repositories:
        repo_path = repo_data['path']
        repo_name = os.path.basename(repo_path)

        if repo_data['auto_pull']:
            logging.info(f"Attempting one-shot pull for {repo_name}...")
            if pull_repository(repo_path):
                logging.info(f"One-shot pull successful for {repo_name}.")
            else:
                logging.warning(f"One-shot pull failed for {repo_name}.")
        else:
            logging.debug(f"Auto-pull disabled for {repo_name}. Skipping one-shot pull.")
    logging.info("One-shot pull operations completed.")


def main():
    """
    Main function to execute the Git operations based on command-line arguments
    or run the periodic service loop.
    """
    parser = argparse.ArgumentParser(description="GitBuddy Background Service")
    parser.add_argument('--commit-push-on-exit', action='store_true',
                        help="Perform a one-shot commit and push for all enabled repos.")
    parser.add_argument('--pull-on-login', action='store_true',
                        help="Perform a one-shot pull for all enabled repos.")
    args = parser.parse_args()

    if args.commit_push_on_exit:
        logging.info("GitBuddy service started in --commit-push-on-exit mode.")
        perform_commit_push_for_all_repos()
        sys.exit(0)
    elif args.pull_on_login:
        logging.info("GitBuddy service started in --pull-on-login mode.")
        perform_pull_for_all_repos()
        sys.exit(0)
    else:
        # This is the main periodic loop
        logging.info(f"GitBuddy periodic service started at {datetime.now()}")

        SERVICE_POLLING_INTERVAL_SECONDS = 30 # Check every 30 seconds

        # Load repositories initially
        repositories = load_repositories()

        while running:
            # Reload repositories periodically to pick up changes from the GUI
            current_repositories_config = load_repositories()

            # Merge new config with existing 'last_pulled_at', 'last_committed_at', and 'last_pushed_at' timestamps
            updated_repositories = []
            for new_repo_entry in current_repositories_config:
                found = False
                for old_repo_entry in repositories:
                    if new_repo_entry['path'] == old_repo_entry['path']:
                        new_repo_entry['last_pulled_at'] = old_repo_entry['last_pulled_at']
                        new_repo_entry['last_committed_at'] = old_repo_entry.get('last_committed_at', datetime.min)
                        new_repo_entry['last_pushed_at'] = old_repo_entry['last_pushed_at']
                        updated_repositories.append(new_repo_entry)
                        found = True
                        break
                if not found:
                    updated_repositories.append(new_repo_entry)
            repositories = updated_repositories

            if not repositories:
                logging.info("No repositories configured. Waiting for configuration...")
            else:
                for repo_data in repositories:
                    if not running:
                        break

                    repo_path = repo_data['path']
                    
                    # --- Pull Logic ---
                    if repo_data['auto_pull']:
                        pull_interval_seconds = repo_data['pull_interval']
                        last_pulled = repo_data['last_pulled_at']
                        time_since_last_pull = datetime.now() - last_pulled
                        
                        if time_since_last_pull.total_seconds() >= pull_interval_seconds:
                            logging.info(f"Repository {repo_path} is due for a pull (last pulled {time_since_last_pull} ago).")
                            if pull_repository(repo_path):
                                repo_data['last_pulled_at'] = datetime.now()
                    else:
                        logging.debug(f"Auto-pull is disabled for {repo_path}.")


                    # --- Commit Logic (Now time-based) ---
                    if repo_data['auto_commit']:
                        commit_interval_seconds = repo_data['commit_interval']
                        last_committed = repo_data['last_committed_at']
                        time_since_last_commit = datetime.now() - last_committed
                        
                        if time_since_last_commit.total_seconds() >= commit_interval_seconds:
                            logging.info(f"Repository {repo_path} is due for a commit (last committed {time_since_last_commit} ago).")
                            if commit_repository(repo_path, repo_data['commit_message_template']):
                                repo_data['last_committed_at'] = datetime.now()
                        else:
                            logging.debug(f"Repository {repo_path} not due for commit yet. Next commit in {timedelta(seconds=remaining_seconds)}.")
                    else:
                        logging.debug(f"Auto-commit is disabled for {repo_path}.")


                    # --- Push Logic ---
                    if repo_data['auto_push']:
                        push_interval_seconds = repo_data['push_interval']
                        last_pushed = repo_data['last_pushed_at']
                        time_since_last_push = datetime.now() - last_pushed

                        if time_since_last_push.total_seconds() >= push_interval_seconds:
                            logging.info(f"Repository {repo_path} is due for a push (last pushed {time_since_last_push} ago).")
                            if push_repository(repo_path):
                                repo_data['last_pushed_at'] = datetime.now()
                        else:
                            logging.debug(f"Repository {repo_path} not due for push yet. Next push in {timedelta(seconds=remaining_seconds)}.")
                    else:
                        logging.debug(f"Auto-push is disabled for {repo_path}.")

            sleep_start = time.time()
            while running and (time.time() - sleep_start) < SERVICE_POLLING_INTERVAL_SECONDS:
                time.sleep(1)

        logging.info(f"GitBuddy periodic service finished at {datetime.now()}")
        sys.exit(0)

if __name__ == "__main__":
    main()
