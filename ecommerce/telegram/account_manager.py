import random
import re

from pyrogram import Client, errors
from pyrogram.types import TermsOfService

from ecommerce.product.models import AccountSession
from fixtures.names import fake_names
from utils.load_env import config as CONFIG


class TMAccountManager:
    def __init__(self, session_id=0) -> None:
        self.session_id = session_id

    async def get_proxy(self, data):
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
        else:
            host, port = data
            proxy.update(
                {
                    "hostname": host,
                    "port": int(port),
                }
            )
        return proxy

    async def check_session_status(self):
        session_obj = await AccountSession.objects.aget(id=self.session_id)
        _proxy = session_obj.proxy.split(":")
        proxy = await self.get_proxy(_proxy)
        account = Client(
            name="",
            api_id=session_obj.api_id,
            api_hash=session_obj.api_hash,
            proxy=proxy,
            session_string=session_obj.session_string,
            in_memory=True,
            no_updates=True,
        )
        try:
            if await account.connect():
                await account.get_me()
                session_obj.status = AccountSession.StatusChoices.active
                await session_obj.asave()
                await account.disconnect()
                return True, session_obj.status.value, True
        except Exception as err:
            print(err)

        session_obj.status = AccountSession.StatusChoices.disable
        await session_obj.asave()
        return False, session_obj.status.value, None

    async def extract_session_string(self):
        proxy = None
        if CONFIG.PROXY_SOCKS:
            proxy = {"scheme": "socks5", "hostname": "127.0.0.1", "port": 1359}

        account = Client(
            name="/tmp/session_file",
            api_id=901903,
            api_hash="ef8acfacf0d45e16bba0b0568251ef2b",
            proxy=proxy,
        )
        try:
            await account.connect()
            session_string = await account.export_session_string()
            await account.disconnect()
            return session_string
        except Exception as error:
            print("[Error] Export session string: ", error)
            return False, False

    async def send_login_code(self):
        session_obj = await AccountSession.objects.aget(id=self.session_id)
        _proxy = session_obj.proxy.split(":")
        proxy = await self.get_proxy(_proxy)
        account = Client(
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
        try:
            await account.connect()
            result = await account.send_code(session_obj.phone)
            return True, account, result

        except errors.PhoneNumberInvalid:
            return False, "Phone number invalid", errors.PhoneNumberInvalid

        except Exception as error:
            return False, "Unexpected error, check server log", False

    async def sign_in_account(self, account: Client, phone_code_hash, login_code):
        session_obj = await AccountSession.objects.aget(id=self.session_id)
        try:
            user = await account.sign_in(
                phone_number=session_obj.phone,
                phone_code_hash=phone_code_hash,
                phone_code=login_code,
            )
            if user.id:
                session_string = await account.export_session_string()
                session_obj.session_string = session_string
                session_obj.status = AccountSession.StatusChoices.active
                await session_obj.asave()
                return True, None, None
        except errors.SessionPasswordNeeded:
            hint = await account.get_password_hint()
            return False, hint, errors.SessionPasswordNeeded

        except errors.PhoneCodeInvalid:
            return False, "Login code invalid", errors.PhoneCodeInvalid

        except errors.PhoneCodeExpired:
            return False, "Login code expired", errors.PhoneCodeExpired

        except errors.PhonePasswordFlood:
            return False, "Password foold", errors.PhonePasswordFlood

        except errors.FloodWait:
            return False, "FoolWait tray later", errors.FloodWait

        except Exception as err:
            print(err)
            return False, "Unexpected error, check server log", False

        return False, "Unexpected error, check server log", False

    async def sign_up_account(self, account: Client, phone_code_hash):
        session_obj = await AccountSession.objects.aget(id=self.session_id)
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
                    ...

                session_string = await account.export_session_string()
                session_obj.session_string = session_string
                session_obj.status = AccountSession.StatusChoices.active
                await session_obj.asave()
                return True, None, None
        except errors.PhoneCodeInvalid:
            return False, "Login code invalid", errors.PhoneCodeInvalid

        except errors.PhoneCodeExpired:
            return False, "Login code expired", errors.PhoneCodeExpired

        except errors.FloodWait:
            return False, "FoolWait tray later", errors.FloodWait

        except Exception as err:
            print(err)
            return False, "Unexpected error, check server log", False

    async def confirm_password(self, account: Client, password):
        try:
            await account.check_password(password)
            session_obj = await AccountSession.objects.aget(id=self.session_id)
            session_string = await account.export_session_string()
            session_obj.session_string = session_string
            session_obj.password = password
            session_obj.status = AccountSession.StatusChoices.active
            await session_obj.asave()
            return True, None, None
        except errors.PasswordHashInvalid:
            error = "❌ Invalid Password"
            hint = await account.get_password_hint()
            return False, hint + error, errors.PasswordHashInvalid

        except Exception as err:
            print(err)
            return False, "Unexpected error, check server log", False

    async def retrive_login_code(self, phone):
        session_obj = await AccountSession.objects.aget(phone=phone)
        _proxy = session_obj.proxy.split(":")
        proxy = await self.get_proxy(_proxy)
        account = Client(
            name="",
            api_id=session_obj.api_id,
            api_hash=session_obj.api_hash,
            proxy=proxy,
            session_string=session_obj.session_string,
        )
        try:
            await account.connect()
            async for msg in account.get_chat_history(777000, limit=1):
                await account.disconnect()
                pattern = "(\d{1,5})"
                code = re.findall(pattern, msg.text.lower())
                if code:
                    return True, code[0], None
                return False, None, None
        except Exception as error:
            print("[Error] Retrive login code: ", error)

        return False, False, False
