import json
from typing import List, Optional, Union

import requests

from utils.load_env import config


class Telegram:
    webhook_url: str = "https://api.telegram.org/bot{}/{}"
    headers: dict = {"Cache-Control": "no-cache"}
    proxy: dict = {}

    def bot(
        self, telegram_method, data, method="GET", input_file=None, params: dict = {}
    ):
        if config.PROXY_SOCKS:
            self.proxy = {
                "http": f"socks5h://{config.PROXY_SOCKS}",
                "https": f"socks5h://{config.PROXY_SOCKS}",
            }
        url = self.webhook_url.format(config.TOKEN, telegram_method)
        try:
            if keys := data.get("reply_markup"):
                data["reply_markup"] = json.dumps(keys)

            if method == "GET":
                request = requests.get(
                    url, params=data, proxies=self.proxy, headers=self.headers
                )
                return json.loads(request.text)
            else:
                request = requests.post(
                    url=url,
                    data=data,
                    params=params,
                    files=input_file,
                    timeout=100,
                    proxies=self.proxy,
                    headers=self.headers,
                )
                if request.text:
                    return json.loads(request.text)
                return {}
        except Exception as error:
            print("Error in Telegram Class: ", error)

    def send_message(
        self: "Telegram",
        chat_id: Union[int, str],
        text: str,
        parse_mode: Optional["ParseMode"] = "html",
        entities: List["MessageEntity"] = None,
        disable_web_page_preview: bool = True,
        disable_notification: bool = None,
        reply_to_message_id: int = None,
        schedule_date: "datetime" = None,
        protect_content: bool = None,
        reply_markup: Union[
            "InlineKeyboardMarkup",
            "ReplyKeyboardMarkup",
            "ReplyKeyboardRemove",
            "ForceReply",
        ] = None,
    ):
        """
        This Method for sending a message in telegram.

          Parameters:
            chat_id (``int`` | ``str``):
                Unique identifier (int) or username (str) of the target chat.

            text (``str``):
                Text of the message to be sent.

            parse_mode (`str`, *optional*):
               By default, texts are parsed as HTML styles.

            entities (`list`, *optional*):
                List of special entities that appear in message text.

            disable_web_page_preview (`bool`, *optional*):
                Disables link previews for links in this message.

            disable_notification (`bool`, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            reply_to_message_id (`int`, *optional*):
                If the message is a reply, ID of the original message.

            schedule_date (`datetime.datetime`, *optional*):
                Date when the message will be automatically sent.

            protect_content(`bool`, *optional*):
                Protects the contents of the sent message from forwarding and saving.

            reply_markup (`list`, *optional*):
                An object for an inline keyboard, custom reply keyboard,
                instructions to remove reply keyboard or to force a reply from the user.

        """
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "entities": entities,
            "disable_web_page_preview": disable_web_page_preview,
            "disable_notification": disable_notification,
            "reply_to_message_id": reply_to_message_id,
            "schedule_date": schedule_date,
            "protect_content": protect_content,
            "reply_markup": reply_markup,
        }
        result = self.bot(telegram_method="sendMessage", data=data)
        return result

    def edit_message_text(self, chat_id, message_id, text, **kwargs):
        """
        This Method for sending message in telegram.
        **kwargs :
            parse_mode-> Str ,
            entities-> List ,
            disable_web_page_preview -> Bool ,
            disable_notification = > Bool ,
            protect_content -> Bool ,
            reply_to_message_id - > Int ,
            allow_sending_without_reply -> Bool ,
            reply_markup - > List ,
        """
        data = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "html",
            "disable_web_page_preview": "true",
        }
        data.update(**kwargs)
        result = self.bot(telegram_method="editMessageText", data=data)
        return result

    def send_answer_callback_query(self, callback_query_id, text: str, **kwargs):
        """
        This Method for send_AnswerCallbackQuery in telegram.
            **kwargs :
                show_alert -> Bool ,
                url -> text ,
                cache_time -> Int ,
        """
        method = "GET"

        data = {"callback_query_id": str(callback_query_id), "text": text}
        data.update(**kwargs)
        result = self.bot("answerCallbackQuery", data=data, method=method)
        return result

    def forward_message(self, chat_id, from_chat_id, message_id: int, **kwargs):
        """
        This Method for forward message in telegram.
            **kwargs :
                disable_notification - > Bool
                protect_content - > Bool
        """
        data = {
            "chat_id": chat_id,
            "from_chat_id": from_chat_id,
            "message_id": message_id,
        }

        data.update(**kwargs)
        result = self.bot(telegram_method="forwardMessage", data=data)
        return result

    def copy_message(self, chat_id, from_chat_id, message_id: int, **kwargs):
        """
        This Method for Copy message in telegram.
            **kwargs :
                caption -> Str
                parse_mode -> Str
                caption_entities -> List
                disable_notification -> Bool
                protect_content -> Bool
                reply_to_message_id -> Int
                allow_sending_without_reply -> Bool
                reply_markup -> List
        """
        data = {
            "chat_id": chat_id,
            "from_chat_id": from_chat_id,
            "message_id": message_id,
        }

        data.update(**kwargs)
        result = self.bot(telegram_method="copyMessage", data=data)
        return result

    def download_file(self, file_id: str):
        method = "GET"
        data = {"file_id": file_id}
        file_info = self.bot("getFile", data=data, method=method)
        file_path = file_info["result"]["file_path"]
        if config.PROXY_SOCKS:
            self.proxy = {
                "http": f"socks5h://{config.PROXY_SOCKS}",
                "https": f"socks5h://{config.PROXY_SOCKS}",
            }
        try:
            url = f"https://api.telegram.org/file/bot{config.TOKEN}/{file_path}"
            request = requests.get(
                url, params=data, proxies=self.proxy, headers=self.headers
            )
            return request.content
        except Exception as error:
            print("Error in Telegram Class: ", error)

    def get_chat_member(self, chat_id, user_id, **kwargs):
        data = {
            "chat_id": chat_id if "@" in chat_id else f"@{chat_id}",
            "user_id": user_id,
        }
        data.update(**kwargs)
        result = self.bot(telegram_method="getChatMember", data=data)
        if result["ok"]:
            return result["result"]

    def send_document(self, chat_id, document, **kwargs):
        """
        This Method for send_Document in telegram.
            **kwargs :
                caption -> Str ,
                parse_mode -> Str ,
                caption_entities -> List ,
                disable_content_type_detection -> Bool ,
                disable_notification -> Bool ,
                protect_content -> Bool ,
                reply_to_message_id -> Int ,
                allow_sending_without_reply -> Bool ,
                reply_markup -> List ,
        """
        method = "POST"
        data = {"chat_id": str(chat_id)}
        file_doc = {"document": open(document, "rb")}

        data.update(**kwargs)
        result = self.bot("sendDocument", data=data, method=method, input_file=file_doc)
        return result

    def delete_message(self, chat_id, message_id: int):
        """This Method for delete_Message in telegram."""
        method = "GET"
        data = {"chat_id": str(chat_id), "message_id": message_id}

        result = self.bot("deleteMessage", data=data, method=method)
        return result

    def remove_inline_keyboard(self, chat_id, message_id, keyboard):
        """Remove or edit the inline keyboard from msg"""
        data = {
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": {"inline_keyboard": [keyboard]},
        }
        self.bot("editMessageReplyMarkup", data=data, method="post")
