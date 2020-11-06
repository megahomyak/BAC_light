import datetime
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any, Tuple, Callable, Type, Dict, List

import exceptions
import lexer.exceptions
from enums import GrammaticalCases


class BaseArgType(ABC):

    """
    Interface for type of argument, does conversion from string to some type.

    It isn't static because quite often it has __init__, where you can specify
    some things, which affects the conversion and regex.
    """

    @property
    def name(self) -> str:
        """
        Shortcut for the self.get_name()

        Returns:
            name of the argument
        """
        return self.get_name()

    @abstractmethod
    def _get_name(
            self, case: GrammaticalCases = GrammaticalCases.NOMINATIVE,
            singular: bool = True) -> Optional[str]:
        """
        Returns the string with the name of the argument or None, if there is
        no matching name. Shouldn't be used, because there is a get_name method,
        which is a wrapper around this method.

        Args:
            case:
                grammatical case of the name
            singular:
                if True, name will be returned in a singular form, else in a
                plural form

        Returns:
            name or None
        """
        pass

    def get_name(
            self, case: GrammaticalCases = GrammaticalCases.NOMINATIVE,
            singular: bool = True) -> str:
        """
        Returns the name of the argument. If nothing found, raises a
        NotImplementedError.

        Args:
            case:
                grammatical case of the name
            singular:
                if True, name will be returned in a singular form, else in a
                plural form

        Returns:
            name of the argument

        Raises:
            NotImplementedError:
                if name in the specified case and form isn't found
        """
        name = self._get_name(case, singular)
        if name is None:
            raise exceptions.NameCaseNotFound(
                f"There is no {case} for the name of {self.__class__.__name__}!"
            )
        return name

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

    # noinspection GrazieInspection
    # because what's wrong with "Stores values", come on...
    """
    Stores values, which can be used in some commands and can vary each time the
    object of this class is created. Solves the circular dependencies problem.
    """

    vk_message_info: dict
    current_datetime: datetime.date


@dataclass
class ConstantContext:

    # noinspection GrazieInspection
    # because "dependencies" is the right word! I don't want to change it to
    # "dependencies'"!!!
    """
    Object of this class is created once and then used on commands that need
    constant metadata to work. Solves the circular dependencies problem.
    """

    commands: Tuple["Command", ...]
    command_descriptions: Dict[str, List[Callable]]


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


class BaseConstantMetadataElement(ABC):

    """
    Class for getting constant additional arguments to throw in the handler,
    which will help to handle a command.
    """

    @staticmethod
    @abstractmethod
    def get_data_from_constant_context(
            constant_context: ConstantContext) -> Any:
        """
        Returns any value, which can depend on the given constant context.

        Args:
            constant_context:
                dict, where keys are str and values are whatever you want

        Returns:
            Any value
        """
        pass


@dataclass
class ConvertedCommand:

    name: str
    arguments: list


@dataclass
class Command:

    names: Tuple[str, ...]
    handler: Callable
    description: Optional[str] = None
    metadata: Tuple[Type[BaseMetadataElement], ...] = ()
    constant_metadata: Tuple[Type[BaseConstantMetadataElement], ...] = ()
    fillers: tuple = ()
    arguments: Tuple[Arg, ...] = ()
    is_not_allowed_for_clients: bool = False

    def convert_command_to_args(
            self, command: str, separator: str = " ") -> ConvertedCommand:
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
                    f"({names})",
                    *[
                        f"({arg.type.regex})"
                        for arg in self.arguments[:args_num]
                    ]  # Something like (\d\d)
                ]  # Something like (?:command) (\d\d)
            ) + ("$" if args_num == len(self.arguments) else "")
            rgx_result = re.match(pattern, command)
            if rgx_result is None:
                raise lexer.exceptions.ParsingError(args_num)
        # noinspection PyUnboundLocalVariable
        # because range(len(self.arguments) + 1) will be at least with length of
        # 1
        rgx_groups = rgx_result.groups()
        # noinspection PyArgumentList
        # because IDK why it thinks that `arg` argument is already filled
        # (like `self`)
        return ConvertedCommand(
            name=rgx_groups[0],
            arguments=[
                converter(group)
                for group, converter in zip(
                    rgx_groups[1:],
                    [
                        arg.type.convert
                        for arg in self.arguments
                    ]
                )
            ]
        )

    def get_converted_metadata(self, context: Context) -> tuple:
        """
        Takes context, goes through all metadata elements and gets data from
        them using context.

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

    def get_converted_constant_metadata(
            self, constant_context: ConstantContext) -> tuple:
        """
        Takes constant context, goes through all constant metadata elements and
        gets data from them using constant context.

        Args:
            constant_context:
                constant context, which will be passed to the conversion
                function of every constant metadata element

        Returns:
            tuple of data received from the constant metadata elements
        """
        return tuple(
            one_constant_metadata.get_data_from_constant_context(
                constant_context
            )
            for one_constant_metadata in self.constant_metadata
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
            f"Описание команды '{self.names[0]}': {self.description}" + (
                " (только для сотрудников)"  # (only for employees)
                if self.is_not_allowed_for_clients else
                ""
            )
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
            if argument.type.name == argument.name:
                temp_type_name = (
                    f" ({argument.type.description})"
                    if (
                        include_type_descriptions
                        and
                        argument.type.description is not None
                    ) else
                    ""
                )
            else:
                temp_type_name = (
                    f" ({argument.type.name} - {argument.type.description})"
                    if (
                        include_type_descriptions
                        and
                        argument.type.description is not None
                    ) else
                    f" ({argument.type.name})"
                )
            args.append(
                f"{argument.name}{temp_type_name}{temp_desc}"
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
