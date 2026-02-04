from ..bridge.config_bridge import ConfigBridge
from ..core.problem import OptimizationProblem
from ..impl.evaluators.seims_adapter import SEIMSEvaluator
from ..impl.evaluators.cost_adapter import CostEvaluator
from ..impl.evaluators.func_adapter import CustomFunctionEvaluator
from ..impl.constraints.budget_constraint import BudgetConstraint
from ..impl.solvers.nsga2_solver import StandardNSGA2Solver
from ..impl.solvers.interactive_solver import InteractiveNSGA2Solver
from ..impl.constraints.func_constraint import CustomFunctionConstraint # [需新增]

class OptimizationFactory:
    @staticmethod
    def create(json_data):
        # 1. Bridge Legacy Config
        legacy_cfg, is_temporal = ConfigBridge.create_legacy_config_object(json_data)

        # 2. Create Evaluators
        evaluators = []
        weights = []
        adapter_map = {
            "SEIMS": SEIMSEvaluator,
            "BMP_net_cost_model": CostEvaluator
        }
        for obj in json_data.get('optimization_problem', {}).get('objectives', []):
            eval_type = obj.get('evaluator')

            # [固定流程]：加载预置组件
            if eval_type in adapter_map:
                evaluators.append(adapter_map[eval_type](legacy_cfg, is_temporal))

            # [固定流程]：加载 LLM 生成的自定义代码
            elif eval_type == 'Custom_Python':
                if 'code' in obj:
                    evaluators.append(CustomFunctionEvaluator(obj['code']))

            # 权重处理
            name = obj.get('name', '').lower()
            w = 1.0 if obj.get('type') == 'max' else -1.0
            weights.append(w)

        # 3. 静态：解析约束 (Constraints)
        constraints = []
        con_defs = json_data.get('optimization_problem', {}).get('constraints', [])

        for cons in con_defs:
            c_type = cons.get('type')

            # [固定流程]：加载预置约束
            if c_type == 'Resource_Limitation':
                constraints.append(BudgetConstraint(cons['budget']))
                # [固定流程]：加载 LLM 生成的自定义约束代码
            elif c_type == 'Custom_Python':
                if 'code' in cons:
                    constraints.append(CustomFunctionConstraint(cons['code']))

                # 4. 静态：组装 Problem 和 Solver
        problem = OptimizationProblem(
                name="Auto_Gen_Problem",
                context=legacy_cfg,
                evaluators=evaluators,
                constraints=constraints,
                weights=tuple(weights)
        )

        solver_cfg = json_data.get('solver', {})
        if solver_cfg.get('Interactive', False):
            solver = InteractiveNSGA2Solver(legacy_cfg, is_temporal)
        else:
            solver = StandardNSGA2Solver(legacy_cfg, is_temporal)

        return problem, solver
