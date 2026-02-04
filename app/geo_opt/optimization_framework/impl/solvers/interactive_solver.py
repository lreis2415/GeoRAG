from deap import algorithms
from .nsga2_solver import StandardNSGA2Solver

# 尝试导入交互相关的 Legacy 工具
try:
    from scenario_analysis.deap_tool import (
        interactive_selection,
        update_preference_params,
        merge_multiuser_prefs,
        selNSGA2_prefer  # 带偏好的选择算子
    )

    IS_INTERACTIVE_AVAILABLE = True
except ImportError:
    IS_INTERACTIVE_AVAILABLE = False
    print("⚠️ [InteractiveSolver] Interactive tools not found in legacy scenario_analysis.")


class InteractiveNSGA2Solver(StandardNSGA2Solver):
    """
    交互式求解器：在进化过程中引入人类偏好。
    继承自 StandardNSGA2Solver，复用其算子注册逻辑。
    """

    def solve(self, problem):
        # 1. 初始化 DEAP 环境 (复用父类逻辑)
        self._setup_deap(problem)

        # 如果遗留库中有带偏好的选择算子，覆盖默认的 select
        if IS_INTERACTIVE_AVAILABLE:
            # 注意：selNSGA2_prefer 需要 preference_params 参数，将在调用时动态传入
            # 这里先不覆盖注册，而是在循环中手动调用
            pass

        # 2. 生成初始种群
        pop = self.toolbox.population(n=self.cfg.opt.npop)

        # 获取用户信息 (通常在 ConfigBridge 中解析并挂载到 cfg 上)
        users_info = getattr(self.cfg, 'users', {})

        print(f"🔧 [Interactive] Started with {len(users_info)} users configured.")

        # 3. 手动执行进化循环 (Manual Evolution Loop)
        for gen in range(1, self.cfg.opt.ngens + 1):

            # --- A. 产生后代 (Offspring) ---
            # 使用 varOr 进行交叉和变异
            offspring = algorithms.varOr(
                pop, self.toolbox,
                lambda_=self.cfg.opt.npop,
                cxpb=self.cfg.opt.rcross,
                mutpb=self.cfg.opt.rmut
            )

            # --- B. 评估 (Evaluation) ---
            # 仅评估 fitness 无效的个体 (新生成的)
            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            fitnesses = map(self.toolbox.evaluate, invalid_ind)

            for ind, fit in zip(invalid_ind, fitnesses):
                ind.fitness.values = fit
                ind.gen = gen  # 记录代数 (Legacy代码可能需要)
                if not hasattr(ind, 'id'):
                    ind.id = -1  # 确保有 ID 属性

            # --- C. 交互环节 (Interaction Hook) ---
            # 设定交互间隔，例如每 5 代交互一次
            INTERACTIVE_INTERVAL = 5

            current_selector = self.toolbox.select
            selector_kwargs = {}

            if IS_INTERACTIVE_AVAILABLE and users_info and (gen % INTERACTIVE_INTERVAL == 0):
                print(f"\n--- 🗣️ Interaction Phase at Gen {gen} ---")

                user_prefs_list = []

                for user_id, user in users_info.items():
                    print(f"   Querying User: {user_id}...")

                    # 1. 调用遗留交互函数
                    # 注意：这通常会触发一个命令行输入或读取临时文件
                    good, bad, reasons, _ = interactive_selection(
                        pop,
                        user.get('history_good', []),
                        user.get('history_bad', []),
                        user.get('history_bad_reasons', []),
                        user_id
                    )

                    # 2. 更新偏好参数
                    # 这里的 preference_param 包含了权重向量、参考点等信息
                    user['preference_param'] = update_preference_params(
                        good, bad,
                        user.get('preference_param', {}),
                        reasons
                    )

                    # 更新历史记录
                    user['history_good'] = good
                    user['history_bad'] = bad
                    user['history_bad_reasons'] = reasons

                    user_prefs_list.append(user['preference_param'])

                # 3. 合并多用户偏好 (如果有多个用户)
                merged_prefs = merge_multiuser_prefs(user_prefs_list)

                # 4. 切换选择策略为 "带偏好选择"
                # selNSGA2_prefer 是 legacy 中修改过的选择算子，偏向用户喜欢的区域
                current_selector = selNSGA2_prefer
                selector_kwargs = {'preference_params': merged_prefs}
                print(f"   Preferences merged. Applying biased selection.")

            # --- D. 环境选择 (Selection) ---
            # 从 父代 + 子代 中选择下一代
            # 如果触发了交互，这里使用的是 selNSGA2_prefer，否则是 selNSGA2
            pop = current_selector(pop + offspring, self.cfg.opt.npop, **selector_kwargs)

            # 简单打印进度
            fits = [ind.fitness.values[0] for ind in pop]
            print(f"   Gen {gen}: Min Cost {min(fits):.2f}")

        return pop