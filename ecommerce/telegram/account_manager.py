import random
import re
import traceback
from pathlib import Path

from pyrogram import Client, errors
from pyrogram.types import TermsOfService

from ecommerce.product.models import AccountSession
from fixtures.names import fake_names
from utils.load_env import config as CONFIG
import sqlite3

from typing import NewType, Tuple

Status = NewType("SessionStatus", str)
PhoneNumber = NewType("PhoneNumber", str)
LoginCode = NewType("LoginCode", str)


BASE_DIR = Path(__file__).resolve().parent.parent


class ProxyManager:
    @staticmethod
    async def get_proxy(data: list = []):
        """Return a proxy configuration based on provided data or CONFIG."""
        proxy = {"scheme": "socks5"}
        if len(data) > 3:
            host, port, username, passwd = data
            proxy.update(
                {
                    "hostname": host,
                    "port": int(port),
                    "username": username,
                    "password": passwd,
                }
            )
        elif len(data) == 2:
            host, port = data
            proxy.update(
                {
                    "hostname": host,
                    "port": int(port),
                }
            )
        else:
            if local_proxy := CONFIG.PROXY_SOCKS:
                host, port = local_proxy.split(":")
                proxy.update(
                    {
                        "hostname": host,
                        "port": int(port),
                    }
                )
        return proxy


class SessionDetector:
    @staticmethod
    def detect_session_file_type(db_path):
        """Detect session type based on the session file content."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        query = "SELECT server_address FROM sessions"
        cursor.execute(query)
        results = cursor.fetchone()
        conn.close()
        return "telethon" if results else "pyrogram"

    @staticmethod
    def detect_session_string_type(session_string):
        """Detect session type based on the session string length."""
        return "telethon" if len(session_string) < 362 else "pyrogram"


class SessionStatus:
    @staticmethod
    async def check_telethon_session_status(session_obj):
        """Check the status of a Telethon session."""
        account = TelegramClient(
            StringSession(session_obj.session_string),
            session_obj.api_id,
            session_obj.api_hash,
        )
        _proxy = session_obj.proxy.split(":")
        _proxy = _proxy[0], int(_proxy[1])
        proxy = ("socks5", *_proxy)
        account.set_proxy(proxy)
        await account.connect()
        me = await account.get_entity("me")
        session_obj.status = AccountSession.StatusChoices.active
        await session_obj.asave()
        await account.disconnect()
        return session_obj.status.value, me.phone

    @staticmethod
    async def check_pyrogram_session_status(session_obj):
        """Check the status of a Pyrogram session."""
        _proxy = session_obj.proxy.split(":")
        proxy = await ProxyManager.get_proxy(data=_proxy)
        account = Client(
            name="",
            api_id=session_obj.api_id,
            api_hash=session_obj.api_hash,
            proxy=proxy,
            session_string=session_obj.session_string,
            in_memory=True,
            no_updates=True,
        )
        await account.connect()
        me = await account.get_me()
        session_obj.status = AccountSession.StatusChoices.active
        await session_obj.asave()
        await account.disconnect()
        return session_obj.status.value, me.phone_number


class SessionStringExtractor:
    @staticmethod
    async def extract_telethon_session_string(session_file_path: str):
        """Extract session string from a Telethon session file."""
        account = TelegramClient(session_file_path, int(CONFIG.API_ID), CONFIG.API_HASH)
        session_string = StringSession.save(account.session)
        _proxy = await ProxyManager.get_proxy()
        proxy = ("socks5", *_proxy.values())
        account.set_proxy(proxy)
        await account.connect()
        me = await account.get_entity("me")
        return session_string, me.phone

    @staticmethod
    async def extract_pyrogram_session_string(session_file_path):
        """Extract session string from a Pyrogram session file."""
        proxy = await ProxyManager.get_proxy()
        account = Client(
            name=session_file_path,
            api_id=int(CONFIG.API_ID),
            api_hash=CONFIG.API_HASH,
            proxy=proxy,
        )
        await account.connect()
        session_string = await account.export_session_string()
        phone = (await account.get_me()).phone_number
        await account.disconnect()
        return session_string, phone

class LoginCodeRetriever:
    @staticmethod
    async def retrieve_telethon_login_code(session_obj):
        """Retrieve login code from Telethon session."""
        pattern = r"(\d{1,5})"
        account = TelegramClient(
            StringSession(session_obj.session_string),
            session_obj.api_id,
            session_obj.api_hash,
        )
        _proxy = session_obj.proxy.split(":")
        _proxy = _proxy[0], int(_proxy[1])
        proxy = ("socks5", *_proxy)
        account.set_proxy(proxy)
        await account.connect()
        async for msg in account.iter_messages(777000, limit=1):
            code = re.findall(pattern, msg.text.lower())
        await account.disconnect()
        return code

    @staticmethod
    async def retrieve_pyrogram_login_code(session_obj):
        """Retrieve login code from Pyrogram session."""
        pattern = r"(\d{1,5})"
        _proxy = session_obj.proxy.split(":")
        proxy = await ProxyManager.get_proxy(data=_proxy)
        account = Client(
            name="",
            api_id=session_obj.api_id,
            api_hash=session_obj.api_hash,
            proxy=proxy,
            session_string=session_obj.session_string,
        )
        await account.connect()
        async for msg in account.get_chat_history(777000, limit=1):
            code = re.findall(pattern, msg.text.lower())
        await account.disconnect()
        return code


class TMAccountManager:
    def __init__(self, session_id=0) -> None:
        self.session_id = session_id

    async def check_session_status(self) -> Tuple[Status, PhoneNumber] | Tuple[bool, bool]:
        """Check the status of a session."""
        session_obj = await AccountSession.objects.aget(id=self.session_id)
        session_type = SessionDetector.detect_session_string_type(
            session_obj.session_string
        )
        try:
            if session_type == "telethon":
                status_value, phone_number = (
                    await SessionStatus.check_telethon_session_status(
                        session_obj
                    )
                )
            else:
                status_value, phone_number = (
                    await SessionStatus.check_pyrogram_session_status(
                        session_obj
                    )
                )
            return status_value, phone_number
        except Exception:
            error_msg = traceback.format_exc().strip()
            print(error_msg)
            session_obj.status = AccountSession.StatusChoices.disable
            await session_obj.asave()
            return False, False

    async def extract_session_string(self, session_file_path: str):
        """Extract the session string from a session file."""
        session_type = SessionDetector.detect_session_file_type(session_file_path)
        try:
            if session_type == "telethon":
                return await SessionStringExtractor.extract_telethon_session_string(
                    session_file_path
                )
            else:
                return await SessionStringExtractor.extract_pyrogram_session_string(
                    session_file_path
                )
        except Exception as error:
            print("[Error] Export session string: ", error)
            return False, False

    async def retrieve_login_code(self, phone) -> LoginCode:
        """Retrieve login code for a given phone number."""
        session_obj = await AccountSession.objects.aget(phone=phone)
        session_type = SessionDetector.detect_session_string_type(
            session_obj.session_string
        )
        try:
            if session_type == "telethon":
                code = await LoginCodeRetriever.retrieve_telethon_login_code(
                    session_obj
                )
            else:
                code = await LoginCodeRetriever.retrieve_pyrogram_login_code(
                    session_obj
                )
            if code:
                return code[0]
            return False, None, None
        except Exception as error:
            print("[Error] Retrieve login code: ", error)
            return False


class SignInSignUpSessionManager:
    def __init__(self, session_id):
        self.session_id = session_id

    async def _get_session_obj(self):
        return await AccountSession.objects.aget(id=self.session_id)

    async def _create_account_client(self, session_obj):
        _proxy = session_obj.proxy.split(":")
        proxy = await ProxyManager.get_proxy(_proxy)
        return Client(
            name="",
            phone_number=session_obj.phone,
            api_id=session_obj.api_id,
            api_hash=session_obj.api_hash,
            app_version=session_obj.app_version,
            device_model=session_obj.device_model,
            system_version=session_obj.system_version,
            proxy=proxy,
            in_memory=True,
            no_updates=True,
        )

    async def send_login_code(self):
        session_obj = await self._get_session_obj()
        account = await self._create_account_client(session_obj)
        try:
            await account.connect()
            result = await account.send_code(session_obj.phone)
            return True, account, result
        except errors.PhoneNumberInvalid:
            return False, "Phone number invalid", errors.PhoneNumberInvalid
        except Exception as error:
            print(f"Unexpected error in send_login_code: {error}")
            return False, "Unexpected error, check server log", False

    async def sign_in_account(self, account: Client, phone_code_hash, login_code):
        session_obj = await self._get_session_obj()
        try:
            user = await account.sign_in(
                phone_number=session_obj.phone,
                phone_code_hash=phone_code_hash,
                phone_code=login_code,
            )
            if user.id:
                await self._update_session_obj(session_obj, account)
                return True, None, None
        except errors.SessionPasswordNeeded:
            hint = await account.get_password_hint()
            return False, hint, errors.SessionPasswordNeeded
        except errors.PhoneCodeInvalid:
            return False, "Login code invalid", errors.PhoneCodeInvalid
        except errors.PhoneCodeExpired:
            return False, "Login code expired", errors.PhoneCodeExpired
        except errors.PhonePasswordFlood:
            return False, "Password flood", errors.PhonePasswordFlood
        except errors.FloodWait as e:
            return False, f"FloodWait, try later: {e.x}", errors.FloodWait
        except Exception as err:
            print(f"Unexpected error in sign_in_account: {err}")
            return False, "Unexpected error, check server log", False

    async def sign_up_account(self, account: Client, phone_code_hash):
        session_obj = await self._get_session_obj()
        try:
            signed_up = await account.sign_up(
                phone_number=session_obj.phone,
                phone_code_hash=phone_code_hash,
                first_name=random.choice(fake_names),
            )
            if isinstance(signed_up, TermsOfService):
                is_accepted = await account.accept_terms_of_service(signed_up.id)
                if is_accepted:
                    # TODO: Enable cloud password
                    pass

                await self._update_session_obj(session_obj, account)
                return True, None, None
        except errors.PhoneCodeInvalid:
            return False, "Login code invalid", errors.PhoneCodeInvalid
        except errors.PhoneCodeExpired:
            return False, "Login code expired", errors.PhoneCodeExpired
        except errors.FloodWait as e:
            return False, f"FloodWait, try later: {e.x}", errors.FloodWait
        except Exception as err:
            print(f"Unexpected error in sign_up_account: {err}")
            return False, "Unexpected error, check server log", False

    async def confirm_password(self, account: Client, password):
        try:
            await account.check_password(password)
            session_obj = await self._get_session_obj()
            await self._update_session_obj(session_obj, account, password)
            return True, None, None
        except errors.PasswordHashInvalid:
            error = "❌ Invalid Password"
            hint = await account.get_password_hint()
            return False, str(hint) + error, errors.PasswordHashInvalid
        except Exception as err:
            print(f"Unexpected error in confirm_password: {err}")
            return False, "Unexpected error, check server log", False

    async def _update_session_obj(self, session_obj, account, password=None):
        session_string = await account.export_session_string()
        session_obj.session_string = session_string
        session_obj.status = AccountSession.StatusChoices.active
        if password:
            session_obj.password = password
        await session_obj.asave()

