import asyncio
from dotenv import load_dotenv

# 引入 LangChain 模型适配器
from langchain_openai import ChatOpenAI
#from langchain_google_genai import ChatGoogleGenerativeAI
# 引入你的 Agent
# 假设你的 agent 代码在 app/services/geoopt_service.py
from app.geo_opt.geo_opt_agent import GeoOptInteractionAgent

# 加载 .env 环境变量 (如果有 API Key)
load_dotenv()


# ============================================
# 1. 定义一个简单的 ChatService 适配器
#    用于剥离 FastAPI 依赖，直接连接 LLM
# ============================================
class DebugChatService:
    def __init__(self, use_local=True):
        # --- 配置你的 LLM ---
        if use_local:
            # 选项 A: 使用本地 Ollama (免费，适合调试)
            #print("🔌 连接到本地 Ollama (qwen2.5-coder)...")
            #self.llm = ChatOllama(model="qwen2.5-coder:latest", temperature=0)
            '''print("🔌 连接到 Google Gemini API (gemini-3.0-flash)...")

            # 获取 API Key (建议放入 .env 文件: GOOGLE_API_KEY=AIzaSy...)
            google_api_key = "AIzaSyC6-beXvvi3BtuQzplBMwGMQM__T7Cgq9s"

            if not google_api_key:
                raise ValueError("❌ 未找到 GOOGLE_API_KEY，请在 .env 文件中配置。")

            self.llm = ChatGoogleGenerativeAI(
                model="gemini-3.0-flash",  # 或者 "gemini-1.5-flash"
                google_api_key=google_api_key,
                temperature=0,
                convert_system_message_to_human=True  # 有些旧版 Gemini 不支持 System Message，加这个保险
            )'''
        else:
            # =====================================================
            # 👇 这里填你的阿里云配置
            # =====================================================

            # 1. 把你的 Key 填在下面引号里 (sk-xxxxxxxx)
            api_key = "sk-92109e5885764a32972905d021e84b6a"

            # 2. 阿里云兼容模式的固定地址 (不要改)
            base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

            # 3. 模型名称 (例如: qwen-plus, qwen-max, qwen-turbo)
            model_name = "qwen-turbo-latest"

            print(f"🔌 连接到阿里云 API ({model_name})...")

            self.llm = ChatOpenAI(
                api_key=api_key,
                base_url=base_url,
                model=model_name,
                temperature=0,
            )

    def _create_llm(self, model_name=None):
        """适配 Agent 中调用的方法"""
        return self.llm


# ============================================
# 2. 交互循环主程序
# ============================================
async def main():
    # 1. 初始化服务
    # 修改 use_local=True 使用 Ollama，False 使用 API
    chat_service = DebugChatService(use_local=False)

    # 实例化 Agent (model_service 传 None 即可，因为调试时只测交互)
    agent = GeoOptInteractionAgent(model_service=None, chat_service=chat_service)

    session_id = "DEBUG_SESSION_001"

    print("\n" + "=" * 60)
    print("🛠️  GeoOpt Agent 本地调试终端")
    print("在此窗口输入内容，即可直接与 Agent 交互。")
    print("输入 'exit' 或 'quit' 退出。")
    print("=" * 60 + "\n")

    while True:
        # 2. 获取用户输入
        try:
            user_input = input("\n👤 [User]: ").strip()
        except EOFError:
            break

        if not user_input: continue
        if user_input.lower() in ["exit", "quit"]:
            print("👋 退出调试。")
            break

        # 3. 调用 Agent
        print("\n⏳ Agent 思考中...", end="", flush=True)
        try:
            result = await agent.interact(user_input, session_id)

            # 4. 打印 Agent 的最终回复
            print(f"\n\n🤖 [Agent Reply]:\n{result['response']}")

            # 5. (可选) 打印当前的 Session 状态快照
            # print(f"\n📊 [State Snapshot]: step={result['step']}")

        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())