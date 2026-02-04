import json
import os
import sys
from ..utils.config_proxy import DictConfigProxy

# --- [关键修改] 移除 try-except，强制加载真实库 ---
# 如果这里报错，说明 sys.path 设置不对，或者缺少依赖包 (如 pygeoc)
print(f"DEBUG: Loading Legacy Config from path: {sys.path}")
from scenario_analysis.config import SAConfig
from scenario_analysis.spatialunits.config import SASlpPosConfig, SAConnFieldConfig

class ConfigBridge:
    @staticmethod
    def _construct_config_dict(json_data):
        """将 Agent JSON 转换为符合 legacy 结构的字典"""
        input_prob = json_data['optimization_problem']
        seims_cfg = json_data['evaluator'].get('seims', {})

        config_dict = {}

        # [SEIMS_Model]
        raw_model_dir = seims_cfg.get("MODEL_DIR", r"D:\Default")
        clean_model_dir = os.path.normpath(raw_model_dir)
        config_dict['SEIMS_Model'] = {
            "HOSTNAME": seims_cfg.get("HOSTNAME", "127.0.0.1"),
            "PORT": seims_cfg.get("PORT", "27017"),
            "VERSION": "OMP",
            "NTHREAD": "4", "FDIRMTD": "0", "LYRMTD": "1", "SCENARIO_ID": "0",
            "Sim_Time_start": "2013-01-01 00:00:00", "Sim_Time_end": "2017-12-31 23:59:59",
            "MODEL_DIR": clean_model_dir,
            "BIN_DIR": seims_cfg.get("BIN_DIR", r"D:\Default\Bin"),
            "db_name": seims_cfg.get("db_name", os.path.basename(clean_model_dir))
        }

        # [Scenario_Common]
        time_span = seims_cfg.get('time_span', "2013-2017")
        start_year, end_year = time_span.split('-') if '-' in time_span else ("2013", "2017")
        bmp_times = input_prob['decision_variable'].get('BMP_value', {}).get('BMP_time', [])  # 比如 [1,2,3]
        is_temporal = bool(bmp_times)

        # 寻找预算
        budget = 100000
        for cons in input_prob.get('constraints', []):
            if cons.get('type') == 'Budget_limitation':
                budget = cons.get('budget', 100000)

        config_dict['Scenario_Common'] = {
            "runtime_years": int(end_year) - int(start_year) + 1,
            "eval_time_start": f"{start_year}-01-01 00:00:00",
            "eval_time_end": f"{end_year}-12-31 23:59:59",
            "worst_economy": 99999999.0,
            "worst_environment": 0.0,
            "enable_implementation_order": is_temporal,
            "implementation_period": len(bmp_times) if is_temporal else 5,
            "effectiveness_changeable": is_temporal,
            "change_frequency": 1,
            "change_times": len(bmp_times) if is_temporal else 1,  # 必须加上这个
            "years_first_period": len(bmp_times) if is_temporal else 5,
            "enable_investment_quota": True,
            "investment_float_range": 0.2,
            "investment_each_period": [budget],  # 必须是列表字符串
            "investment_aver_constrain": False,
            "discount_rate": 0.1,
            "selected_scenario_file": "",
            "export_scenario_txt": True,
            "export_scenario_tif": False,
            "prioritize_key_bmps": False,
            "pareto_front_scenarios": "[]"
        }

        # [BMPs]
        spatial_unit = input_prob['decision_variable'].get('spatial_discretization', 'SLPPOS')
        bmp_types = input_prob['decision_variable'].get('BMP_value', {}).get('BMP_type', [1, 2])

        # 构造 BMPs_info (简化版，实际应从数据库读取或更复杂构造)
        bmps_info = {
            "17": {
                "COLLECTION": "AREAL_STRUCT_MANAGEMENT",
                "SUBSCENARIO": bmp_types,
                "SLPPOS_TAG_NAME": {"1": "summit", "4": "backslope", "16": "valley"},
                "SLPPOS_GFS_NAME": {"1": "rdgInf", "4": "bksInf", "16": "vlyInf"}
            }
        }
        bmps_retain = {
            "12": {
                "COLLECTION": "PLANT_MANAGEMENT",
                "DISTRIBUTION": "RASTER|LANDUSE",
                "LOCATION": "33",
                "SUBSCENARIO": 0
            }
        }
        unit_json_map = {"SLPPOS": "slppos_3cls_units_updown.json", "CONNFIELD": "connected_field_units_updown_15.json"}
        cfg_units = {spatial_unit: {"DISTRIBUTION": f"RASTER|{spatial_unit}_UNITS",
                                    "UNITJSON": unit_json_map.get(spatial_unit, "units.json")}}

        config_dict['BMPs'] = {
            "bmps_info": json.dumps(bmps_info),
            "bmps_retain": json.dumps(bmps_retain),
            "eval_info": json.dumps({"OUTPUTID": "SED_OL", "ENVEVAL": "SED_OL_SUM.tif", "BASE_ENV": -9999}),
            "bmps_cfg_units": json.dumps(cfg_units),
            "bmps_cfg_method": "HILLSLP" if spatial_unit == 'SLPPOS' else "RAND",
            "bmps_cfg_units_opt": False
        }

        # [NSGA2]
        solver_cfg = json_data.get('solver', {})
        config_dict['NSGA2'] = {
            "GenerationsNum": solver_cfg.get('GenerationsNum', 100),
            "PopulationSize": solver_cfg.get('PopulationSize', 80),
            "CrossoverRate": solver_cfg.get('CrossoverRate', 0.8),
            "MutateRate": solver_cfg.get('MutateRate', 0.1),
            "MaxMutatePerc": 0.2,
            "InputPopulation": False
        }

        return config_dict, spatial_unit, is_temporal

    @staticmethod
    def create_legacy_config_object(json_data):
        cfg_dict, unit_type, is_temporal = ConfigBridge._construct_config_dict(json_data)
        proxy = DictConfigProxy(cfg_dict)

        if unit_type == 'SLPPOS':
            raw_cfg = SASlpPosConfig(proxy)
        elif unit_type == 'CONNFIELD':
            raw_cfg = SAConnFieldConfig(proxy)
        else:
            raw_cfg = SAConfig(proxy)

        try:
            raw_cfg.construct_indexes_units_gene()
        except Exception as e:
            print(f"⚠️ Warning during SAConfig init (Expected if testing without data): {e}")

        return raw_cfg, is_temporal
