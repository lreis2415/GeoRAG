import json
import os
from typing import Dict, List


class KnowledgeManager:
    """
    统一知识管理中心
    职责：加载地理业务知识库 & 数学映射知识库
    """

    def __init__(self, domain_kb_path: str, math_kb_path: str, code_kb_path=None):
        """
                初始化知识库管理器
                :param domain_kb_path: 领域知识库路径 (geo_opt_kgb.json)
                :param math_kb_path: 数学映射知识库路径 (geo_opt_math_kb.json)
                :param code_kb_path: [新增] 代码生成知识库路径 (geo_opt_code_kb.json)
                """
        self.domain_kb_path = domain_kb_path
        self.math_kb_path = math_kb_path
        self.code_kb_path = code_kb_path  # 1. 保存路径

        # 加载领域知识库 (geo_opt_kgb.json)
        domain_json = self._load_json(domain_kb_path)

        # 1. 定位到 spatial_optimization_kb
        root_data = domain_json.get("spatial_optimization_kb", {})

        # 2. 定位到 Watershed_BMP_knowledge (这是实际存放数据的节点)
        # 如果未来有其他领域 (如 Land_Use_Opt)，可以在这里做逻辑分发
        # 目前我们默认只处理流域治理知识
        self.data = root_data.get("Watershed_BMP_knowledge", {})

        # 加载数学映射库
        self.math_data = self._load_json(math_kb_path).get("mathematical_mapping_kb", {})

    def get_code_kb(self):
        """
        2. [新增] 获取代码生成知识库
        """
        if not self.code_kb_path:
            print("⚠️ Warning: Code KB path not set.")
            return {}

        if not os.path.exists(self.code_kb_path):
            print(f"❌ Error: Code KB file not found at {self.code_kb_path}")
            return {}

        try:
            with open(self.code_kb_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error reading Code KB: {e}")
            return {}
    def _load_json(self, path: str) -> Dict:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"❌ 加载知识库失败 {path}: {e}")
                return {}
        print(f"⚠️ 文件不存在: {path}")
        return {}

    def get_formatted_options(self, category: str) -> str:
        """
        格式化知识库选项，包含定义和适用场景，供 Interpreter 做专业解释。
        """
        items = []

        # =========================================================
        # 1. 空间离散化 (Discretization)
        # =========================================================
        if category == "discs":
            # 你的 JSON 中 key 是 "discretization"
            source = self.data.get("discretization", [])

            for item in source:
                name = item.get("name", "未知")
                type_code = item.get("type", "N/A")
                desc = item.get("applicability", "暂无说明")  # 你的 JSON 里用的是 applicability
                tags = ", ".join(item.get("semantic_tags", []))

                items.append(f"- 【{type_code}】({name}):\n   适用性: {desc}\n   关键词: {tags}")

        # =========================================================
        # 2. 治理措施 (Measures)
        # =========================================================
        elif category == "measures":
            # 你的 JSON 中 key 是 "measure_library"
            source = self.data.get("measure_library", [])

            for item in source:
                name = item.get("name", "未知措施")
                desc = item.get("description", "")
                tags = ", ".join(item.get("semantic_tags", []))

                # 还可以提取一下它的建模模式，告诉 LLM 是否支持时间/面积
                modes = [m.get("mode_id") for m in item.get("modeling_modes", [])]
                mode_str = "/".join(modes) if modes else "通用"

                items.append(f"- 【{name}】 (支持模式: {mode_str}):\n   描述: {desc}\n   关键词: {tags}")

        # =========================================================
        # 3. 治理目标 (Objectives)
        # =========================================================
        elif category == "models":
            # 你的 JSON 中 key 是 "optimization_objectives"
            source = self.data.get("optimization_objectives", [])

            for item in source:
                obj_id = item.get("id", "未知目标")
                tags = ", ".join(item.get("semantic_tags", []))

                # 你的 JSON 里 indicators 是列表，需要 join
                inds = item.get("indicators", [])
                ind_str = ", ".join(inds) if isinstance(inds, list) else str(inds)

                linked = item.get("linked_models", [])
                link_str = ", ".join(linked) if isinstance(linked, list) else str(linked)

                items.append(f"- 【{obj_id}】 (模型: {link_str}):\n   指标: [{ind_str}]\n   关键词: {tags}")

        # 如果列表为空，返回提示信息而不是空字符串
        return "\n".join(items) if items else "（该分类下未找到知识库数据）"

    def get_valid_enums(self) -> Dict:
        """提供给 Validator 进行硬校验的白名单"""
        # 基于 self.data 提取，保持与 JSON 结构一致
        return {
            "discs": {i.get('type') for i in self.data.get("discretization", [])},
            "measures": {i.get('name') for i in self.data.get("measure_library", [])},
            "models": {i.get('id') for i in self.data.get("optimization_objectives", [])}
        }

    def get_math_kb(self) -> str:
        return json.dumps(self.math_data, ensure_ascii=False, indent=2)