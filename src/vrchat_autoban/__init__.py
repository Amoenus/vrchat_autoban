import os
import time
import json
from typing import List
from abc import ABC, abstractmethod
import vrchatapi
from vrchatapi.api import authentication_api, groups_api
from vrchatapi.exceptions import UnauthorizedException
from vrchatapi.models.two_factor_auth_code import TwoFactorAuthCode
from vrchatapi.models.two_factor_email_code import TwoFactorEmailCode
from vrchatapi.models.ban_group_member_request import BanGroupMemberRequest

class User:
    def __init__(self, id: str, display_name: str):
        self.id = id
        self.display_name = display_name

class UserLoader(ABC):
    @abstractmethod
    def load_users(self) -> List[User]:
        pass

class JSONUserLoader:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def load_users(self) -> List[User]:
        try:
            with open(self.file_path, 'r') as file:
                data = json.load(file)
        except FileNotFoundError:
            print(f"Error: User file '{self.file_path}' not found.")
            print(f"Current working directory: {os.getcwd()}")
            print("Please ensure the user file exists in the correct location.")
            raise SystemExit(1)
        except json.JSONDecodeError:
            print(f"Error: Unable to parse '{self.file_path}'. Please ensure it's valid JSON.")
            raise SystemExit(1)

        users = []
        for member in data:
            user_data = member.get('user', {})
            user_id = user_data.get('id')
            display_name = user_data.get('displayName')
            if user_id and display_name:
                users.append(User(user_id, display_name))
        
        return users

class TextUserLoader:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def load_users(self) -> List[User]:
        try:
            with open(self.file_path, 'r') as file:
                content = file.read().strip()
                user_ids = content.split(',')
        except FileNotFoundError:
            print(f"Error: User file '{self.file_path}' not found.")
            print(f"Current working directory: {os.getcwd()}")
            print("Please ensure the user file exists in the correct location.")
            raise SystemExit(1)

        return [User(id=user_id, display_name="DCN Dump User") for user_id in user_ids if user_id]

class VRChatAuthenticator:
    def __init__(self, api_client: vrchatapi.ApiClient):
        self.auth_api = authentication_api.AuthenticationApi(api_client)

    def authenticate(self):
        try:
            current_user = self.auth_api.get_current_user()
            print(f"Logged in as: {current_user.display_name}")
        except UnauthorizedException as e:
            if e.status == 200:
                if "Email 2 Factor Authentication" in e.reason:
                    self._handle_email_2fa()
                elif "2 Factor Authentication" in e.reason:
                    self._handle_2fa()
                current_user = self.auth_api.get_current_user()
            else:
                raise
        except vrchatapi.ApiException as e:
            print(f"Exception when calling API: {e}")
            raise

    def _handle_email_2fa(self):
        code = input("Email 2FA Code: ")
        self.auth_api.verify2_fa_email_code(two_factor_email_code=TwoFactorEmailCode(code))

    def _handle_2fa(self):
        code = input("2FA Code: ")
        self.auth_api.verify2_fa(two_factor_auth_code=TwoFactorAuthCode(code))

class GroupBanner:
    def __init__(self, api_client: vrchatapi.ApiClient):
        self.groups_api = groups_api.GroupsApi(api_client)

    def ban_user(self, group_id: str, user_id: str) -> bool:
        try:
            ban_request = BanGroupMemberRequest(user_id=user_id)
            result = self.groups_api.ban_group_member(group_id, ban_group_member_request=ban_request)
            print(f"Ban result: {result}")  # This will print the GroupMember object returned
            return True
        except vrchatapi.ApiException as e:
            print(f"Exception when calling GroupsApi->ban_group_member: {e}")
            return False

class VRChatAPI:
    def __init__(self, username: str, password: str):
        self.configuration = vrchatapi.Configuration(
            username=username,
            password=password,
        )
        self.api_client = vrchatapi.ApiClient(self.configuration)
        self.api_client.user_agent = "VRChatGroupBannerScript/1.0 (https://github.com/Amoenus/vrchat_autoban)"
        self.authenticator = VRChatAuthenticator(self.api_client)
        self.banner = GroupBanner(self.api_client)

    def authenticate(self):
        self.authenticator.authenticate()

    def ban_user_from_group(self, group_id: str, user_id: str) -> bool:
        return self.banner.ban_user(group_id, user_id)


class Config:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.data = self.load_config()

    def load_config(self):
        try:
            with open(self.file_path, 'r') as config_file:
                return json.load(config_file)
        except FileNotFoundError:
            print(f"Error: Config file '{self.file_path}' not found.")
            print(f"Current working directory: {os.getcwd()}")
            print("Please ensure the config file exists in the correct location.")
            raise SystemExit(1)
        except json.JSONDecodeError:
            print(f"Error: Unable to parse '{self.file_path}'. Please ensure it's valid JSON.")
            raise SystemExit(1)

    def get(self, key: str):
        return self.data.get(key)

def main():
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Construct the full paths to the config and users files
    CONFIG_FILE = os.path.join(script_dir, 'config.json')
    USERS_FILE = os.path.join(script_dir, 'crashers.json')
    TEXT_USERS_FILE = os.path.join(script_dir, 'cracher_id_dump_from_DCN.txt')

    API_RATE_LIMIT = 60  # seconds

    config = Config(CONFIG_FILE)
    api = VRChatAPI(config.get('username'), config.get('password'))
    api.authenticate()

   # json_user_loader = JSONUserLoader(USERS_FILE)
    text_user_loader = TextUserLoader(TEXT_USERS_FILE)
    
    users_to_ban = text_user_loader.load_users()

    group_id = config.get('group_id')

    for user in users_to_ban:
        if api.ban_user_from_group(group_id, user.id):
            print(f"Successfully banned user {user.display_name} (ID: {user.id})")
        else:
            print(f"Failed to ban user {user.display_name} (ID: {user.id})")
        time.sleep(API_RATE_LIMIT)

if __name__ == "__main__":
    main()