from dataclasses import dataclass
from typing import List, TextIO


@dataclass
class VkConfig:
    TOKEN: str
    GROUP_ID: int
    EMPLOYEES_CHAT_PEER_ID: int
    SYMBOLS_PER_MESSAGE: int
    HELP_MESSAGE_BEGINNING: str
    DEFAULT_BIG_ORDER_SEQUENCES_LIMIT: int
    MEMO_FOR_USERS: str


SPECIAL_FIELDS = {
    "help_message_beginning": (
        lambda string: f"{string}\n\n" if string else string
    )
}


def make_vk_config_from_files(
        files_with_config: List[TextIO], file_with_memo: TextIO) -> VkConfig:
    """
    WARNING: All files will be read
    """
    config_values = {}
    for file in files_with_config:
        for line in file:
            if line.endswith("\n"):
                line = line[:-1]
            if line and line[0] != ";":  # Comments start with ; in .ini files
                divided_line = line.split("=")  # "a = b" -> ["a ", " b"]
                variable_name = divided_line[0].rstrip()  # "a " -> "a"
                variable_value_as_str = divided_line[1].lstrip()  # " b" -> "b"
                middleware = SPECIAL_FIELDS.get(variable_name)
                if middleware:
                    variable_value_as_str = middleware(variable_value_as_str)
                field_name = variable_name.upper()
                config_values[field_name] = (
                    # __annotations__ looks like {field_name: annotation_class}
                    VkConfig.__annotations__[
                        field_name
                    ](variable_value_as_str)  # Calling class's constructor
                )
    return VkConfig(**config_values, MEMO_FOR_USERS=file_with_memo.read())
