import json
import re
from langchain.prompts import ChatPromptTemplate
from app.services.base_service import BaseService


class MathModelingAgent(BaseService):
    def __init__(self, llm, kb_manager):
        """
        :param llm: LLM 实例
        :param kb_manager: 知识库管理器 (需包含 get_math_kb 方法)
        """
        super().__init__()
        self.llm = llm
        self.kb_manager = kb_manager

    def _extract_json_and_report(self, text):
        """
        分离 LLM 返回的 JSON 配置和 Markdown 报告。
        """
        # 1. 尝试提取 ```json ... ``` 代码块
        json_match = re.search(r"```json\n(.*?)\n```", text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Fallback: 尝试寻找最外层的 {}
            json_match_fallback = re.search(r"(\{.*\})", text, re.DOTALL)
            json_str = json_match_fallback.group(1) if json_match_fallback else "{}"

        # 2. 提取 Markdown 报告 (去除 JSON 部分剩下的就是报告)
        report_text = re.sub(r"```json\n.*?\n```", "", text, flags=re.DOTALL).strip()

        return report_text, json_str

    async def build_conceptual_model(self, simplified_requirements: dict):
        """
        构建概念模型
        :param simplified_requirements: 经 simplify_data 处理后的字典 (只包含 value)
        """
        # 1. 获取上下文 (从 Knowledge Manager)
        # 假设 kb_manager.get_math_kb() 返回的是 JSON 字符串，如果返回 dict 则需 json.dumps
        kb_context = self.kb_manager.get_math_kb()
        if isinstance(kb_context, dict):
            kb_context = json.dumps(kb_context, ensure_ascii=False, indent=2)

        req_context = json.dumps(simplified_requirements, ensure_ascii=False, indent=2)

        # 2. 构建 Prompt (注意使用 {{ }} 转义 JSON/LaTeX 中的大括号)
        system_prompt = """
        现在有一个面向流域精细治理的智能化“流域系统模拟-多目标优化”方法框架，在该框架中你属于地理优化问题建模专家。
        你的任务是根据【用户需求】查阅【数学映射知识库】，构建形式化表述的优化模型。
       
        ### 🛠️ 核心任务流程：
        一个情景优化模型由**basic_info**, **optimization_problem**, **solver**三部分组成：
        1. **basic_info**:
        该部分需要填写：
        **spatial_scope**：需要查阅【知识库】中的`data_meta`，根据用户输入的区域名 (如 "游乌镇")和’description‘匹配已有研究区，填写数据字段名（如“Youwuzhen”），若不存在可匹配研究区，则填写None，不允许填写知识库中没有的研究区
        **spatial_resolution**： 需要查阅【知识库】中的`data_meta`，根据已匹配的研究区的datasets，从中选择一组合适数据，填写其“resolution”
        **time_span**：根据【用户需求】中已填写的“time_span”字段填写，需严格按照“起始年份-中止年份”填写（如，2013-2017）
        
        2. **optimization_problem**：
        该部分需要填写：
        “objectives”：需要查血【知识库】中的’optimization_objectives‘，匹配和【用户需求】中已填写的“objectives”中的objectives和indicator匹配的优化目标，并判断优化方向"optimization_sense"和需要的evaluator
        “decision variables”：需要查阅【知识库】中的decision_variables，匹配和【用户需求】中已填写的“discretization”匹配的空间离散化方案，记住其name和数学表达；
                            匹配和【用户需求】中已填写的“candidate_measures”中“selected_measures"，查阅其对应的"BMP_type" (如 封禁治理=1)，根据“implementation_mode”确定是否需要优化"BMP_time"或”BMP_area"
                            
        “constraints”：需要查阅【知识库】中的constraint_library，匹配和【用户需求】中已填写“constraints”匹配的约束条件类型，再根据其表达式给出相应公式，
                        根据【知识库】中“optimization objectives”部分知识判断当前约束条件是否可以借助已有evaluator如BMP cost model，若不存在现成evaluator，则填写“no available evaluator”
                        
        3. **solver**:
        该部分需要填写：
        “type”：具体的优化算法，需要查血【知识库】中的solver_recommendation_rules，根据“reason”来判断当前【用户需求】下应该推荐哪一个算法，填写知识库中存在的准确的“name”，禁止超出知识库范围
                        
        ### 注意事项：
        1. **⚠️ 优化模式判定 (至关重要)**:
           - **必须检查** `candidate_measures.implementation_mode` 字段：
             - **情况 A (Type_selection)**: 若模式为 `Type_selection`，**忽略时间跨度**。
               - 这属于**静态空间优化** (Spatial Optimization)。
               - 默认所有措施在起始年 (如2013) 一次性实施。
               - **严禁**生成 `BMP_time` 变量。决策变量仅包含措施类型代码。
               - 推荐求解器: `NSGA2 (Spatial)`。
             - **情况 B (Time_Schedule)**: 若模式为 `Time_Schedule`。
               - 这属于**时空协同优化** (Spatio-Temporal Optimization)。
               - 需要生成 `BMP_time` 变量。
               - 推荐求解器: `NSGA2 (Spatio-Temporal)`。

        2. **输出要求**:
           - **Part 1 (JSON)**: `decision_variable` 必须根据上述判定生成 (有无 BMP_time)。
           - **Part 2 (Modeling Report)**: 数学符号定义必须准确。
             - 若为 Type_selection，变量为 $x_{{i}}$ (无下标 t)。 
             - 若为 Time_Schedule，变量为 $x_{{i,t}}$。          

        ### 🎯 示例输出 (Strict Output Format):

        **[Part 1: JSON Payload]**
        ```json
        {{
          "basic_info": {{
            "spatial_scope": "Youwuzhen",
            "time_span": "2013-2017",
            "spatial_resolution": 30
          }},
          "optimization_problem": {{
            "objectives": [
              {{ "name": "env", "type": "max", "indicator": "sediment reduction rate", "evaluator": "seims" }},
              {{ "name": "eco", "type": "min", "indicator": "net cost", "evaluator": "bmp_net_cost_model" }}
            ],
            "decision_variable": {{
              "spatial_discretization": "SLPPOS",
              "BMP_value": {{
                "BMP_type": [1, 2, 4], 
                // 注意：这里如果没有 BMP_time，因为是 Type_selection，如果有则包含
                "BMP_time": [2013, 2014, 2015, 2016, 2017] （选填）
                ”BMP_area": (0.0, 1.0]（选填）
              }}
            }},
            "constraints": [
              {{ "name": "cost_constraint", "type": "Budget_limitation", "mathematical_form": "Sum(cost)<=1000000", "evaluator": "bmp_cost_model" }}
              {{ "name": "slope_adaption", "type": "Physical_feasibility",  "mathematical_form": "x_i in {{1 ,2}} if Slope_i > 15", "evaluator": "no available evaluator" }}
            ]
          }},
          "solver": {{
            "Type": "NSGA2",
            "GenerationsNum": 100,
            "PopulationSize": 80,
          }}
        }}
        ```

        **[Part 2: Modeling Report]**
        ## 1. 基础信息
        - **研究区**: 游乌镇流域
        - **模拟时段**: 2013-2017

        ## 2. 决策变量
        令 $x_{{i,t}}$ 表示第 $i$ 个单元在第 $t$ 年的措施：
        $$ x_{{i,t}} \in \\{{1:\\text{{封禁}}, 2:\\text{{林草}}...\\}} $$

        ## 3. 优化目标
        1. **环境效益 ($F_1$)**: 最大化泥沙削减率，使用 SEIMS 模型评估不同 BMP 配置下的泥沙削减效果；
           $$ \\max F_1 = R_{{sediment}} $$

        ---

        ### 当前输入数据:
        - **知识库 (Knowledge Base)**: {kb_context}
        - **用户需求 (User Req)**: {req_context}
        """

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "请开始建模，先输出 JSON，再输出 Markdown 报告。")
        ])

        # 3. 调用 LLM
        chain = prompt | self.llm
        response_content = (await chain.ainvoke({
            "kb_context": kb_context,
            "req_context": req_context
        })).content

        # 4. 解析结果
        report_md, json_payload = self._extract_json_and_report(response_content)
        return report_md, json_payload