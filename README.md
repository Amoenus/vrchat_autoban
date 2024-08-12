# VRChat Group Auto-Ban Tool

# VRChat Group Auto-Ban Tool

## Description

The VRChat Group Auto-Ban Tool is designed to assist VRChat group moderators in efficiently managing large-scale banning operations. Its primary purpose is to automate the process of banning multiple users from a specified VRChat group, particularly useful when dealing with spam accounts, malicious users, or cleaning up after a major incident.

Key purposes of this tool include:
- Streamlining the banning process for group moderators
- Reducing the time and effort required to manage large groups
- Providing a systematic approach to handle ban lists exported from VRCX or other sources
- Ensuring consistent application of bans across a large number of user IDs

## Features

- Asynchronous operation for improved performance
- Support for both JSON (VRCX group export) and plain text input files containing user IDs
- Session management to reduce authentication overhead
- Rate limiting to comply with API restrictions
- Progress tracking and logging
- Handling of various ban statuses (newly banned, already banned, already processed, failed)

## Prerequisites

- Python 3.12 or higher
- Rye (Python project manager)

## Setup

This project uses Rye for Python environment and dependency management. To set up the project:

1. Install Rye if you haven't already: [Rye Installation Guide](https://rye.astral.sh/guide/installation/)
2. Clone the repository
3. Navigate to the project directory
4. Run `rye sync` to install dependencies

The project dependencies and settings are managed through the `pyproject.toml` file.

## File Structure

- `pyproject.toml`: Project configuration and dependencies
- `settings.toml`: Default configuration settings with example values
- `.secrets.toml`: Sensitive configuration settings (sensitive, gitignored)
- `crashers.json`: JSON file containing user data from VRCX group export (gitignored)
- `crasher_id_dump.txt`: Text file containing comma-separated user IDs to ban (gitignored)
- `processed_users.json`: JSON file tracking processed user IDs (gitignored)
- `vrchat_session.json`: JSON file storing session data for quicker authentication (sensitive, gitignored)
- `LICENSE`: MIT License file

## Configuration

1. The project comes with a `settings.toml` file in the `src/vrchat_autoban/` directory, which serves as a template:

```toml
username = "changeme"
password = "changemeaswell"
group_id = "grp_00000000-0000-0000-0000-000000000000"
rate_limit = 60
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
```

This would override the rate limit, username, password, and group ID, respectively.

4. Prepare your user data files:
   - `crashers.json`: A JSON file containing user data from VRCX group export
   - `crasher_id_dump.txt`: A plain text file with comma-separated user IDs to ban

Place both files in the `src/vrchat_autoban/` directory.

The application will load settings in the following order of precedence:
1. Environment variables with the "VRCHATBAN_" prefix (highest priority)
2. `.secrets.toml`
3. `settings.toml` (lowest priority)

This allows for flexible configuration management while keeping sensitive information secure.

## Usage

Run the script:

```bash
rye run python src/vrchat_autoban/__init__.py
```

The script will:
1. Load the configuration and user data
2. Authenticate with VRChat (using stored session if available)
3. Process each user ID, attempting to ban them from the specified group
4. Apply rate limiting between API calls
5. Track processed users to avoid redundant operations
6. Log the progress and results

Ensure your `crashers.json` file is in the format exported by VRCX for group members. If you're unsure about this format, refer to VRCX documentation or export a sample file to see the structure.

## Key Components

- `Config`: Handles loading and storing of configuration data using dynaconf
- `ProcessedUserTracker`: Manages the list of processed user IDs
- `TextUserLoader` and `JSONUserLoader`: Load user IDs from text and JSON files respectively
- `SessionManager`: Manages VRChat authentication sessions
- `VRChatAuthenticator`: Handles the authentication process
- `VRChatGroupModerator`: Performs the actual banning operations
- `VRChatAPI`: Main class that coordinates authentication and moderation

## Logging

The script uses the `loguru` library for logging. Logs are written to both the console and a file named `vrchat_moderation.log`, which rotates daily.

## Error Handling

The script includes error handling for various scenarios, including:
- Configuration file not found or invalid
- Authentication failures
- API exceptions during ban operations
- Rate limiting

## Caution

- Use this tool responsibly and in accordance with VRChat's terms of service.
- Banning a large number of users in quick succession might be flagged as suspicious activity.
- Always double-check the list of users before initiating the ban process.
- Ensure you have the necessary permissions to manage the specified group.
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