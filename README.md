# VRChat Group Auto-Ban Tool

## Description

The VRChat Auto-Ban Tool is designed to assist VRChat group moderators and users in efficiently managing large-scale banning and blocking operations.

Its primary purposes are:

- Automating the process of banning multiple users from a specified VRChat group, particularly useful when dealing with spam accounts, malicious users, or cleaning up after a major incident.
- Automating the process of blocking multiple users on your VRChat account, providing an additional layer of moderation beyond group-specific actions.

Key purposes of this tool include:

- Streamlining the banning and blocking process.
  Reducing the time and effort required to manage large groups and user interactions.
  Providing a systematic approach to handle ban/block lists exported from VRCX or other sources.
  Ensuring consistent application of bans/blocks across a large number of user IDs.

## Features

- Asynchronous operation for improved performance
- Support for both JSON (VRCX group export) and plain text input files containing user IDs
- Session management to reduce authentication overhead
- Rate limiting to comply with API restrictions
- Progress tracking and logging
- Handling of various ban statuses (newly banned, already banned, already processed, failed)
- User-side blocking: Option to block users on your VRChat account, independently of or in addition to group bans.

## Prerequisites

- Python 3.12 or higher
- uv (Python project manager)

## Setup

This project uses uv for Python environment and dependency management. To set up the project:

1. Install uv if you haven't already: [uv Installation Guide](https://docs.astral.sh/uv/getting-started/installation/)
2. Clone the repository
3. Navigate to the project directory
4. Run `uv sync` to install dependencies

The project dependencies and settings are managed through the `pyproject.toml` file.

## File Structure

- `pyproject.toml`: Project configuration and dependencies
- `settings.toml`: Default configuration settings with example values
- `.secrets.toml`: Sensitive configuration settings (sensitive, gitignored)
- `crashers.json`: JSON file containing user data from VRCX group export (gitignored)
- `crasher_id_dump.txt`: Text file containing comma-separated user IDs to ban (gitignored)
- `processed_group_bans.json`: Tracks user IDs processed for group bans (gitignored).
- `processed_account_blocks.json`: Tracks user IDs processed for account-level blocks (gitignored).
- `vrchat_session.json`: JSON file storing session data for quicker authentication (sensitive, gitignored)
- `LICENSE`: MIT License file

## Configuration

1. The project comes with a `settings.toml` file in the `src/vrchat_autoban/` directory, which serves as a template:

```toml
username = "changeme"
password = "changemeaswell"
group_id = "grp_00000000-0000-0000-0000-000000000000" # Optional if only using user_side_blocking_enabled
rate_limit = 60
user_side_blocking_enabled = false # Set to true to enable blocking users on your account
```

This file is version-controlled and provides an example of the required configuration.

2. Create a `.secrets.toml` file in the `src/vrchat_autoban/` directory with your actual credentials:

```toml
username = "your_vrchat_username"
password = "your_vrchat_password"
group_id = "grp_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

Replace the values with your VRChat credentials and the ID of the group you want to manage.

**Note:** The `.secrets.toml` file contains sensitive information. Never commit this file to version control or share it publicly. Ensure `.secrets.toml` is added to your `.gitignore` file to prevent accidentally committing sensitive information.

3. (Optional) You can override any setting from `settings.toml` or `.secrets.toml` using environment variables. The application uses Dynaconf with the prefix "VRCHATBAN". For example:

```bash
export VRCHATBAN_RATE_LIMIT=30
export VRCHATBAN_USERNAME="my_vrchat_user"
export VRCHATBAN_PASSWORD="my_vrchat_password"
export VRCHATBAN_GROUP_ID="grp_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
export VRCHATBAN_USER_SIDE_BLOCKING_ENABLED=true
```

This would override the rate limit, username, password, and group ID, respectively.

4. Prepare your user data files:
   - `crashers.json`: A JSON file containing user data from VRCX group export
   - `crasher_id_dump.txt`: A plain text file with comma-separated user IDs to ban

Place both files in the `src/vrchat_autoban/` directory.

Example crasher_id_dump.txt content:

```text
usr_11111111-aaaa-2222-bbbb-333333333333,usr_44444444-cccc-5555-dddd-666666666666,usr_77777777-eeee-8888-ffff-999999999999
```

or

```text
usr_11111111-aaaa-2222-bbbb-333333333333,
usr_44444444-cccc-5555-dddd-666666666666,
usr_77777777-eeee-8888-ffff-999999999999
```

The application will load settings in the following order of precedence:

1. Environment variables with the "VRCHATBAN\_" prefix (highest priority)
2. `.secrets.toml`
3. `settings.toml` (lowest priority)

This allows for flexible configuration management while keeping sensitive information secure.

At least username and password must be set. You must also configure either a group_id for group banning or set user_side_blocking_enabled = true for user-side blocking (or both).

## Usage

Run the script:

```bash
uv run python src/vrchat_autoban/__init__.py
```

The script will:

1. Load the configuration and user data.
2. Authenticate with VRChat (using stored session if available).
3. Process each user ID:
   1. If a group_id is configured, attempt to ban them from the specified group.
   2. If user_side_blocking_enabled is true, attempt to block them on your VRChat account.
4. Apply rate limiting between API calls.
5. Track processed users for group bans to avoid redundant operations in subsequent runs for that action. User-side blocking checks if the user is already blocked via an API call.
6. Log the progress and results for both banning and blocking actions.

Ensure your `crashers.json` file is in the format exported by VRCX for group members. If you're unsure about this format, refer to VRCX documentation or export a sample file to see the structure.

## Key Components

- `Config`: Handles loading and storing of configuration data using dynaconf
- `ProcessedUserTracker`: Manages the list of processed user IDs
- `TextUserLoader` and `JSONUserLoader`: Load user IDs from text and JSON files respectively
- `SessionManager`: Manages VRChat authentication sessions
- `VRChatAuthenticator`: Handles the authentication process
- `VRChatGroupModerator`: Performs the actual banning operations
- `VRChatUserModerator`: Performs user-side blocking operations.
- `VRChatAPI`: Main class that coordinates authentication and moderation

## Logging

The script uses the `loguru` library for logging. Logs are written to both the console and a file named `vrchat_moderation.log`, which rotates daily.

## Error Handling

The script includes error handling for various scenarios, including:

- Configuration file not found or invalid
- Authentication failures
- API exceptions during ban operations
- Rate limiting

## Deduplicating User ID Lists (Utility Script)

To help manage and clean your input user ID lists, especially the `crasher_id_dump.txt` file, a utility script is provided to deduplicate entries, trim whitespace, and standardize the format.

**Script Location:** `src/vrchat_autoban/deduplicate_ids.py`

**Purpose:**
This script reads a comma-separated text file of user IDs (like the one used for `crasher_id_dump.txt`). It performs the following actions:

- Removes any leading or trailing whitespace from each user ID.
- Eliminates duplicate user IDs.
- Handles IDs spread across multiple lines as long as they are comma-separated.
- Filters out any empty entries that might result from extra commas or blank lines.
- Sorts the unique user IDs alphabetically.
- Overwrites the original file with the cleaned, sorted, and comma-separated list of unique user IDs.

This is useful for ensuring your input list is clean and efficient before running the main auto-ban tool.

**Usage:**
To run the deduplication script, navigate to the project's root directory and use the following command:

```bash
uv run python src/vrchat_autoban/deduplicate_ids.py
```

## Caution

- Use this tool responsibly and in accordance with VRChat's Terms of Service and Community Guidelines.
- Banning or blocking a large number of users in quick succession might be flagged as suspicious activity by VRChat. The built-in rate limiter helps, but discretion is advised.
- Always double-check the list of users before initiating any moderation process.
- Group Bans: Ensure you have the necessary permissions (e.g., moderator role with ban privileges) to manage the specified group if performing group bans.
- User-Side Blocks: Blocking a user is an action tied directly to your VRChat account and affects your interaction with that user across all of VRChat. This action is persistent until you manually unblock them.
- Keep your `.secrets.toml` and `vrchat_session.json` files secure. These contain sensitive data that could compromise your VRChat account if exposed.

## Contributing

Contributions to improve the tool are welcome. Please follow these steps:

1. First, create an issue describing the improvement or feature you'd like to add.
2. Once the issue is approved:
   a. Fork the repository
   b. Create a new branch for your feature
   c. Ensure that you don't commit any sensitive information to the repository
   d. Commit your changes
   e. Push to the branch
   f. Create a new Pull Request, referencing the original issue

## Disclaimer

This tool is not officially affiliated with or endorsed by VRChat. Use at your own risk.
