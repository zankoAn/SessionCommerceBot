class TextUpdateDeserializer:
    def __init__(self, update: dict) -> None:
        self.update = update

    def deserialize(self):
        chat = self.update.get("chat", {})
        self.chat_id = chat.get("id")
        self.message_id = self.update.get("message_id")
        self.first_name = chat.get("first_name", "id")
        self.last_name = chat.get("last_name", "id")
        self.username = chat.get("username", self.chat_id)
        self.text = self.update.get("text", "")
        self.reply_to_msg = self.update.get("reply_to_message", [])
        self.file_id = self.update.get("document", {}).get("file_id", 0)


class CallbackUpdateDeSerializer:
    def __init__(self, update: dict) -> None:
        self.update = update

    def deserialize(self):
        message = self.update.get("message", {})
        self.callback_data = self.update.get("data")
        self.from_chat_id = self.update.get("from", {}).get("id")
        self.chat_id = message.get("chat", {}).get("id")
        self.text = message.get("text", {})
        self.message_id = message.get("message_id")
        self.callback_query_id = self.update.get("id")
        self.entities = message.get("entities", [])
        self.msg_reply_markup = message.get("reply_markup", {})