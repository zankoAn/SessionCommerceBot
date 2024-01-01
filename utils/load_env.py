import configparser


class Config:
    def __init__(self, env=".env") -> None:
        config = configparser.ConfigParser(interpolation=None)
        file_name = f"{env}.ini"
        config.read(file_name)
        for section_name in config.sections():
            for key, value in config[section_name].items():
                setattr(self, key.upper(), value)

config = Config()