# git_puller_service.py

import json
import subprocess
import os
import logging
import time
import signal
import sys
from datetime import datetime, timedelta

# Define the configuration file path
CONFIG_DIR = os.path.expanduser("~/.config/git-puller")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
LOG_FILE = os.path.join(CONFIG_DIR, "git_puller.log")

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
    """
    global running
    logging.info(f"Received signal {signum}. Shutting down gracefully...")
    running = False

# Register the signal handler for SIGTERM
signal.signal(signal.SIGTERM, signal_handler)

def load_repositories():
    """
    Loads the list of Git repository configurations from the configuration file.
    Each entry is expected to be a dictionary with 'path' and other optional keys.
    Initializes 'last_pulled_at' and 'last_pushed_at' for internal tracking.
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
                
                # Default values for new settings
                pull_interval = entry.get('pull_interval', 300) # Default 5 minutes
                auto_commit = entry.get('auto_commit', False)
                commit_message_template = entry.get('commit_message_template', "Auto-commit from Git Puller: {timestamp}")
                auto_push = entry.get('auto_push', False)
                push_interval = entry.get('push_interval', 3600) # Default 1 hour

                # Validate intervals
                if not isinstance(pull_interval, (int, float)) or pull_interval <= 0:
                    logging.warning(f"Invalid pull_interval for {repo_path}. Using default 300 seconds.")
                    pull_interval = 300
                if not isinstance(push_interval, (int, float)) or push_interval <= 0:
                    logging.warning(f"Invalid push_interval for {repo_path}. Using default 3600 seconds.")
                    push_interval = 3600

                repositories.append({
                    'path': repo_path,
                    'pull_interval': pull_interval,
                    'last_pulled_at': datetime.min, # Initialize to a very old time to ensure first pull
                    'auto_commit': auto_commit,
                    'commit_message_template': commit_message_template,
                    'auto_push': auto_push,
                    'push_interval': push_interval,
                    'last_pushed_at': datetime.min # Initialize to a very old time for first push
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
    else:
        logging.error(f"Failed to pull {repo_path}: {message}")
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
        return False
    
    if not output_status.strip():
        logging.info(f"No changes to commit in {repo_path}. Skipping commit.")
        return False

    logging.info(f"Staging changes in {repo_path}...")
    success_add, message_add = run_git_command(repo_path, ['add', '.'])
    if not success_add:
        logging.error(f"Failed to stage changes in {repo_path}: {message_add}")
        return False

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    commit_message = commit_message_template.format(timestamp=timestamp)
    logging.info(f"Attempting to commit {repo_path} with message: '{commit_message}'")
    success_commit, message_commit = run_git_command(repo_path, ['commit', '-m', commit_message])
    if success_commit:
        logging.info(f"Successfully committed {repo_path}")
    else:
        logging.error(f"Failed to commit {repo_path}: {message_commit}")
    return success_commit

def push_repository(repo_path):
    """Attempts to perform a 'git push'."""
    logging.info(f"Attempting to push repository: {repo_path}")
    success, message = run_git_command(repo_path, ['push'])
    if success:
        logging.info(f"Successfully pushed {repo_path}")
    else:
        logging.error(f"Failed to push {repo_path}: {message}")
    return success

def main():
    """
    Main function to execute the Git pulling, committing, and pushing process in a loop.
    """
    logging.info(f"Git Puller service started at {datetime.now()}")

    # Interval at which the service re-checks all repositories for pending actions
    SERVICE_POLLING_INTERVAL_SECONDS = 30 # Check every 30 seconds

    # Load repositories initially
    repositories = load_repositories()

    while running:
        # Reload repositories periodically to pick up changes from the GUI
        # This also ensures we get the latest 'pull_interval', 'auto_commit', 'auto_push', 'push_interval' settings.
        current_repositories_config = load_repositories()

        # Merge new config with existing 'last_pulled_at' and 'last_pushed_at' timestamps
        updated_repositories = []
        for new_repo_entry in current_repositories_config:
            found = False
            for old_repo_entry in repositories:
                if new_repo_entry['path'] == old_repo_entry['path']:
                    # Keep old timestamps, but update other settings from new config
                    new_repo_entry['last_pulled_at'] = old_repo_entry['last_pulled_at']
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
                if not running: # Check running flag before starting next action
                    break

                repo_path = repo_data['path']
                
                # --- Pull Logic ---
                pull_interval = repo_data['pull_interval']
                last_pulled = repo_data['last_pulled_at']
                time_since_last_pull = datetime.now() - last_pulled
                
                if time_since_last_pull.total_seconds() >= pull_interval:
                    logging.info(f"Repository {repo_path} is due for a pull (last pulled {time_since_last_pull} ago).")
                    if pull_repository(repo_path):
                        repo_data['last_pulled_at'] = datetime.now() # Update timestamp on successful pull
                else:
                    logging.debug(f"Repository {repo_path} not due for pull yet. Next pull in {timedelta(seconds=pull_interval - time_since_last_pull.total_seconds())}.")

                # --- Commit Logic ---
                if repo_data['auto_commit']:
                    # Commit immediately after pull if changes exist, or based on a separate trigger
                    # For simplicity, we'll try to commit after every pull check if auto_commit is true
                    # A more sophisticated approach might check for uncommitted changes first.
                    if commit_repository(repo_path, repo_data['commit_message_template']):
                        # No specific 'last_committed_at' needed if commit is tied to pull/push
                        pass
                else:
                    logging.debug(f"Auto-commit is disabled for {repo_path}.")

                # --- Push Logic ---
                if repo_data['auto_push']:
                    push_interval = repo_data['push_interval']
                    last_pushed = repo_data['last_pushed_at']
                    time_since_last_push = datetime.now() - last_pushed

                    if time_since_last_push.total_seconds() >= push_interval:
                        logging.info(f"Repository {repo_path} is due for a push (last pushed {time_since_last_push} ago).")
                        if push_repository(repo_path):
                            repo_data['last_pushed_at'] = datetime.now() # Update timestamp on successful push
                    else:
                        logging.debug(f"Repository {repo_path} not due for push yet. Next push in {timedelta(seconds=push_interval - time_since_last_push.total_seconds())}.")
                else:
                    logging.debug(f"Auto-push is disabled for {repo_path}.")

        # Sleep for the defined service polling interval, checking the running flag periodically
        sleep_start = time.time()
        while running and (time.time() - sleep_start) < SERVICE_POLLING_INTERVAL_SECONDS:
            time.sleep(1) # Sleep in 1-second increments

    logging.info(f"Git Puller service finished at {datetime.now()}")
    sys.exit(0) # Explicitly exit with success code

if __name__ == "__main__":
    main()