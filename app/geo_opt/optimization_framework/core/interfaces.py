from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, List, Tuple

class ConstraintMode(Enum):
    PRE_EVALUATION = 1  # 基因生成后，跑任何评估前 (如：检查拓扑)
    POST_EVALUATION = 2 # 跑完部分评估后 (如：算出成本后检查预算)

class AbstractConstraint(ABC):
    @abstractmethod
    def validate(self, individual: Any, context: Any, mode: ConstraintMode) -> bool:
        """返回 True 表示满足约束，False 表示违背"""
        pass

class AbstractEvaluator(ABC):
    @abstractmethod
    def evaluate(self, individual: Any, context: Any) -> float:
        """返回单项目标值"""
        pass

class AbstractSolver(ABC):
    @abstractmethod
    def solve(self, problem: Any) -> List[Any]:
        """运行优化算法"""
        pass