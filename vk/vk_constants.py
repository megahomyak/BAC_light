import configparser

_secret_config = configparser.ConfigParser()
_secret_config.read("vk/vk_constants.ini")
# vk_constants.ini is not in git, so you need to create it


TOKEN = _secret_config["SECRETS"]["token"]
GROUP_ID = int(_secret_config["SECRETS"]["group_id"])


SYMBOLS_PER_MESSAGE = 4096
EMPLOYEES_CHAT_PEER_ID = int(
    _secret_config["EMPLOYEES"]["employees_chat_peer_id"]
)
