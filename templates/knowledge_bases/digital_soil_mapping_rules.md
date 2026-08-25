---
template_id: digital_soil_mapping
template_version: v1
domain: digital_soil_mapping
document_type: extraction_rules
---

# 数字土壤制图结构化问题抽取规则

## 适用范围

本模板用于从自然语言问题、论文描述或项目需求中提取数字土壤制图
（Digital Soil Mapping）的建模信息。常见任务包括土壤属性空间推测、
土壤有机碳（SOC）制图、土壤养分制图和指定土层制图。

“DSM”在不同领域也可能表示 Digital Surface Model。只有当上下文明确涉及
土壤属性、土层或数字土壤制图时，才将 DSM 归类为本模板。

## 输出结构

```json
{
  "建模目标": {
    "研究区名称": null,
    "建模用途": [],
    "目标土层": null,
    "制图分辨率": null
  },
  "应用背景": {
    "地理特征参数": {
      "区域面积": {"value": null, "unit": "km²", "raw": null},
      "平均坡度": {"value": null, "unit": "°", "raw": null},
      "高程落差": {"value": null, "unit": "m", "raw": null},
      "高程标准差": {"value": null, "unit": "m", "raw": null}
    }
  }
}
```

## 字段抽取规则

### 研究区名称

提取研究区、研究区域、试验区、农场、流域或行政区名称。
同义表达包括 `study area`、`study region` 和 `research area`。
无法从原文确认时返回 `null`，不得根据常识补全地名。

### 建模用途

提取建模目的，可包含多个值。常见表达包括：

- 土壤属性空间推测
- 土壤有机碳（SOC）制图
- 土壤养分制图
- 土壤属性数字制图
- soil property mapping
- digital soil mapping

### 目标土层

提取土层深度、采样深度或目标土壤层。例如 `0-30 cm`、`0–20 cm`、
“表层土壤”。已给出上下限时规范为 `下限-上限 cm`；只有“表层”而无
明确深度时保留原始表达，不要自行假定深度。

### 制图分辨率

提取栅格分辨率、空间分辨率或制图分辨率。例如 `30 m`、`30米`、
`10 × 10 m`。保留原始表达，同时将单一数值和单位规范化。

### 地理特征参数

- 区域面积：同义词包括研究区面积、area of study region，规范单位为 `km²`。
- 平均坡度：同义词包括平均坡度、mean slope，规范单位为 `°`。
- 高程落差：表示最大高程减最小高程，同义词包括高程范围、地形起伏、
  relief、elevation range，规范单位为 `m`。
- 高程标准差：同义词包括高程离散程度、elevation standard deviation，
  规范单位为 `m`。

如果原文只给出最大和最小高程，不要自行计算高程落差，除非调用方明确
允许计算；应保留原始值并将高程落差设为 `null`。

## 通用约束

1. 只使用输入文本中能够找到证据的内容。
2. 缺失字段使用 `null`；多值字段使用数组。
3. 不把 Digital Surface Model 自动识别为 Digital Soil Mapping。
4. 输出必须是合法 JSON，不添加解释性段落。
5. 如果无法判断模板类型，应返回模板不确定，而不是强行填充字段。
