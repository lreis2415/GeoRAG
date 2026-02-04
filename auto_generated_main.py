import sys
import os

# 1. 路径注入
sys.path.append(r"D:\EGC\SEIMS-dev\seims")

from app.services.geo_opt.optimization_framework.utils.factory import OptimizationFactory
from app.services.geo_opt.optimization_framework.utils.visualizer import OptimizationVisualizer

# 2. 自定义约束代码 (由 LLM 生成)
constraint_code_1 = """
def validate(individual, context, mode):
    if str(mode) != 'ConstraintMode.PRE_EVALUATION': return True
    cfg = context.cfg

    for idx, val in enumerate(individual):
        if val == 1: continue # 已经是封禁，合规

        # 计算空间属性（需要用户在unit info中提供每个空间单元的slope值，若存在则继续判断，若不存在则直接跳过）
        uid = cfg.gene_to_unit.get(idx)
        if not uid: continue
        u_info = cfg.units_infos.get('units', {}).get(uid, {})
        slope = u_info.get('slope', 0)

        # 核心判断：如果坡度 > 15，则必须封禁（即 val 必须为 1）
        if slope > 15:
            return False
    return True
"""

# 3. 配置定义
AGENT_PAYLOAD = {
    "optimization_problem": {
        "objectives": [
            {
                "name": "env",
                "type": "max",
                "indicator": "sediment reduction rate",
                "evaluator": "SEIMS"
            },
            {
                "name": "eco",
                "type": "min",
                "indicator": "net cost",
                "evaluator": "BMP_net_cost_model"
            }
        ],
        "decision_variable": {
            "spatial_discretization": "SLPPOS",
            "BMP_value": {
                "BMP_type": [1, 3, 4],
                "BMP_time": [2013, 2014, 2015, 2016, 2017]
            }
        },
        "constraints": [
            {
                "name": "cost_constraint",
                "type": "Resource_Limitation",
                "mathematical_form": "Sum(cost) <= 700000",
                "evaluator": "BMP_cost_model"
            },
            {
                "name": "slope_adaption",
                "type": "Custom_Python",
                "code": constraint_code_1
            }
        ]
    },
    "evaluator": {
        "seims": {
            "MODEL_DIR": r"D:\EGC\SEIMS-dev\data\youwuzhen\demo_youwuzhen30m_longterm_model",
            "BIN_DIR": r"D:\EGC\SEIMS-dev\build\bin",
            "spatial_scope": "Youwuzhen",
            "time_span": "2013-2017",
            "spatial_resolution": 30
        }
    },
    "solver": {
        "Type": "NSGA2",  # ✅ 修正为标准名称（框架自动识别时空变量）
        "GenerationsNum": 100,
        "PopulationSize": 80
    }
}

def main():
    print("🚀 Starting Optimization...")
    # 标准工厂调用
    problem, solver = OptimizationFactory.create(AGENT_PAYLOAD)

    # 建立可视化
    out_dir = os.path.join(os.path.dirname(__file__), "results")
    vis = OptimizationVisualizer(out_dir)

    def on_step(pop, gen):
        vis.plot_pareto_front(pop, gen)
        vis.update_hypervolume(pop)

    # 执行求解
    solver.solve(problem, on_generation_callback=on_step)
    vis.plot_hypervolume_curve()

if __name__ == "__main__":
    main()