from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple, Any, Optional
from .interfaces import AbstractConstraint, AbstractEvaluator, ConstraintMode


# --- 1. 补回缺失的枚举和数据类 ---

class ObjectiveDir(Enum):
    """优化目标方向"""
    MINIMIZE = -1.0
    MAXIMIZE = 1.0


@dataclass
class VariableDefinition:
    """决策变量定义 (保留以维持兼容性)"""
    name: str
    type: str  # 'int', 'float', 'categorical'
    lower: float
    upper: float


# --- 2. 优化问题主类 ---

class OptimizationProblem:
    """
    优化问题定义类。
    职责：编排评估流程（Pre-Check -> Evaluators -> Post-Check）。
    """

    def __init__(self,
                 name: str,
                 context: Any,  # Legacy Config Context
                 evaluators: List[AbstractEvaluator],
                 constraints: List[AbstractConstraint],
                 weights: Tuple[float, ...],
                 variables: Optional[List[VariableDefinition]] = None):  # 允许传入变量定义
        self.name = name
        self.ctx = context
        self.evaluators = evaluators
        self.constraints = constraints
        self.weights = weights
        self.variables = variables or []  # 虽然主要逻辑依赖 context，但保留此属性供查阅

    @property
    def n_vars(self):
        """变量数量优先从 Context 获取 (Legacy逻辑)，其次从 variables 列表获取"""
        if hasattr(self.ctx, 'genes_num'):
            return self.ctx.genes_num
        return len(self.variables)

    @property
    def n_objs(self):
        return len(self.evaluators)

    def evaluate(self, individual) -> Tuple[float, ...]:
        """
        核心评估流：Cost (Fast) -> Constraint -> SEIMS (Slow)
        """
        # 1. Pre-Evaluation Constraints (如拓扑检查)
        for cons in self.constraints:
            if not cons.validate(individual, self.ctx, ConstraintMode.PRE_EVALUATION):
                return self._get_penalty_fitness()

        results = []
        try:
            # 2. Run Evaluators (按顺序执行)
            for i, ev in enumerate(self.evaluators):
                # 2.1 执行单个评估器
                val = ev.evaluate(individual, self.ctx)

                # 2.2 将结果暂存到 individual 中，供后续约束使用
                # 例如：第一个评估器是 Cost，结果存入 obj_0
                setattr(individual, f"obj_{i}", val)
                results.append(val)

                # 2.3 Post-Evaluation Constraints (Inter-step check)
                # 每算完一个目标，就检查一次约束。
                # 如果算完 Cost 发现超支，直接中断，不跑后面的 SEIMS。
                for cons in self.constraints:
                    if not cons.validate(individual, self.ctx, ConstraintMode.POST_EVALUATION):
                        return self._get_penalty_fitness()

        except Exception as e:
            # 捕获评估期间的异常，避免整个优化进程崩溃
            print(f"Error evaluating individual {getattr(individual, 'id', '?')}: {e}")
            return self._get_penalty_fitness()

        return tuple(results)

    def _get_penalty_fitness(self):
        """根据权重方向返回极差值 (Min->inf, Max->-inf)"""
        penalty = []
        for w in self.weights:
            if w < 0:
                penalty.append(1e15)  # Minimize -> Max Penalty
            else:
                penalty.append(-1e15)  # Maximize -> Min Penalty
        return tuple(penalty)