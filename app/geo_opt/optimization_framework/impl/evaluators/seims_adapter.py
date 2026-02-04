import sys

# 确保能加载 Legacy 代码
seims_path = r"D:\EGC\SEIMS-dev\seims"
if seims_path not in sys.path:
    sys.path.insert(0, seims_path)

from ...core.interfaces import AbstractEvaluator

# 引入 Legacy Scenario 类
try:
    from scenario_analysis.spatialunits.scenario import (
        SUScenario,
        scenario_effectiveness,
        scenario_effectiveness_with_bmps_order
    )
except ImportError:
    # 仅用于防止IDE报错，实际运行时 ConfigBridge 已修复路径
    class SUScenario:
        pass


    scenario_effectiveness = None
    scenario_effectiveness_with_bmps_order = None


class SEIMSEvaluator(AbstractEvaluator):
    def __init__(self, raw_config, is_temporal=False):
        self.raw_cfg = raw_config
        self.is_temporal = is_temporal

        # 初始化时立即检查并运行基准情景
        print("🔍 [SEIMSEvaluator] Checking Base Scenario status...")
        self._check_and_run_base_scenario()

    def _check_and_run_base_scenario(self):
        """
        检查配置中的 BASE_ENV。如果是占位符(-9999)，则运行全0情景获取基准值。
        """
        # 1. 检查是否已有基准值
        current_base = self.raw_cfg.eval_info.get('BASE_ENV', -9999)
        if current_base > 0:
            print(f"✅ [Evaluator] Using existing Base Environment Value: {current_base}")
            return

        print("⚠️ [Evaluator] BASE_ENV missing or invalid. Running Base Scenario (All Zeros)...")

        # 2. 构造全 0 基因 (代表无 BMP 措施)
        n_genes = self.raw_cfg.genes_num
        zero_genes = [0] * n_genes

        # 3. 手动实例化 SUScenario 并运行
        # 这里不使用 scenario_effectiveness 函数，而是手动控制流程以确保 ID 正确且能捕获错误
        try:
            sce = SUScenario(self.raw_cfg)
            sce.initialize(input_genes=zero_genes)

            # 强制设置 ID 为 0 (约定 0 为基准情景)
            sce.set_unique_id(0)

            # 解码并写入数据库
            if self.is_temporal:
                sce.decoding_with_bmps_order()
            else:
                sce.decoding()
            sce.export_to_mongodb()

            # 运行模型 (关键：如果这里失败，会抛出异常或返回 False)
            print(f"   [Base] Executing SEIMS model for Scenario ID 0...")
            success = sce.execute_seims_model()

            if not success:
                print("❌ [Error] Base Scenario execution returned False.")
                # 这里不抛出致命异常，允许后续重试，但打印明显警告
                return

            # 计算环境指标 (此时 base_env 是负数，calculate 会返回绝对值 sed_sum)
            if self.is_temporal:
                sce.calculate_environment_bmps_order()
            else:
                sce.calculate_environment()

            base_sed_sum = sce.sed_sum

            # 4. 更新配置对象
            if base_sed_sum > 0:
                self.raw_cfg.eval_info['BASE_ENV'] = base_sed_sum
                if self.is_temporal:
                    self.raw_cfg.eval_info['BASE_SED_PERIODS'] = sce.sed_per_period
                print(f"✅ [Evaluator] Base Scenario Updated: BASE_ENV = {base_sed_sum}")
            else:
                print(f"❌ [Error] Base Scenario Result Invalid (Sediment={base_sed_sum})")

        except Exception as e:
            print(f"❌ [Error] Failed to run Base Scenario: {e}")
            import traceback
            traceback.print_exc()

    def evaluate(self, individual, context) -> float:
        # 1. 注入 ID
        if not hasattr(individual, 'id') or individual.id < 0:
            # 临时生成一个 ID (避免与 Base 0 冲突)
            individual.id = self.raw_cfg.model.scenario_id + 100

            # 2. 调用 Legacy 函数
        # 注意：此时 BASE_ENV 应该是正数，计算出的 environment 是削减率
        try:
            if self.is_temporal:
                processed_ind = scenario_effectiveness_with_bmps_order(self.raw_cfg, individual)
            else:
                processed_ind = scenario_effectiveness(self.raw_cfg, individual)

            return processed_ind.environment
        except Exception as e:
            print(f"❌ [Evaluator] Evaluate failed for ID {individual.id}: {e}")
            return self.raw_cfg.worst_env
