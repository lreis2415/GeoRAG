from datetime import datetime
import logging
import os
from typing import Dict, List, Any, Optional
import pandas as pd
import json
import time

from GeoRAGService.RAGAgent import ask_agent, get_persist_directory
from GeoRAGService.VectorDB import VectorDB


class RAGEvaluator:
    """大模型RAG回答效果评估器"""
    
    def __init__(
        self,
        chat_model_name: str,
        db_name: str,  # 替换embed_model_name为db_name
        log_dir: str = "evaluation_logs",
        use_api: bool = False,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        use_tools: bool = True,  # 添加use_tools参数，默认为True
        prompt: Optional[str] = None
    ):
        """
        初始化评估器
        
        Args:
            chat_model_name: 聊天模型名称
            db_name: 数据库名称
            log_dir: 日志目录
            use_api: 是否使用API
            api_key: API密钥
            api_base: API基础URL
            use_tools: 是否使用RAG工具，默认为True
            prompt: 自定义系统提示词
        """
        self.chat_model_name = chat_model_name
        self.db_name = db_name
        self.log_dir = log_dir
        self.use_api = use_api
        self.api_key = api_key
        self.api_base = api_base
        self.use_tools = use_tools  # 保存use_tools参数
        self.prompt = prompt
        
        # 设置日志
        self.logger = self._setup_logger()
        
        # 加载数据库
        self.vector_db = self._load_existing_database()
        
        # 初始化评估结果
        self.evaluation_results = {
            "total": 0,
            "success": 0,
            "failure": 0,
            "items": []
        }
        
        self.logger.info(f"初始化评估器: 模型={chat_model_name}, 数据库={db_name}, 使用API={use_api}, 使用工具={use_tools}")
        
        # 记录会话元数据
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_log_file = os.path.join(log_dir, f"session_{self.session_id}.json")
        self.results = []
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        # 创建日志目录
        os.makedirs(self.log_dir, exist_ok=True)
        
        logger = logging.getLogger("rag_evaluator")
        logger.setLevel(logging.INFO)
        
        # 文件处理器
        file_handler = logging.FileHandler(
            os.path.join(self.log_dir, "evaluator.log")
        )
        file_handler.setLevel(logging.INFO)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 格式化器
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加处理器
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def _load_existing_database(self) -> VectorDB:
        """
        加载已有的知识库
        
        Returns:
            VectorDB: 向量数据库实例
        """
        self.logger.info(f"正在加载已有知识库: {self.db_name}")
        
        # 检查知识库是否存在
        db_path = get_persist_directory(self.db_name)
        if not os.path.exists(db_path):
            error_msg = f"知识库 {self.db_name} 不存在，请先创建知识库"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        try:
            # 加载已有的向量数据库
            from GeoRAGService.FlexibleVectorDB import FlexibleVectorDB
            embedding_api_url = os.environ.get("EMBEDDING_API_URL", "")
            
            vector_db = FlexibleVectorDB(
                embedding_api_url=embedding_api_url,
                persist_directory=db_path,
                model_name="text-embedding-v3"
            )
            
            self.logger.info(f"知识库 {self.db_name} 加载成功")
            return vector_db
        except Exception as e:
            error_msg = f"知识库加载失败: {str(e)}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    def load_dataset(self, dataset_path: str) -> List[Dict[str, Any]]:
        """
        加载评估数据集
        
        Args:
            dataset_path: 数据集文件路径
            
        Returns:
            数据集列表
        """
        self.logger.info(f"加载评估数据集: {dataset_path}")
        
        if dataset_path.endswith('.csv'):
            df = pd.read_csv(dataset_path)
            dataset = df.to_dict('records')
        elif dataset_path.endswith('.json'):
            with open(dataset_path, 'r', encoding='utf-8') as f:
                dataset = json.load(f)
        else:
            raise ValueError(f"不支持的数据集格式: {dataset_path}")
            
        self.logger.info(f"数据集加载成功，共 {len(dataset)} 条记录")
        return dataset
    
    def _record_interaction(
        self, 
        query: str, 
        response: str, 
        metadata: Dict[str, Any]
    ) -> None:
        """
        记录交互数据
        
        Args:
            query: 查询
            response: 响应
            metadata: 元数据
        """
        interaction = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "response": response,
            "metadata": metadata
        }
        
        self.results.append(interaction)
        
        # 实时保存结果
        with open(self.session_log_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
    
    def run_evaluation(self, dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        运行评估
        
        Args:
            dataset: 评估数据集
            
        Returns:
            评估结果
        """
        if not self.vector_db:
            raise ValueError("请先加载知识库")
        
        total_count = len(dataset)
        self.logger.info(f"开始评估，共 {total_count} 条记录")
        
        for i, item in enumerate(dataset):
            query = item.get("query")
            if not query:
                self.logger.warning(f"记录 {i} 缺少查询字段，跳过")
                continue
                
            ground_truth = item.get("ground_truth", "")
            
            self.logger.info(f"处理记录 {i+1}/{total_count}: {query[:50]}...")
            
            # 记录响应和元数据
            response = ""
            metadata = {
                "item_id": i,
                "start_time": time.time(),
                "tokens": 0,  # 占位，实际应从API响应中获取
                "model": self.chat_model_name,
                "ground_truth": ground_truth
            }

            try:
                # 定义回调函数捕获响应
                def capture_response(chunk):
                    nonlocal response
                    if "agent" in chunk:
                        agent_message = chunk["agent"]["messages"][0]
                        if agent_message.content:
                            response += f"<模型输出> {agent_message.content}<模型输出>\n"
                    elif "tools" in chunk:
                        tool_message = chunk["tools"]["messages"][0]
                        response += f"<检索结果> {tool_message.content}<检索结果>\n"
                
                
                # 执行查询
                ask_agent(
                    chat_model_name=self.chat_model_name,
                    query=query,
                    use_api=self.use_api,
                    api_key=self.api_key, 
                    api_base=self.api_base,
                    vector_db=self.vector_db,
                    callback=capture_response,
                    prompt=self.prompt,
                    use_tools=self.use_tools  # 传递use_tools参数
                )
                
                # 更新元数据
                metadata["end_time"] = time.time()
                metadata["duration"] = metadata["end_time"] - metadata["start_time"]
                
                # 记录交互
                self._record_interaction(query, response, metadata)
                
                # 计算评估指标（留空）
                self._evaluate_response(query, response, ground_truth, metadata)
                
                self.logger.info(f"记录 {i+1} 处理完成，耗时 {metadata['duration']:.2f}秒")
                
            except Exception as e:
                self.logger.error(f"处理记录 {i+1} 失败: {str(e)}")
                metadata["error"] = str(e)
                metadata["end_time"] = time.time()
                metadata["duration"] = metadata["end_time"] - metadata["start_time"]
                self._record_interaction(query, f"错误: {str(e)}", metadata)
        
        self.logger.info("评估完成")
        return self._generate_evaluation_report()
    
    def _evaluate_response(
        self, 
        query: str, 
        response: str, 
        ground_truth: str, 
        metadata: Dict[str, Any]
    ) -> None:
        """
        评估响应（留空）
        
        Args:
            query: 查询
            response: 响应
            ground_truth: 真实答案
            metadata: 元数据
        """
        # 这里可以添加评估逻辑，例如计算相似度、ROUGE分数等
        # 暂时留空
        pass
    
    def _generate_evaluation_report(self) -> Dict[str, Any]:
        """
        生成评估报告
        
        Returns:
            评估报告
        """
        # 这里可以添加生成报告逻辑
        # 暂时返回基本统计信息
        return {
            "total_queries": len(self.results),
            "avg_duration": sum(r["metadata"]["duration"] for r in self.results) / len(self.results) if self.results else 0,
            "session_id": self.session_id,
            "log_file": self.session_log_file
        }


# 示例使用方法
if __name__ == "__main__":
    dta_tools_prompt = """你是一位数字地形分析(DTA)领域的专家，拥有丰富的地理信息系统和地形分析经验。
    必须先使用检索工具info_retriever查找信息，再基于检索结果回答问题，以Markdown格式输出。
    如果检索结果不完整或不足以回答问题，请明确指出。
    你应该先确定工作流的结构，以得到逻辑工作流，然后为每个计算任务选择算法，以得到可执行工作流，两者都以mermaid流程图的形式给出。
    以下是示例：
    问题：如何计算汇流累积量？
    以下是逻辑工作流：
    ```mermaid
    graph TD;
        A[填洼处理] --> B[计算流向];
        B --> C[计算汇流累积量];
    ```
    以下是可执行工作流：
    ```mermaid
    graph TD;
        A[填洼（坡度抬升填平）] --> B[流向（D8）];
        B --> C[汇流累积量_D8（栅格）];
    ```
    """

    dta_prompt = """你是一位数字地形分析(DTA)领域的专家，拥有丰富的地理信息系统和地形分析经验。
    如果涉及到流程，请提供mermaid流程图的代码。
    如果检索结果不完整或不足以回答问题，请明确指出。
    """
    # 初始化评估器
    evaluator = RAGEvaluator(
        chat_model_name="qwen-turbo",
        db_name="dta_merged",
        use_api=True,
        use_tools=True,
        api_key=os.environ.get("OPENAI_API_KEY"),
        api_base=os.environ.get("OPENAI_API_BASE"),
        prompt=dta_tools_prompt
    )
    
    # 加载数据集
    dataset = evaluator.load_dataset("GeoRAGService/data/evaluation/dta_questions.json")
    
    # 运行评估
    results = evaluator.run_evaluation(dataset)
    
    # 输出结果
    print("\n评估报告:")
    print(f"总查询数: {results['total_queries']}")
    print(f"平均响应时间: {results['avg_duration']:.2f}秒")
    print(f"日志文件: {results['log_file']}")