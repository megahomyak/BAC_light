class ParsingError(BaseException):

    def __init__(self, args_num: int) -> None:
        self.args_num = args_num


class NameCaseNotFound(BaseException):

    pass
