import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any, Tuple, Callable, Type

import exceptions


class BaseArgType(ABC):

    """
    Interface for type of argument, does conversion from string to some type.

    It isn't static because quite often it has __init__, where you can specify
    some things, which affects the conversion and regex.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def regex(self) -> str:
        pass

    @property
    def description(self) -> Optional[str]:
        return None

    @abstractmethod
    def convert(self, arg: str) -> Any:
        """
        Converts incoming argument to some type

        Args:
            arg: str with some argument

        Returns:
            arg converted to some type
        """
        pass


@dataclass
class Arg:

    name: str
    type: BaseArgType
    description: Optional[str] = None


@dataclass
class Context:

    vk_message_info: dict
    commands: Tuple["Command", ...]


class BaseMetadataElement(ABC):

    """
    Class for getting additional arguments to throw in the handler, which will
    help to handle a command.
    """

    @staticmethod
    @abstractmethod
    def get_data_from_context(context: Context) -> Any:
        """
        Returns any value, which can depend on the given context.

        Args:
            context: dict, where keys are str and values are whatever you want

        Returns:
            Any value
        """
        pass


@dataclass
class Command:

    names: Tuple[str, ...]
    handler: Callable
    description: Optional[str] = None
    metadata: Tuple[Type[BaseMetadataElement], ...] = ()
    arguments: Tuple[Arg, ...] = ()

    def convert_command_to_args(
            self, command: str, separator: str = " ") -> Tuple[Any, ...]:
        """
        Takes some str, converts it to tuple with some values.

        Args:
            command:
                user input (like "command arg1 arg2")
            separator:
                what symbol needs to be between arguments (regex);
                default " "

        Returns:
            tuple of some values, which are converted arguments from string
        """
        for args_num in range(len(self.arguments) + 1):
            names = '|'.join(re.escape(name) for name in self.names)
            pattern = separator.join(
                [
                    f"(?i:{names})",
                    *[
                        f"({arg.type.regex})"
                        for arg in self.arguments[:args_num]
                    ]  # Something like (\d\d)
                ]  # Something like (?:command) (\d\d)
            ) + ("$" if args_num == len(self.arguments) else "")
            rgx_result = re.match(
                pattern=pattern,
                string=command
            )
            if rgx_result is None:
                raise exceptions.ParsingError(args_num)
        # noinspection PyArgumentList
        # because IDK why it thinks that `arg` argument is already filled
        # (like `self`)
        # noinspection PyUnboundLocalVariable
        # because range will be at least with length of 1
        return tuple(
            converter(group)
            for group, converter in zip(
                rgx_result.groups(),
                [
                    arg.type.convert
                    for arg in self.arguments
                ]
            )
        )

    def get_converted_metadata(
            self, context: Context) -> Tuple[Any]:
        """
        Takes context, goes through all metadata elements and gets data from
        them.

        Args:
            context:
                context, which will be passed to the conversion function of
                every metadata element

        Returns:
            tuple of data received from the metadata elements
        """
        return tuple(
            one_metadata.get_data_from_context(context)
            for one_metadata in self.metadata
        )

    def get_full_description(
            self, include_type_descriptions: bool = False,
            include_heading: bool = False) -> str:
        """
        Makes a full description of the command.

        Args:
            include_type_descriptions:
                include description for type of every argument or not
            include_heading:
                include heading ("Description for command '{your_command}':
                {description}") or not

        Returns:
            generated description
        """
        heading_str = (
            f"Описание команды '{self.names[0]}': "
            f"{self.description}"
        ) if include_heading else None
        aliases_str = (
            f"Псевдонимы: {', '.join(self.names[1:])}"
        ) if len(self.names) > 1 else None
        args = []
        for argument in self.arguments:
            temp_desc = (
                f" - {argument.description}"
                if argument.description is not None else
                ""
            )
            temp_type_desc = (
                f" - {argument.type.description}"
                if argument.type.description is not None else
                ""
            )
            args.append(
                f"{argument.name} ({argument.type.name}"
                f"{temp_type_desc}){temp_desc}"
                if include_type_descriptions else
                f"{argument.name} ({argument.type.name}){temp_desc}"
            )
        args_str = (
            "Аргументы:\n{}".format("\n".join(args))
        ) if args else None
        return "\n".join(
            filter(
                lambda string: string is not None,
                (heading_str, aliases_str, args_str)
            )
        )
