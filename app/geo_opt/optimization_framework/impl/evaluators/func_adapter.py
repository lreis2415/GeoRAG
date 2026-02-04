from ...core.interfaces import AbstractEvaluator

class CustomFunctionEvaluator(AbstractEvaluator):
    def __init__(self, func_code: str):
        self.local_scope = {}
        exec(func_code, {}, self.local_scope)
        self.func = self.local_scope.get('evaluate')

    def evaluate(self, individual, context) -> float:
        return self.func(list(individual), getattr(context, 'config_dict', {}))