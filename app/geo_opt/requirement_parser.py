import json
import re
from typing import Dict, List
from langchain_core.messages import SystemMessage, HumanMessage
# 思维链 Prompt：强制 LLM 先思考再填空
PARSER_SYSTEM_PROMPT = """
你是一个流域治理领域的【需求解析专家】。
为了辅助用户确定专业化表达的治理需求，你需要根据对话历史和最新输入，更新治理需求清单。

### 1. 待填充的治理需求清单 (6项)
1. **治理区域的空间范围** (Spatial Scope)
2. **治理的时间跨度** (Time Span)
3. **治理的目标** (Objectives) [严格限制,每个目标需要选择一个确定的量化指标]
4. **空间离散化方案** (Discretization) [严格限制]
5. **候选治理措施及实施细节** (Measures) [严格限制，包含: 类型、面积/比例、实施时间]
6. **其他约束条件** (Constraints) [可选]
### 2. 知识库参考手册 (严格限制项必须由此选出)
{kb_context}
【实施细节模式 (Implementation Mode)】
- **Type_Selection**: 仅需确定措施类型（做或不做）。关键词：类型、选哪个、二选一。
- **Area_Proportion**: 需要规划具体面积、占比或数量。关键词：面积、多少亩、比例、规模。
- **Time_Schedule**: 需要规划实施时间。关键词：哪一年、时间表、分期实施。
### 3. 当前状态表 (Current State)
{current_state_json}

### 4. 思维链处理规则 (Chain of Thought)
请针对清单中的**每一项**问题，依次执行以下逻辑：

1. **检查状态**: 
   - 检查该项当前的 `status`。
   - 如果是 `CONFIRMED` (已确认): **跳过该项**，不许修改，除非用户明确要求“撤销确认”或“重置”。
   - 如果是 `EMPTY` 或 `FILLED`: 继续下一步。

2. **提取与更新**:
   - 判断用户的输入中是否包含了关于该项的新信息。
   - **严禁捏造**: 必须源自用户的显式表达。若未提及，保持原值。

3. **严格性校验 (针对第 3, 4, 5 项)**:
   - **目标/离散化/措施**: 必须在【知识库参考手册】中寻找语义最接近的选项。
     - *找到匹配项*: 填入知识库中的标准名称。
     - *未找到匹配项*: 保持原值或不填，**严禁**创造知识库中不存在的术语。
   **提取模式**: 判断用户对“实施细节”的要求。
   - 如果用户问“每个地块种多少”、“面积分配”，匹配为 `Area_Proportion`。
   - 如果用户问“什么时候做”，匹配为 `Time_Schedule`。
   - 如果用户只关注“选哪种措施”，匹配为 `Type_Selection`。

4. **非严格项处理 (针对第 1, 2, 6 项)**:
   - 使用专业、简洁的语言概括用户的需求。

5. **状态流转**:
    每个字段都有三个状态：`EMPTY` (未填), `FILLED` (已填待确认), `CONFIRMED` (已确认锁定)。

    请根据以下逻辑判断新状态：
    1. **提取/修改 (Update)**: 
    - 如果用户提供了新信息，状态变为 `FILLED`。
    - 示例: "改成农田" -> `status: "FILLED"`
    2. **局部确认 (Local Confirm)**: 
    - 如果用户针对某一项说"确认"，仅该项变为 `CONFIRMED`。
    3. **全局确认/结束 (Global Confirm)**: ⚠️ 关键规则
    - 如果用户表达了**“整体方案可以”**、**“进入下一步”**、**“开始建模”**、**“没问题了”**等终结性意图：
    - 请将**所有**当前已有值（非 null）且状态不是 CONFIRMED 的字段，**全部**标记为 `CONFIRMED`。

### 6. 输出要求
请输出一个 JSON 对象，**仅包含发生变化的字段**。结构如下：
{{
  "字段名": {{ "value": "更新后的值", "status": "更新后的状态(FILLED/CONFIRMED)" }}
}}
(如果无变化，返回空 JSON {{}})
"""


class RequirementParser:
    """
    流域治理专家 - 需求解析器
    职责：接收用户输入，基于知识库和当前状态，更新需求表。
    """

    def __init__(self, llm_service, kb_manager):
        self.llm = llm_service
        self.kb = kb_manager

    async def parse(self, user_input: str, current_state: Dict, history: List) -> Dict:
        # 1. 构造 System Message (包含规则、知识库、当前状态)
        system_content = PARSER_SYSTEM_PROMPT.format(
            current_state_json=json.dumps(current_state, ensure_ascii=False),
            kb_context=self._get_kb_context()  # 简单封装一下知识库获取
        )

        # 2. 构造完整的消息链：[System, ...History, User]
        # 注意：我们只取 history 的最近几条，避免 Parser 被太久远的废话干扰
        recent_history = history[-6:] if len(history) > 6 else history

        messages = [
            SystemMessage(content=system_content),
            *recent_history,  # 展开历史消息
            HumanMessage(content=user_input)
        ]
        # ==================== [DEBUG START] ====================
        print("\n" + "=" * 60)
        print("🚀 [DEBUG] 正在发送给 LLM 的 Prompt 内容:")
        print("=" * 60)

        for i, msg in enumerate(messages):
            # 获取角色名称 (System, Human, AI)
            role = msg.type.upper() if hasattr(msg, 'type') else msg.__class__.__name__

            print(f"\n📝 Message {i + 1} - [{role}]:")
            print("-" * 20)
            print(msg.content)
            print("-" * 20)

        print("=" * 60 + "\n")
        # ==================== [DEBUG END] ====================
        # 3. 调用 LLM
        response = await self.llm.ainvoke(messages)
        updates = self._safe_parse_json(response.content)

        # 4. 合并状态
        return self._apply_updates(current_state, updates)

    def _get_kb_context(self):
        return (
            f"【可选目标】{self.kb.get_formatted_options('models')}\n"
            f"【可选离散化方案】{self.kb.get_formatted_options('discs')}\n"
            f"【可选措施】{self.kb.get_formatted_options('measures')}"
        )

    def _apply_updates(self, current: Dict, updates: Dict) -> Dict:
        """
        将 LLM 返回的 update patch 应用到当前状态
        """
        if not updates:
            return current

        for field_key, change_info in updates.items():
            # 确保字段存在于我们的结构中
            if field_key in current:
                target_field = current[field_key]

                # 更新值 (如果有)
                if "value" in change_info:
                    target_field["value"] = change_info["value"]

                # 更新状态 (如果有)
                if "status" in change_info:
                    # 可以在这里加一个兜底校验：只能流转为 FILLED 或 CONFIRMED
                    if change_info["status"] in ["FILLED", "CONFIRMED"]:
                        target_field["status"] = change_info["status"]

        return current

    def _safe_parse_json(self, content):
        try:
            match = re.search(r'\{.*\}', content.replace('\n', ''), re.DOTALL)
            return json.loads(match.group(0)) if match else json.loads(content)
        except:
            return {}
    def _format_disc_details(self) -> str:
        """将离散化方案格式化为 '名称: 描述' 的形式，辅助 LLM 推理"""
        raw_discs = self.kb.raw_data.get("part_2_domain_specific_bmp", {}).get("discretization_schemes", [])
        lines = []
        for d in raw_discs:
            # 组合名称和描述/适用性
            desc = d.get("description") or d.get("rationale") or "无描述"
            tags = ",".join(d.get("semantic_tags", []))
            lines.append(f"- [{d['type']}]: 适用场景/特点 -> {desc} (关键词: {tags})")
        return "\n".join(lines)

    def _format_obj_details(self) -> str:
        """将目标和模型格式化"""
        raw_objs = self.kb.raw_data.get("part_2_domain_specific_bmp", {}).get("optimization_goals", [])
        lines = []
        for o in raw_objs:
            models = ",".join(o.get("linked_models", []))
            tags = ",".join(o.get("semantic_tags", []))
            lines.append(f"- [{o.get('id', '未命名')}]: 对应模型 -> [{models}] (关键词: {tags})")
        return "\n".join(lines)

    # ... _merge_templates 和 _safe_parse_json 保持不变 ...

    def _merge_templates(self, target: Dict, source: Dict) -> Dict:
        """深度合并，新值覆盖旧值"""
        # (此处复用你之前的合并逻辑，略微优化结构)
        if "problem_definition" in source:
            target["problem_definition"].update(source["problem_definition"])
        if "mathematical_constructs" in source:
            src_math = source["mathematical_constructs"]
            tgt_math = target["mathematical_constructs"]
            # 列表类型：覆盖策略（支持用户修改）
            for key in ["indices", "decision_variables", "optimization_objectives", "constraints"]:
                if key in src_math:
                    tgt_math[key] = src_math[key]
        return target
