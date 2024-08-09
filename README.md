# VRChat Group Auto-Ban Tool

## Description

This tool is designed to automatically ban users from a specified VRChat group based on a list of user IDs. It can process user data from both JSON files (exported from VRCX) and plain text files containing comma-separated user IDs.

## Prerequisites

- Python 3.7 or higher
- `vrchatapi` library

## Configuration

1. Create a `config.json` file in the project root with the following structure:
```json
{
  "username": "your_vrchat_username",
  "password": "your_vrchat_password",
  "group_id": "grp_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

2. Replace the values with your VRChat credentials and the ID of the group you want to manage.

Prepare your user data files:

`crashers.json`: A JSON file exported from VRCX containing user data.
`cracher_id_dump_from_DCN.txt`: A plain text file with comma-separated user IDs.

## Usage
Run the script:
```terminal
python src/vrchat_autoban/__init__.py
```

The script will:

- Authenticate with VRChat.
- Load user data from both the JSON and/or text files.
- Attempt to ban each user from the specified group.
- Wait for 60 seconds between each ban action to comply with API rate limits.

## Caution

Use this tool responsibly and in accordance with VRChat's terms of service.
Banning a large number of users in quick succession might be flagged as suspicious activity.
Always double-check the list of users before initiating the ban process.