import json
import os
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from .knowledge_manager import KnowledgeManager
from .requirement_parser import RequirementParser
from .logic_validator import LogicValidator
from .model_interpreter import ModelInterpreter
from app.services.base_service import BaseService
from .math_modeling_agent import MathModelingAgent
from .code_generator_agent import CodeGeneratorAgent
class GeoOptInteractionAgent(BaseService):
    """
    Pipeline 架构的 Agent
    流程：Parser -> Validator -> Interpreter
    """

    def __init__(self, model_service, chat_service):
        super().__init__()
        # 初始化 LLM
        self.llm = chat_service._create_llm()

        # 初始化知识库 (确保包含 Code KB)
        self.kb_manager = KnowledgeManager(
            domain_kb_path=r"D:\EGC\GeoRAG\geo_opt_kgb.json",
            math_kb_path=r"D:\EGC\GeoRAG\geo_opt_math_kb.json",
            code_kb_path=r"D:\EGC\GeoRAG\geo_opt_code_kb.json"  # [新增]
        )

        # Expert 1: 需求分析组件
        self.parser = RequirementParser(self.llm, self.kb_manager)
        self.validator = LogicValidator(self.kb_manager)
        self.interpreter = ModelInterpreter(self.llm, self.kb_manager)

        # Expert 2: 数学建模
        self.math_agent = MathModelingAgent(self.llm, self.kb_manager)

        # Expert 3: 代码生成
        self.code_agent = CodeGeneratorAgent(self.llm, self.kb_manager)

        self.session_states = {}

    async def interact(self, user_input: str, session_id: str, execution_mode: int = 1) -> dict:
        """
        交互主入口
        :param user_input: 用户输入
        :param session_id: 会话ID
        :param execution_mode: 执行模式
               0: 纯闲聊 (不启动 Expert 1)
               1: 只运行 Expert 1 (需求分析)
               2: Expert 1 -> Expert 2 (数学建模)
               3: Expert 1 -> Expert 2 -> Expert 3 (代码生成)
        """

        # --- Mode 0: 纯 LLM 对话 (Chat with Agent) ---
        if execution_mode == 0:
            # 这是一个简单的直通模式，不走 Parser 状态机
            messages = [HumanMessage(content=user_input)]
            response = await self.llm.ainvoke(messages)
            return {
                "response": response.content,
                "step": "CHAT_ONLY",
                "template": {}
            }
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

            state["step"] = "CONFIRMED"

            # 准备基础回复
            base_response = "✅ **Expert 1 (Requirement):** 需求提取完成，任务已锁定。\n"

            # --- Mode 1 Finish: 到此为止 ---
            if execution_mode == 1:
                final_response = base_response + "🚫 **Debug:** 模式设置为 1，停止调用后续专家。"
                self._update_history(history, user_input, final_response)
                return {"response": final_response, "template": state["template"], "step": "FINISH_E1"}

            # --- Expert 2: 数学建模 ---
            print("🧠 [System] Calling Expert 2 (Math Modeling)...")
            task_data = self._simplify_template_for_view(state["template"])

            # 获取报告文本和 JSON 字符串
            report_md, math_json_str = await self.math_agent.build_conceptual_model(task_data)

            # 追加回复
            base_response += f"\n----------------------------------\n" \
                             f"🧠 **Expert 2 (Math Model):** 概念模型构建完成。\n\n{report_md}\n"

            # --- Mode 2 Finish: 到此为止 ---
            if execution_mode == 2:
                final_response = base_response + "\n🚫 **Debug:** 模式设置为 2，停止代码生成。"
                self._update_history(history, user_input, final_response)
                return {"response": final_response, "template": state["template"], "step": "FINISH_E2"}

            # --- Expert 3: 代码生成 ---
            print("💻 [System] Calling Expert 3 (Code Generation)...")
            try:
                math_json = json.loads(math_json_str)
                generated_code = await self.code_agent.generate_entry_script(math_json)

                # 保存代码文件
                code_filename = f"data/runtime_configs/{session_id}_main.py"
                os.makedirs(os.path.dirname(code_filename), exist_ok=True)
                with open(code_filename, "w", encoding="utf-8") as f:
                    f.write(generated_code)

                base_response += f"\n----------------------------------\n" \
                                 f"💻 **Expert 3 (Code Gen):** 执行代码已生成。\n" \
                                 f"💾 已保存至: `{code_filename}`\n" \
                                 f"```python\n{generated_code[:500]}...\n(代码过长，仅展示前500字符)\n```"

                state["step"] = "FINISH_ALL"
            except Exception as e:
                base_response += f"\n❌ **Expert 3 Error:** 代码生成失败 - {str(e)}"

            self._update_history(history, user_input, base_response)
            return {"response": base_response, "template": state["template"], "step": "FINISH_ALL"}

            # --- Expert 1 未完成: 继续引导 ---
            # 如果需求没确认完，无论选什么模式（>0），都得先跑完 Expert 1
        report = self.validator.validate(state["template"])
        response_text = await self.interpreter.generate_progress_response(user_input, state["template"], report,
                                                                          history)

        self._update_history(history, user_input, response_text)
        state["step"] = "PROCESSING"

        return {
            "response": response_text,
            "template": state["template"],
            "step": "PROCESSING"
        }

    def _update_history(self, history, user_input, ai_response):
        history.append(HumanMessage(content=user_input))
        history.append(AIMessage(content=ai_response))
        if len(history) > 20:
            history.pop(0)
            history.pop(0)
    def _check_all_confirmed(self, template):
        required_keys = ["spatial_scope", "time_span", "objectives", "discretization", "candidate_measures"]
        for key in required_keys:
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