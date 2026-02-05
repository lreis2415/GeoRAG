import asyncio
import sys
import os

# 1. 环境路径设置
sys.path.append(os.getcwd())
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 2. 引入业务类
from app.geo_opt.geo_opt_agent import GeoOptInteractionAgent

load_dotenv()


# ============================================
# 简单的 ChatService 适配器
# ============================================
class DebugChatService:
    def __init__(self, use_local=False):
        if use_local:
            # 本地模型配置 (略)
            pass
        else:
            # 阿里云 / OpenAI 配置
            api_key = os.environ.get("DASHSCOPE_API_KEY")  # 建议从 env 读取
            if not api_key:
                # 这里的 fallback 仅用于演示，实际请配置环境变量
                api_key = "sk-xxxxxxxxxxxxxxxxxxxxxxxx"

            base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            model_name = "qwen-plus"  # 推荐使用更强的模型

            print(f"🔌 连接到 API ({model_name})...")
            self.llm = ChatOpenAI(
                api_key=api_key,
                base_url=base_url,
                model=model_name,
                temperature=0,
            )

    def _create_llm(self, model_name=None):
        return self.llm


# ============================================
# 主程序
# ============================================
async def main():
    print("\n" + "=" * 60)
    print("🛠️  GeoOpt Unified Debugger (统一调试器)")
    print("=" * 60)

    # 1. 选择运行模式
    print("\n请选择运行模式 (输入数字):")
    print(" [0] Chat Mode    : 仅与 LLM 对话，不启动任何专家 (Raw LLM)")
    print(" [1] Expert 1 Only: 仅启动需求分析专家 (Requirement Agent)")
    print(" [2] Up to Exp 2  : 需求分析 -> 数学建模 (Math Agent)")
    print(" [3] Full Chain   : 需求分析 -> 数学建模 -> 代码生成 (Code Agent)")

    while True:
        mode_input = input("\n请选择模式 (0-3): ").strip()
        if mode_input in ["0", "1", "2", "3"]:
            mode = int(mode_input)
            break
        print("❌ 输入无效，请输入 0, 1, 2 或 3")

    print(f"\n✅ 已选择模式: [{mode}]")
    print("-" * 60)

    # 2. 初始化 Agent
    # 注意：这里不需要手动初始化 Math/Code Agent，GeoOptInteractionAgent 内部会根据模式自动处理
    chat_service = DebugChatService(use_local=False)
    agent = GeoOptInteractionAgent(model_service=None, chat_service=chat_service)

    session_id = "DEBUG_SESSION_UNIFIED"

    # 3. 交互循环
    print("\n💬 开始对话 (输入 'exit' 退出)...")

    # 如果是为了测试 Expert 2/3，可以预置一句 Prompt 快速跳过寒暄
    # user_input = "帮我制定游乌镇2013-2017年的治理方案，目标是减沙和省钱，预算70万，坡度大于15度退耕，用SLPPOS和生态林草、封禁措施"

    while True:
        try:
            user_input = input("\n👤 [User]: ").strip()
        except EOFError:
            break

        if not user_input: continue
        if user_input.lower() in ["exit", "quit"]:
            print("👋 退出调试。")
            break

        print("\n⏳ Agent Running...", end="", flush=True)

        try:
            # 关键：将 mode 传入 interact 方法
            result = await agent.interact(user_input, session_id, execution_mode=mode)

            print(f"\n\n🤖 [Agent Reply]:\n{result['response']}")

            # 如果任务结束且不需要继续对话 (针对 Mode 2/3 生成完就停止的场景)
            if result.get("step") == "FINISH_ALL" and mode == 3:
                print("\n🎉 全流程执行完毕，调试器准备退出 (或继续输入以开启新会话)")
                # break # 如果想跑完一次就退，取消注释

        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())