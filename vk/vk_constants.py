import configparser

_secret_config = configparser.ConfigParser()
_secret_config.read("vk/vk_secrets.ini")
# vk_secrets.ini is not in git, so you need to create it

TOKEN = _secret_config["SECRETS"]["token"]
GROUP_ID = int(_secret_config["SECRETS"]["group_id"])
EMPLOYEES_CHAT_PEER_ID = int(
    _secret_config["EMPLOYEES"]["employees_chat_peer_id"]
)


_constants_config = configparser.ConfigParser()
_constants_config.read("vk/vk_constants.ini")

SYMBOLS_PER_MESSAGE = int(_constants_config["MESSAGES"]["symbols_limit"])
HELP_MESSAGE_ENDING = _constants_config["HELP_MESSAGE"]["ending"]
