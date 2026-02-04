import json
import os
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from .knowledge_manager import KnowledgeManager
from .requirement_parser import RequirementParser
from .logic_validator import LogicValidator
from .model_interpreter import ModelInterpreter
from app.services.base_service import BaseService
from .math_modeling_agent import MathModelingAgent

class GeoOptInteractionAgent(BaseService):
    """
    Pipeline 架构的 Agent
    流程：Parser -> Validator -> Interpreter
    """

    def __init__(self, model_service, chat_service):
        super().__init__()
        self.kb_manager = KnowledgeManager(domain_kb_path=r"/geo_opt_kgb.json", math_kb_path=r"/geo_opt_math_kb.json")
        self.parser = RequirementParser(chat_service._create_llm(), self.kb_manager)
        self.validator = LogicValidator(self.kb_manager)
        self.interpreter = ModelInterpreter(chat_service._create_llm(), self.kb_manager)
        self.math_agent = MathModelingAgent(chat_service._create_llm(), self.kb_manager)
        self.session_states = {}

    async def interact(self, user_input: str, session_id: str) -> dict:
        state = self._get_session_state(session_id)
        history = state["history"]  # 获取历史记录
        # --- 1. Parser: 全权负责提取信息 + 判断状态 ---
        # 现在的 state["template"] 已经包含了最新的状态
        state["template"] = await self.parser.parse(user_input, state["template"], history)
        # =================================================================
        # 🐞 [DEBUG] 插入监控代码：查看 Parser 填完后的实时状态表
        # =================================================================
        print("\n" + "=" * 50)
        print("📊 [DEBUG MONITOR] 当前 Session State (After Parser & Update)")
        print("=" * 50)
        print(json.dumps(state["template"], ensure_ascii=False, indent=2))
        print("=" * 50 + "\n")
        # =================================================================
        # --- 2. 检查全部确认 ---
        if self._check_all_confirmed(state["template"]):
            self._save_task(session_id, state["template"])

            state["step"] = "FINISH"


            # 2. 调用数学专家构建模型 (一行代码搞定，不关心内部 Prompt)
            # 传入简化后的纯值字典
            task_data = self._simplify_template_for_view(state["template"])
            conceptual_model = await self.math_agent.build_conceptual_model(task_data)

            # 3. 构造最终回复
            final_response = (
                "✅ **需求提取完成，任务已锁定。**\n"
                "----------------------------------\n"
                "🎓 **数学建模专家已介入，为您构建如下概念模型：**\n\n"
                f"{conceptual_model}\n"
                "----------------------------------\n"
                "系统正在准备求解器数据..."
            )
            self._update_history(history, user_input, final_response)
            return {
                "response": final_response,
                "template": state["template"],
                "step": "FINISH"
            }

        # 3. 未完成：继续引导 (Interpreter)
        # 生成校验报告辅助 Interpreter (例如哪里缺了，哪里填了)
        report = self.validator.validate(state["template"])
        response_text = await self.interpreter.generate_progress_response(user_input, state["template"], report, history)

        self._update_history(history, user_input, response_text)
        state["step"] = "PROCESSING"

        return {
            "response": response_text,
            "template": state["template"],
            "step": "PROCESSING"
        }

    def _update_history(self, history, user_input, ai_response):
        """管理滑动窗口记忆，避免 Token 爆炸"""
        # 保存用户输入
        history.append(HumanMessage(content=user_input))
        # 保存 AI 回复
        history.append(AIMessage(content=ai_response))

        # 简单策略：保留最近 10 轮对话 (20条消息)
        if len(history) > 20:
            history.pop(0)
            history.pop(0)
    def _check_all_confirmed(self, template):
        """检查所有必填项的状态是否均为 CONFIRMED"""
        required_keys = [
            "spatial_scope",
            "time_span",
            "governance_objectives",
            "spatial_discretization",
            "candidate_measures"
        ]
        for key in required_keys:
            # 必须存在且状态为 CONFIRMED
            if template.get(key, {}).get("status") != "CONFIRMED":
                return False
        return True

    def _get_session_state(self, sid):
        if sid not in self.session_states:
            # 初始化包含状态的模板
            self.session_states[sid] = {
                "step": "INIT",
                "history": [],
                "template": {
                    "spatial_scope": {"value": None, "status": "EMPTY"},
                    "time_span": {"value": None, "status": "EMPTY"},
                    "objectives": {"value": {"objectives": [], "indicators": []}, "status": "EMPTY"},
                    "discretization": {"value": None, "status": "EMPTY"},
                    "candidate_measures": {
                        "value": {"selected_measures": [], "implementation_mode": None},
                        "status": "EMPTY"
                    },
                    "constraints": {"value": [], "status": "EMPTY"}  # 可选填，不强制 confirm
                }
            }
        return self.session_states[sid]

    def _save_task(self, session_id, template):
        os.makedirs("data/runtime_configs", exist_ok=True)
        # 提取纯值保存，去掉 status
        clean_data = {k: v["value"] for k, v in template.items()}
        with open(f"data/runtime_configs/{session_id}_task.json", "w", encoding="utf-8") as f:
            json.dump(clean_data, f, ensure_ascii=False, indent=2)

    def _simplify_template_for_view(self, template):
        """
        将带状态的复杂对象简化为纯值，方便下游使用
        """
        # 创建一个新的空字典，保持原有两层结构
        simple = {}

        # 遍历第一层 (e.g., spatial_scope, time_span...)
        for key, info in template.items():
            # info 是 {"value": ..., "status": ...}
            # 我们只取 "value"
            simple[key] = info["value"]

        return simple