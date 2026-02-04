import array
import random
from deap import base, creator, tools, algorithms
from ...core.interfaces import AbstractSolver

# 尝试导入 Legacy 工具
# 注意：前提是 main_entry.py 中已经配置了 sys.path
try:
    from scenario_analysis.spatialunits.scenario import (
        SUScenario,
        initialize_scenario,
        initialize_scenario_s_t
    )
    from scenario_analysis.spatialunits.userdef import (
        crossover_slppos,
        crossover_updown,
        crossover_rdm,
        mutate_rule_s,
        mutate_rule_s_t
    )

    IS_LEGACY_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ [NSGA2Solver] Legacy import failed: {e}")
    IS_LEGACY_AVAILABLE = False


    # Mock for syntax check pass
    def initialize_scenario(*args):
        return []


    def initialize_scenario_s_t(*args):
        return []


class StandardNSGA2Solver(AbstractSolver):
    def __init__(self, raw_config, is_temporal=False):
        self.cfg = raw_config
        self.is_temporal = is_temporal
        self.toolbox = base.Toolbox()

        # 预加载静态数据 (从 Dummy Scenario 获取适合的 BMPs 和等级)
        # 这些数据在变异算子中是必须的
        if IS_LEGACY_AVAILABLE:
            # 实例化一个临时的 Scenario 对象来提取静态配置数据
            # 这样做避免了在每次变异时都去查数据库或解析配置
            temp_sce = SUScenario(self.cfg)
            self.suit_bmps = temp_sce.suit_bmps
            self.bmps_grade = temp_sce.bmps_grade
        else:
            self.suit_bmps = {}
            self.bmps_grade = {}

    def _setup_deap(self, problem):
        """配置 DEAP 环境"""

        # 1. 动态创建 Fitness 和 Individual 类
        # 必须在运行时创建，因为 weights 是从 problem 中获取的
        if hasattr(creator, "FitnessMulti"):
            del creator.FitnessMulti
            del creator.Individual

        creator.create("FitnessMulti", base.Fitness, weights=problem.weights)
        # 使用 array.array 优化内存，typecode='d' 表示双精度浮点数
        creator.create("Individual", array.array, typecode='d', fitness=creator.FitnessMulti)

        # 2. 注册初始化函数
        # 根据是否开启时空优化，选择不同的初始化函数
        init_func = initialize_scenario_s_t if self.is_temporal else initialize_scenario

        # 注册 gene_values: 调用遗留函数生成基因列表
        self.toolbox.register("gene_values", init_func, self.cfg)

        # 注册 individual: 迭代 gene_values 来填充 Individual
        self.toolbox.register("individual", tools.initIterate, creator.Individual, self.toolbox.gene_values)

        # 注册 population
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)

        # 3. 注册评估函数 (委托给 Problem)
        self.toolbox.register("evaluate", problem.evaluate)

        # 4. 注册算子 (交叉、变异、选择)
        self._register_operators()
        self.toolbox.register("select", tools.selNSGA2)

    def _register_operators(self):
        """注册遗传算子，适配不同的空间单元和优化模式"""

        # --- A. 交叉算子 (Crossover) ---
        unit_type = getattr(self.cfg, 'bmps_cfg_unit', '')

        if unit_type == "SLPPOS":  # 坡位单元
            self.toolbox.register("mate", crossover_slppos,
                                  hillslp_values_num=getattr(self.cfg, 'hillslp_genes_num', 0),
                                  fixed_positions=getattr(self.cfg, 'key_bmps', {}))
        elif unit_type == "CONNFIELD":  # 汇流关系单元
            self.toolbox.register("mate", crossover_updown,
                                  updownunits=self.cfg.updown_units,
                                  gene2unit=self.cfg.gene_to_unit,
                                  unit2gene=self.cfg.unit_to_gene)
        else:  # 普通单元或随机
            self.toolbox.register("mate", crossover_rdm)

        # --- B. 变异算子 (Mutation) ---
        # 准备变异所需的通用参数字典
        mutation_kwargs = {
            "unitsinfo": getattr(self.cfg, 'units_infos', {}),
            "gene2unit": getattr(self.cfg, 'gene_to_unit', {}),
            "unit2gene": getattr(self.cfg, 'unit_to_gene', {}),
            "suitbmps": self.suit_bmps,
            "fixed_positions": getattr(self.cfg, 'key_bmps', {}),
            "perc": self.cfg.opt.pmut,  # 变异强度
            "indpb": self.cfg.opt.rmut,  # 变异概率
            "unit": unit_type,
            "method": getattr(self.cfg, 'bmps_cfg_method', ''),
            "bmpgrades": self.bmps_grade,
            "tagnames": getattr(self.cfg, 'slppos_tagnames', None)
        }

        # 使用 Wrapper 函数封装变异逻辑
        # 因为遗留的 mutate_rule 函数不返回值 (in-place 修改)，而 DEAP 期望返回 tuple
        if self.is_temporal:
            def temporal_mutate_wrapper(individual):
                mutate_rule_s_t(
                    individual=individual,
                    low=1,
                    up=getattr(self.cfg, 'change_times', 1),
                    **mutation_kwargs
                )
                return (individual,)

            self.toolbox.register("mutate", temporal_mutate_wrapper)
        else:
            def spatial_mutate_wrapper(individual):
                mutate_rule_s(individual=individual, **mutation_kwargs)
                return (individual,)

            self.toolbox.register("mutate", spatial_mutate_wrapper)

    def solve(self, problem, on_generation_callback=None):
        """
        执行优化主循环
        :param problem: 优化问题对象
        :param on_generation_callback: (可选) 回调函数 func(pop, gen)，用于每代画图
        """
        self._setup_deap(problem)

        # 1. 生成初始种群
        pop = self.toolbox.population(n=self.cfg.opt.npop)

        # 2. 初始评估
        invalid_ind = [ind for ind in pop if not ind.fitness.valid]
        fitnesses = map(self.toolbox.evaluate, invalid_ind)
        for ind, fit in zip(invalid_ind, fitnesses):
            ind.fitness.values = fit
            ind.gen = 0  # 记录代数
            if not hasattr(ind, 'id') or ind.id < 0: ind.id = -1

        # 记录第 0 代
        if on_generation_callback:
            on_generation_callback(pop, 0)

        print(f"🔧 [NSGA2] Started: Pop={len(pop)}, Gen={self.cfg.opt.ngens}")

        # 3. 手动展开进化循环 (Manual Evolution Loop)
        # 这替代了 algorithms.eaMuPlusLambda，以便插入 callback
        for gen in range(1, self.cfg.opt.ngens + 1):

            # A. 选择与变异 (Offspring)
            offspring = algorithms.varOr(
                pop, self.toolbox,
                lambda_=self.cfg.opt.npop,
                cxpb=self.cfg.opt.rcross,
                mutpb=self.cfg.opt.rmut
            )

            # B. 评估新个体
            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            fitnesses = map(self.toolbox.evaluate, invalid_ind)
            for ind, fit in zip(invalid_ind, fitnesses):
                ind.fitness.values = fit
                ind.gen = gen
                if not hasattr(ind, 'id') or ind.id < 0: ind.id = -1

            # C. 环境选择 (NSGA-II Selection)
            # 从 父代 + 子代 中优选
            pop = self.toolbox.select(pop + offspring, self.cfg.opt.npop)

            # D. 执行回调 (画图/日志)
            if on_generation_callback:
                on_generation_callback(pop, gen)

            # 简单的日志
            # fits_cost = [-ind.fitness.values[1] for ind in pop] # 假设 Obj 1 是 Cost
            # print(f"   Gen {gen}: Min Cost {min(fits_cost):.2f}")

        return pop
