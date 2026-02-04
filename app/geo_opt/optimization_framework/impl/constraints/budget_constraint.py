from ...core.interfaces import AbstractConstraint, ConstraintMode


class BudgetConstraint(AbstractConstraint):
    def __init__(self, threshold, target_obj_index=0):
        self.threshold = threshold
        self.target_idx = target_obj_index

    def validate(self, individual, context, mode: ConstraintMode) -> bool:
        # 只在 POST_EVALUATION 阶段检查
        if mode == ConstraintMode.POST_EVALUATION:
            # 尝试获取目标值
            # 注意：problem.evaluate 是按顺序执行的
            attr_name = f'obj_{self.target_idx}'

            # 1. 检查值是否存在
            if not hasattr(individual, attr_name):
                # 关键逻辑：如果轮到了我检查，但我的依赖值还没算出来
                # 说明当前的 evaluate 循环还没执行到 target_idx 这一步
                # 这种情况下，应该暂时 "放行" (return True)，等待后续步骤算出来再拦截
                return True

            cost = getattr(individual, attr_name)

            # 2. 检查数值是否有效
            if cost is None:
                return True

                # 3. 执行核心约束检查
            if cost > self.threshold:
                print(f"   ⛔ [Budget Rejection] Cost {cost:.2f} > Limit {self.threshold}. Skipping SEIMS.")
                return False  # 返回 False，触发 Problem 中的短路逻辑

        return True
