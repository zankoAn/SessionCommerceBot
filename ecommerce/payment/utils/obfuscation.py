import base64 


class Obfuscate:
    key = 0x5F

    @classmethod
    def obfuscate_data(cls, data) -> str:
        xor_data = "".join(chr(ord(char) ^ cls.key) for char in data)
        encoded_data = base64.urlsafe_b64encode(xor_data.encode())
        return encoded_data.decode()
    
    @classmethod
    def deobfuscate_data(cls, encoded_data: str) -> str:
        decoded_data = base64.urlsafe_b64decode(encoded_data).decode()
        deobfuscated_data = "".join(chr(ord(char) ^ cls.key) for char in decoded_data)
        return deobfuscated_data