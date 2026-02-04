from typing import Dict, List, Any


class ValidationReport:
    """校验报告数据结构"""

    def __init__(self):
        self.is_valid: bool = True
        self.is_complete: bool = True
        self.missing: List[str] = []
        self.errors: List[str] = []
        self.recommendations: Dict[str, List[str]] = {}  # 针对缺失项的推荐


class LogicValidator:
    def __init__(self, kb_manager):
        self.valid_enums = kb_manager.get_valid_enums()

    def validate(self, template: Dict) -> Dict: # 返回 Dict
        report = {
            "is_valid": True,
            "is_complete": True,
            "missing": [],
            "errors": [],
            "recommendations": {}
        }

        prob = template.get("problem_definition", {})
        math = template.get("mathematical_constructs", {})

        # 1. 必填项检查
        if not prob.get("spatial_scope"): report["missing"].append("研究区域(spatial_scope)")
        if not prob.get("discretization_type"):
            report["missing"].append("空间单元(discretization_type)")

        if not math.get("decision_variables"):
            report["missing"].append("治理措施(decision_variables)")

        if not math.get("optimization_objectives"):
            report["missing"].append("优化目标(optimization_objectives)")

        # 2. 合法性检查 (查白名单)
        disc = prob.get("discretization_type")
        if disc and disc not in self.valid_enums["discs"]:
            report["errors"].append(f"未知的空间单元类型: {disc}")

        for var in math.get("decision_variables", []):
            if var.get("measure") not in self.valid_enums["measures"]:
                report["errors"].append(f"未知的措施: {var.get('measure')}")

        report["is_ready"] = (len(report["missing"]) == 0 and len(report["errors"]) == 0)
        return report

    def _check_enum(self, value: str, enum_key: str, report: ValidationReport):
        """辅助校验函数"""
        if value and value != "UNKNOWN" and value not in self.kb.enums.get(enum_key, set()):
            report.is_valid = False
            report.errors.append(f"非法值 '{value}'，不属于 {enum_key} 列表")