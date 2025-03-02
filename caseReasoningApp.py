from flask import Flask, request, jsonify
from waitress import serve
import json
import CaseReasonmingMethod as crm
import yaml

app = Flask(__name__)
app.debug = True

@app.route('/')
def start():  # put application's code here
    return "The program is running!"
def convert_value(value):
    """
    将给定的值转换为适当的类型。
    
    如果值是字符串，则尝试将其转换为整数或浮点数。
    如果值是列表，则递归地转换列表中的每个元素。
    如果值是字典，则递归地转换字典中的每个值。
    其他类型的值将原样返回。
    
    参数:
    - value: 要转换的值，可以是字符串、列表、字典或其他任何类型的值。
    
    返回:
    - 转换后的值。
    """
    # 检查输入值是否为字符串类型
    if isinstance(value, str):
        # 如果是数字字符串，则转换为整数
        if value.isdigit():
            return int(value)
        else:
            # 尝试将字符串转换为浮点数，如果失败则原样返回
            try:
                return float(value)
            except ValueError:
                return value
    # 如果输入值是列表，则对每个元素递归调用本函数进行转换
    elif isinstance(value, list):
        return [convert_value(x) for x in value]
    # 如果输入值是字典，则对每个值递归调用本函数进行转换，键保持不变
    elif isinstance(value, dict):
        return {k: convert_value(v) for k, v in value.items()}
    # 如果输入值不是上述类型，则原样返回
    else:
        return value

@app.route('/caseReasoning',methods=['GET',"POST"])
def reasoning():
    """
    step1: 获取参数，包括研究区范围&应用场景（例如dsm）&土壤空间推测需要的属性,测试下先用模拟数据
    step2: 计算研究区的地理环境特征（案例化）
    step3：根据案例化的结果进行案例推理（原型方法）

    :return: 返回推荐的参数
    """
    #
    data = request.get_data(as_text=True)
    json_data = json.loads(data)
    #print(json_data)
    # 测试数据
    #area_hs = ["125.15", "125.27", "48.99", "48.88"]
    #area_xc = ["118.5", "119.6", "31.3", "30.6"]
    # area_zxh = ["116.4", "116.5", "25.7", "25.63"]
    #json_data = {"studyArea": area_hs,
    #              "arg": {"up": "0", "down": "40", "property": "SOM"}, "model": "iPSM"}

    # Load the YAML config file containing the property codes
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Replace the property value with its code from the YAML config file
    json_data['arg']['property'] = str(config['property_codes'][json_data['arg']['property']])

    json_demo = convert_value(json_data)
    result = crm.caseParsing(json_demo)
    print(result)
    return jsonify(result)

@app.route('/caseReasoningEGC',methods=['GET',"POST"])
def reasoningEGC():
    """
    step1: 获取参数，包括研究区范围&应用场景（例如dsm）&土壤空间推测需要的属性,测试下先用模拟数据
    step2: 计算研究区的地理环境特征（案例化）
    step3：根据案例化的结果进行案例推理（原型方法）

    :return: 返回推荐的参数
    """
    #
    data = request.get_data(as_text=True)
    json_data = json.loads(data)
    #print(json_data)
    # 测试数据
    # area_hs = ["125.15", "125.27", "48.99", "48.88"]
    # area_xc = ["118.5", "119.6", "31.3", "30.6"]
    # area_zxh = ["116.4", "116.5", "25.7", "25.63"]
    #json_data = {"studyArea": ["125.15", "48.99"],
    #             "arg": {"up": "0", "down": "40", "property": "SOM"}, "model": "iPSM"}
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Replace the property value with its code from the YAML config file
    json_data['arg']['property'] = str(config['property_codes'][json_data['arg']['property']])

    json_demo = convert_value(json_data)
    result = crm.caseP arsingEGC(json_demo)
    data = result['most_similiar_case']['covariates']
    new_covariates = []
    for covariate in data:
        new_covariate = ''
        for word in covariate.split('_'):
            new_word = word.capitalize()
            if 'dem' in new_word.lower():
                new_word = new_word.replace('Dem', 'DEM')
            new_covariate += new_word + '_'
        new_covariates.append(new_covariate[:-1])
    jsonresult={}
    jsonresult['covariates'] = new_covariates
    return jsonify(jsonresult)

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=7511)
    #app.run()

