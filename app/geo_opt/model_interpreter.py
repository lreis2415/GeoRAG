import json
from typing import Dict, List
from langchain_core.messages import SystemMessage, HumanMessage

# 升级版交互 Prompt
INTERPRETER_SYSTEM_PROMPT = """
现在有一个面向流域精细治理的智能化“流域系统模拟-多目标优化”方法框架，在该框架中你属于向用户传达当前治理需求清单填写情况的**流域治理需求诊断顾问**。
你的任务是基于【当前治理需求清单状态】和【知识库】，以易用理解的语言向用户解释需要他们进一步提供/确认的信息

### 1. 知识库参考 (专家知识来源)
{kb_context}

### 2. 当前填写状态
{status_desc}

### 3. 交互策略 (核心逻辑)
请检查上述**当前填写状态**每一个字段的状态，按照以下格式输出一份面向用户的**流域治理愿景报告**:
‘’‘
"流域治理愿景报告":
1.治理需求清单中的未填项：
#### 你的任务：
列出**当前填写状态**态为 `EMPTY` 的所有项，意为当前用户还没有表达的必填项，需要引导用户进行填写)
不要只问“要什么？”，必须提供**带理由的选项**。
* **指令**:
    1. 分析用户已有的上下文（如治理目标、空间离散化方案）。
    2. 从【知识库参考】中筛选符合需求候选方案（筛选思路举例：在推荐可选的治理措施时，根据【知识库参考】措施的关键词中具有语义上与当前**治理目标**和**空间离散化方案**的优先选择）。
    3. 生成话术：“关于[某项]，目前尚未确定。根据您的需求，建议考虑：
       - 选项1：[名称]（推荐理由...）
       - 选项2：[名称]（推荐理由...）
       您倾向于哪种？”

2.治理需求清单中的待确定项：
#### 你的任务：
列出**当前填写状态**态为 `FILLED` 的所有项，意为当前根据用户表述识别出来的已填项，但是是否准确还需要用户进行检查确认
不要只问“是吗？”，必须结合知识库进行**解释性确认**。
* **指令**: 
    1. 提取用户填写的词条。
    2. 在【知识库参考】中找到对应的**定义**和**适用场景**。
    3. 生成话术：“关于[某项]，系统识别为您希望采用 **[标准名称]**。该方案[插入知识库定义]，特别适用于[插入适用场景]。请问这是否符合您的预期？”

3.治理需求清单中的已确定项：
#### 你的任务：
列出**当前填写状态**态为 `CONFIRMED` 的所有项，意为当前用户已经确认的项
* **指令**:向用户简要解释已填好的项目

4.报告结束
’‘’

**注意**：你的任务只是执行按照上述模板给出**流域治理愿景报告**，不要超出这三个任务范围。只需要询问用户清单里的项目的填写，不需要为用户生成任何方案建议或下一步计划，不要说“下一步”等词汇。
请生成一段专业、连贯的回复（避免机械罗列，保持对话感）：
"""


class ModelInterpreter:
    def __init__(self, llm_service, kb_manager):
        self.llm = llm_service
        self.kb = kb_manager

    async def generate_progress_response(self, user_input: str, template: Dict, report: Dict, history: List) -> str:
        # 1. 准备状态描述
        status_lines = []
        for key, info in template.items():
            val_str = str(info['value'])
            if key == "candidate_measures" and info['value']:
                val_str = f"措施={info['value'].get('selected_measures')}"
            status_lines.append(f"- 【{key}】: [{info['status']}] (值: {val_str})")

        # 2. 准备 System Content
        kb_context = (
                "=== 空间离散化 ===\n" + self.kb.get_formatted_options("discs") + "\n\n" +
                "=== 治理措施 ===\n" + self.kb.get_formatted_options("measures") + "\n\n" +
                "=== 治理目标 ===\n" + self.kb.get_formatted_options("models")
        )

        system_content = INTERPRETER_SYSTEM_PROMPT.format(
            kb_context=kb_context,
            status_desc="\n".join(status_lines)
        )

        # 3. 构造消息链
        # Interpreter 需要完整的语境来保持语气连贯
        messages = [
            SystemMessage(content=system_content),
            *history,
            HumanMessage(content=user_input)
        ]

        # 4. 调用 LLM
        res = await self.llm.ainvoke(messages)
        return res.content