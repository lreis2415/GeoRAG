import json
import re
from langchain.prompts import ChatPromptTemplate
from app.services.base_service import BaseService


class CodeGeneratorAgent(BaseService):
    def __init__(self, llm, kb_manager):
        super().__init__()
        self.llm = llm
        self.kb_manager = kb_manager

    def _extract_python_code(self, text):
        match = re.search(r"```python\n(.*?)\n```", text, re.DOTALL)
        return match.group(1) if match else text

    async def generate_entry_script(self, math_model_json: dict):
        # 1. 获取知识库中的路径配置
        code_kb = self.kb_manager.get_code_kb()
        paths = code_kb.get('paths', {})

        # 2. 准备 Prompt 上下文
        context = {
            "math_json": json.dumps(math_model_json, ensure_ascii=False, indent=2),
            "seims_root": paths.get('seims_root', r"D:\EGC\SEIMS-dev\seims"),
            "model_dir": paths.get('default_model_dir', r"D:\EGC\SEIMS-dev\data\default"),
            "bin_dir": paths.get('default_bin_dir', r"D:\EGC\SEIMS-dev\build\bin")
        }

        # 3. 构建强制性 Prompt
        system_prompt = """
        你是一个**严谨的 Python 代码生成器**。你的任务是将输入的【数学模型 JSON】填充到固定的【代码模板】中。

        ### 🚫 严禁事项:
        1. **严禁修改主流程**: 必须使用 `OptimizationFactory.create` 和 `solver.solve`。不要编造 `factory.run()` 等不存在的方法。
        2. **严禁省略逻辑**: 对于 Custom Constraints，必须根据 `mathematical_form` 编写具体的 `if` 判断逻辑，不能只写 pass 或注释。

        ### ⚙️ 代码生成规则:

        **1. 约束逻辑翻译 (Custom Constraint Logic):**
        如果遇到 `type: "Custom_Python"` (通常对应数学里的 "Physical_feasibility" 或 "slope" 限制)，请编写如下逻辑：
        - 从 `context.cfg.gene_to_unit` 获取基因对应的单元 ID。
        - 从 `context.cfg.units_infos` 获取该单元的属性（如 slope）。
        - 编写判断：如果 `slope > 阈值` 且 `val` 不符合要求，返回 `False`。

        *参考示例 (针对 "Slope > 15 必须封禁"):*
        ```python
        def validate(individual, context, mode):
            if str(mode) != 'ConstraintMode.PRE_EVALUATION': return True
            cfg = context.cfg

            for idx, val in enumerate(individual):
                if val == 1: continue # 已经是封禁，合规

                # 计算空间属性（需要用户在unit info中提供每个空间单元的slope值，若存在则继续判断，若不存在则直接跳过）
                uid = cfg.gene_to_unit.get(idx)
                if not uid: continue
                u_info = cfg.units_infos.get('units', {{}}).get(uid, {{}})
                slope = u_info.get('slope', 0)

                # 核心判断
                if slope > 15: return False
            return True
        ```

        **2. Payload 结构修正:**
        - 将输入 JSON 中的 `basic_info` (paths) 移动到 `evaluator` -> `seims` 节点下。
        - 必须确保 `evaluator` 下包含 `seims` 键，并填入 `MODEL_DIR`, `BIN_DIR`。
        - 将 `solver` 中的 `Type` 修正为标准名称 (如 "NSGA2")，如果原输入是 "NSGA2-SpatioTemporal"，也只填 "NSGA2" (框架会自动识别时间变量)。

        ### 📝 目标代码模板 (必须完全一致):
        ```python
        import sys
        import os

        # 1. 路径注入
        sys.path.append(r"{seims_root}")

        from app.services.geo_opt.optimization_framework.utils.factory import OptimizationFactory
        from app.services.geo_opt.optimization_framework.utils.visualizer import OptimizationVisualizer

        # 2. 自定义约束代码 (由 LLM 生成)
        # constraint_code_1 = \"\"\" ... \"\"\"

        # 3. 配置定义
        AGENT_PAYLOAD = {{
            "optimization_problem": {{
                "objectives": [ ... ], # ⚠️ 务必将 Cost (min) 放在第一个!
                "decision_variable": {{ ... }},
                "constraints": [
                    # Budget 示例: {{ "type": "Budget_limitation", "budget": 100000, "evaluator": "bmp_net_cost_model" }},
                    # Custom 示例: {{ "type": "Custom_Python", "code": constraint_code_1 }}
                ]
            }},
            "evaluator": {{
                "seims": {{
                    "MODEL_DIR": r"{model_dir}",
                    "BIN_DIR": r"{bin_dir}",
                    # 其他 spatial_scope 等信息...
                }}
            }},
            "solver": {{ ... }}
        }}

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
        ```

        ### 📥 输入数据 (Math Model JSON):
        {math_json}
        """

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "请根据输入生成 main_entry.py，确保填充了 slope 约束的逻辑代码。")
        ])

        chain = prompt | self.llm
        response = await chain.ainvoke(context)

        return self._extract_python_code(response.content)