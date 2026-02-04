import os
import numpy as np
import matplotlib.pyplot as plt
from deap.benchmarks.tools import hypervolume


class OptimizationVisualizer:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.hv_history = []

        # 确保输出目录存在
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def _extract_objectives(self, population):
        """
        从种群中提取用于绘图的目标值。
        注意：DEAP 存储的是 fitness (加权后的值)。
        我们需要将其还原为原始物理意义的值 (Cost 为正数，Env 为正数)。

        假设 Problem 定义的 weights 为: (1.0, -1.0)
        Index 0: Env Benefit (Max) -> 存储为正
        Index 1: Economic Cost (Min) -> 存储为负
        """
        env_values = []
        cost_values = []

        for ind in population:
            # 获取 fitness values
            f_vals = ind.fitness.values

            # Env (Index 0): 最大化，直接取值
            env = f_vals[0]

            # Cost (Index 1): 最小化，DEAP存的是负数，绘图时取反转为正数
            # 如果你的 CostAdapter 返回的是正数成本，DEAP 乘以 -1 后存储，这里需要乘回来
            cost = -f_vals[1]

            env_values.append(env)
            cost_values.append(cost)

        return cost_values, env_values

    def plot_pareto_front(self, population, gen):
        """绘制当前代数的帕累托前沿散点图"""
        costs, envs = self._extract_objectives(population)

        plt.figure(figsize=(10, 6), dpi=100)

        # 绘制散点
        plt.scatter(costs, envs, c='red', alpha=0.8, edgecolors='none', s=30)

        # 设置标题和标签
        plt.title(
            f"Near Pareto optimal solutions (Economy, Environment)\nGeneration: {gen}, Population: {len(population)}",
            fontsize=14, color='red')
        plt.xlabel("Economy (Cost)", fontsize=12)
        plt.ylabel("Environment (Benefit)", fontsize=12)

        # 自动调整坐标轴范围，防止点贴边
        if costs:
            plt.xlim(min(costs) * 0.95, max(costs) * 1.05)
        if envs:
            plt.ylim(min(envs) * 0.95, max(envs) * 1.05)

        plt.grid(True, linestyle='--', alpha=0.5)

        # 保存图片
        filename = os.path.join(self.output_dir, f"Pareto_Gen_{gen}.png")
        plt.savefig(filename)
        plt.close()
        # print(f"   📊 Plot saved: {filename}")

    def update_hypervolume(self, population, reference_point=None):
        """
        计算并记录当前种群的 Hypervolume。
        reference_point: 参考点 (worst_env, worst_cost_neg)。
        如果未提供，默认使用一个极大/极小值。
        """
        # 注意：Hypervolume 计算基于 DEAP 的 fitness (即 Maximize 方向)
        # 我们的 fitness 是 (Env, -Cost)，都是越大越好
        # 参考点应该比所有个体都“差”。
        # 例如：Env=0, Cost=Max_Budget (-Cost = -Max_Budget)

        if reference_point is None:
            # 默认参考点：环境=0，成本=无限大(即fitness=-无限大)
            # 实际计算中，建议根据你的问题域手动指定
            reference_point = (0.0, -1e10)

        hv = hypervolume(population, reference_point)
        self.hv_history.append(hv)

    def plot_hypervolume_curve(self):
        """绘制 Hypervolume 随代数变化的曲线"""
        if not self.hv_history:
            return

        plt.figure(figsize=(10, 6), dpi=100)
        plt.plot(range(1, len(self.hv_history) + 1), self.hv_history, marker='o', linestyle='-', color='blue')

        plt.title("Hypervolume Convergence", fontsize=14)
        plt.xlabel("Generation", fontsize=12)
        plt.ylabel("Hypervolume", fontsize=12)
        plt.grid(True)

        filename = os.path.join(self.output_dir, "Hypervolume_Curve.png")
        plt.savefig(filename)
        plt.close()
        print(f"   📈 HV Curve saved: {filename}")
