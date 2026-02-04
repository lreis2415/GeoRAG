import asyncio
import json
import os
import sys

# 路径设置
sys.path.append(os.getcwd())
from dotenv import load_dotenv

# 引入 debug 工具 (复用之前的配置)
try:
    from debug_runner import DebugChatService
except ImportError:
    print("❌ 无法导入 debug_runner")
    sys.exit(1)

# 引入业务 Agent
from app.geo_opt.knowledge_manager import KnowledgeManager
from app.geo_opt.math_modeling_agent import MathModelingAgent
from app.geo_opt.code_generator_agent import CodeGeneratorAgent

load_dotenv()

# ==========================================
# 1. 模拟用户需求 (Expert 1 的输出)
# ==========================================
RAW_USER_REQ = {
    "spatial_scope": {"value": "游乌镇小流域", "status": "CONFIRMED"},
    "time_span": {"value": "2013-2017", "status": "CONFIRMED"},
    "governance_objectives": {
        "value": {
            "objectives": ["最大化泥沙削减 (Sediment_Reduction)", "最小化成本 (Cost)"],
            "indicators": ["sediment reduction rate", "net cost"]
        },
        "status": "CONFIRMED"
    },
    "spatial_discretization": {"value": "SLPPOS", "status": "CONFIRMED"},
    "candidate_measures": {
        "value": {
            "selected_measures": ["生态林草", "封禁", "经济林果"],
            # 这里的模式决定了是否生成 BMP_time
            "implementation_mode": "Time_Schedule"
        },
        "status": "CONFIRMED"
    },
    "constraints": {
        "value": [
            "总预算 <= 70万",
            "坡度大于15度必须只能采用封禁"
        ],
        "status": "CONFIRMED"
    }
}


def simplify_data(raw_state):
    simple = {}
    for key, info in raw_state.items():
        simple[key] = info["value"]
    return simple


async def main():
    print("🚀 [System] 启动多专家联合生成测试...")

    # --- Step 1: 初始化 ---
    chat_service = DebugChatService(use_local=False)
    llm = chat_service._create_llm()

    kb_manager = KnowledgeManager(
        domain_kb_path=r"D:\EGC\GeoRAG\geo_opt_kgb.json",
        math_kb_path=r"D:\EGC\GeoRAG\geo_opt_math_kb.json",
        code_kb_path = r"D:\EGC\GeoRAG\geo_opt_code_kb.json"
    )

    math_agent = MathModelingAgent(llm, kb_manager)
    code_agent = CodeGeneratorAgent(llm, kb_manager)

    # --- Step 2: Expert 2 - 数学建模 ---
    print("\n🧠 [Expert 2] 正在构建数学模型...")
    task_data = simplify_data(RAW_USER_REQ)

    # [关键修改 1] 将 "_" 改为 "report_md"，捕获报告内容
    report_md, math_json_str = await math_agent.build_conceptual_model(task_data)

    # [关键修改 2] 打印 Markdown 建模报告
    print("\n" + "=" * 60)
    print("📝 [Expert 2] Modeling Report (数学建模报告)")
    print("=" * 60)
    print(report_md)

    try:
        math_json = json.loads(math_json_str)
        print("✅ 数学模型构建成功 (JSON 结构已验证)")
        # print(json.dumps(math_json, indent=2, ensure_ascii=False))
    except json.JSONDecodeError:
        print("❌ Math Agent 生成的 JSON 格式错误")
        return

    # --- Step 3: Expert 3 - 代码生成 ---
    print("\n💻 [Expert 3] 正在生成 Python 执行代码...")
    generated_code = await code_agent.generate_entry_script(math_json)

    # --- Step 4: 输出与验证 ---
    print("\n" + "=" * 40)
    print("📄 生成的 main_entry.py 代码预览")
    print("=" * 40)
    print(generated_code)

    # 简单验证代码特征
    checks = {
        "Cost First": "objectives" in generated_code and "bmp_net_cost_model" in generated_code,
        "Custom Constraint": "def validate" in generated_code and "slope" in generated_code.lower(),
        "Path Injection": r"D:\EGC\SEIMS-dev" in generated_code
    }

    print("\n🔍 代码质量自检:")
    for check, passed in checks.items():
        print(f"   - {check}: {'✅ PASS' if passed else '⚠️ CHECK'}")

    # 保存文件 (可选)
    output_path = "auto_generated_main.py"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(generated_code)
    print(f"\n💾 代码已保存至: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())