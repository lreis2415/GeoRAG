from ...core.interfaces import AbstractEvaluator

try:
    from scenario_analysis.spatialunits.scenario import SUScenario
except ImportError:
    # Mock
    class SUScenario:
        def __init__(self, cfg): self.satisfy_investment_constraints = (True, [0, 0, 0])

        def initialize(self, input_genes): pass

        def decoding(self): pass

        def decoding_with_bmps_order(self): pass

        def calculate_economy(self): return 500.0

        def calculate_economy_bmps_order(self, c, m, i): return 500.0


class CostEvaluator(AbstractEvaluator):
    def __init__(self, raw_cfg, is_temporal=False):
        self.raw_cfg = raw_cfg
        self.is_temporal = is_temporal

    def evaluate(self, individual, context) -> float:
        sce = SUScenario(self.raw_cfg)
        sce.initialize(input_genes=list(individual))

        if self.is_temporal:
            sce.decoding_with_bmps_order()
            satisfied, [costs, maintains, incomes] = sce.satisfy_investment_constraints
            if not satisfied: return 1e20  # Soft penalty
            return sce.calculate_economy_bmps_order(costs, maintains, incomes)
        else:
            sce.decoding()
            return sce.calculate_economy()