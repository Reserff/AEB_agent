"""Conservative, evidence-based screening; no inferred enums or physical units."""
import re

EVENT_SIGNALS = {"AEB_Sts", "AEB_PrtBrkReq", "AEB_FulBrkReq", "FVC_AEBReq"}
CONTEXT_SIGNALS = {"Obstacle_PosX", "Obstacle_PosY", "Obstacle_Vx", "Obstacle_Vxabs",
    "Obstacle_Ax", "Obstacle_TTC", "Obstacle_ETTC", "vehspd_mps", "AEB_BrkOrNot",
    "AEB_Override", "AEB_PrtBrkTTCTable", "AEB_FulBrkTTCTable", "FCW_Sts",
    "FVC_AEB_Sts", "FVC_AEB_TargetAx", "FVC_AEB_TgtgetAxReq", "ExternalAccelerationlDemand",
    "FVC_AWBReq", "FVC_ABAReq", "FVC_EBAReq", "XBRControlMode", "XBRurgency"}
BUSINESS_TOPICS = {"/mcu_decision_data", "/mcu_environment_data", "/vse_data",
                   "/func_output", "/func_event_info", "/jac_mcm_callback"}


def classify(row):
    name = row["field_path"].split(".")[-1]
    varied = row["changed"]
    category, reason, meaning = "暂不使用信号", "当前无明确用途；保留画像", "未知"
    if row["data_type"] in ("array", "object") or name == "__length__":
        reason = "结构或数组长度，供结构核查"
    elif name == "FVC_ObjValid":
        reason = "业务明确不作为当前核心过滤条件"
    elif name in EVENT_SIGNALS:
        category = "核心信号" if varied else "待确认信号"
        meaning = "状态/请求原始码，用于候选变化检测"
        reason = "实际出现不同取值，可检测切换；枚举含义待确认" if varied else "本段固定，不能据此认定请求无效或未发生"
    elif name in CONTEXT_SIGNALS:
        category = "辅助信号" if varied else "待确认信号"
        meaning = "目标、阈值或车辆/制动上下文候选"
        reason = "存在实际变化，可提供事件前后上下文" if varied else "本段固定；用途和默认/占位语义需协议确认"
    elif row["topic"] in BUSINESS_TOPICS and varied:
        if re.search(r"speed|spd|accel|brk|brak|aeb|ttc|obj|target|ax|vx", name, re.I):
            category, reason = "待确认信号", "有实际变化且名称提示业务关联；需核对协议及事件时间关联"
        else:
            category, reason = "待确认信号", "有实际变化，但业务语义尚未验证"
    elif row["topic"] == "/tf" or "visual" in row["topic"]:
        reason = "已解析并统计；可视化重复信息暂不作为事件依据"
    return dict(**row, unit="未知", preliminary_meaning=meaning, category=category,
                selection_reason=reason, protocol_confirmation_required=True,
                temporal_evidence="参见event_context.csv；时间接近不证明因果或制动执行")
