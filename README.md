# VRChat Group Auto-Ban Tool

## Description

This tool is an asynchronous Python script designed to automatically ban users from a specified VRChat group based on a list of user IDs. It provides features such as rate limiting, session management, and tracking of processed users to ensure efficient and responsible use of the VRChat API.

## Features

- Asynchronous operation for improved performance
- Support for both JSON and plain text input files containing user IDs
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
- `config.json`: Configuration file containing VRChat credentials and group ID (sensitive, gitignored)
- `crasher_id_dump.txt`: Text file containing comma-separated user IDs to ban (gitignored)
- `processed_users.json`: JSON file tracking processed user IDs (gitignored)
- `vrchat_session.json`: JSON file storing session data for quicker authentication (sensitive, gitignored)
- `LICENSE`: MIT License file

## Configuration

1. Create a `config.json` file in the `src/vrchat_autoban/` directory with the following structure:

```json
{
  "username": "your_vrchat_username",
  "password": "your_vrchat_password",
  "group_id": "grp_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "rate_limit": 60
}
```

Replace the values with your VRChat credentials, the ID of the group you want to manage, and the desired rate limit in seconds.

2. Prepare your user data file:
   - `crasher_id_dump.txt`: A plain text file with comma-separated user IDs to ban, placed in the `src/vrchat_autoban/` directory

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

## Classes and Components

- `Config`: Handles loading and storing of configuration data
- `ProcessedUserTracker`: Manages the list of processed user IDs
- `TextUserLoader`: Loads user IDs from a text file
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

## Contributing

Contributions to improve the tool are welcome. Please follow these steps:

1. First, create an issue describing the improvement or feature you'd like to add. This allows for discussion about the proposed changes and ensures that the improvement aligns with the project's goals.
2. Once the issue is approved:
   a. Fork the repository
   b. Create a new branch for your feature
   c. *Ensure that you don't commit any sensitive information to the repository*
   d. Commit your changes
   e. Push to the branch
   f. Create a new Pull Request, referencing the original issue

By creating an issue first, we can better track proposed improvements and discuss implementation details before work begins.

## Disclaimer

This tool is not officially affiliated with or endorsed by VRChat. Use at your own risk.