class ParsingError(Exception):

    def __init__(self, args_num: int):
        self.args_num = args_num
