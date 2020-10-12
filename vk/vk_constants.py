import configparser

_secret_config = configparser.ConfigParser()
_secret_config.read("vk/vk_secrets.ini")
# vk_secrets.ini is not in git, so you need to create it


TOKEN = _secret_config["SECRETS"]["token"]
GROUP_ID = int(_secret_config["SECRETS"]["group_id"])


SYMBOLS_LIMIT = 4096
