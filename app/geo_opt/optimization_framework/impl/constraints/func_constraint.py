from ...core.interfaces import AbstractConstraint, ConstraintMode

class CustomFunctionConstraint(AbstractConstraint):
    def __init__(self, code_str):
        self.local_scope = {}
        # 预注入必要常量，让LLM生成的代码能用
        self.local_scope['ConstraintMode'] = ConstraintMode
        try:
            exec(code_str, {}, self.local_scope)
            self.func = self.local_scope.get('validate')
        except Exception as e:
            print(f"❌ Error compiling custom constraint: {e}")
            self.func = None

    def validate(self, individual, context, mode: ConstraintMode) -> bool:
        if not self.func: return True
        try:
            # 执行自定义函数
            return self.func(individual, context, mode)
        except Exception as e:
            print(f"⚠️ Custom constraint runtime error: {e}")
            return False
