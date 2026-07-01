import asyncio
import json
import logging
import uuid
import socket
import threading
import time
import random
from http.server import SimpleHTTPRequestHandler, HTTPServer

# 配置日志格式，输出时间、级别及上下文。
logging.basicConfig(
    level=logging.DEBUG,
    format='\033[1;36m%(asctime)s\033[0m [\033[1;33m%(levelname)s\033[0m] %(message)s',
    datefmt='%H:%M:%S'
)

# 维护节点与连接对象的映射关系。
clients = {}

# 模拟巡检点假数据
endpoints = [
    {
        "id": 1,
        "point_id": "point_1",
        "name": "充电桩",
        "x": 0.0,
        "y": 0.0,
        "yaw": 0.0,
        "broadcastContent": "我已到达充电桩",
        "playOnArrival": True,
        "photoOnArrival": False,
        "pointType": 2,
        "status": "可达",
        "isReachable": True,
        "stayTime": 0.0,
        "needRotate": False
    },
    {
        "id": 2,
        "point_id": "point_2",
        "name": "会议室",
        "x": 5.5,
        "y": 2.3,
        "yaw": 1.57,
        "broadcastContent": "会议室已到达",
        "playOnArrival": True,
        "photoOnArrival": True,
        "pointType": 0,
        "status": "可达",
        "isReachable": True,
        "stayTime": 5.0,
        "needRotate": False
    }
]

# 模拟路线假数据
routes = [
    {
        "id": 1,
        "route_id": "route_001",
        "route_name": "每日巡检路线",
        "description": "覆盖办公区 and 休息区的例行巡检",
        "points": ["point_1", "point_2"],
        "pointCount": 2,
        "isActive": True,
        "createTime": int(time.time() * 1000),
        "updateTime": int(time.time() * 1000),
        "loopCount": 2
    }
]

# 模拟手臂动作假数据
arm_actions = [
    {"id": 1, "name": "握手", "time": 3.0},
    {"id": 2, "name": "招手", "time": 2.5},
    {"id": 3, "name": "敬礼", "time": 2.0},
    {"id": 4, "name": "跳舞", "time": 5.0}
]

# 模拟机器人姿态假数据
postures = [
    {"id": 1, "technical_name": "stand", "display_name": "立正"},
    {"id": 2, "technical_name": "rest", "display_name": "稍息"},
    {"id": 3, "technical_name": "sit", "display_name": "坐下"},
    {"id": 4, "technical_name": "squat", "display_name": "蹲下"},
    {"id": 5, "technical_name": "bow", "display_name": "鞠躬"},
    {"id": 6, "technical_name": "think", "display_name": "思考"},
    {"id": 7, "technical_name": "lie", "display_name": "趴下"},
    {"id": 8, "technical_name": "nod", "display_name": "点头"},
    {"id": 9, "technical_name": "shake", "display_name": "摇头"},
    {"id": 10, "technical_name": "stretch", "display_name": "伸懒腰"},
    {"id": 11, "technical_name": "look_around", "display_name": "环视"},
    {"id": 12, "technical_name": "sleep", "display_name": "睡眠"},
    {"id": 13, "technical_name": "happy", "display_name": "开心"},
    {"id": 14, "technical_name": "angry", "display_name": "生气"},
    {"id": 15, "technical_name": "sad", "display_name": "难过"},
    {"id": 16, "technical_name": "surprised", "display_name": "惊讶"},
    {"id": 17, "technical_name": "dance", "display_name": "跳舞"},
    {"id": 18, "technical_name": "look_up", "display_name": "抬头"},
    {"id": 19, "technical_name": "look_down", "display_name": "低头"},
    {"id": 20, "technical_name": "wave", "display_name": "挥手"},
    {"id": 21, "technical_name": "salute", "display_name": "敬礼"},
    {"id": 22, "technical_name": "turn_around", "display_name": "转身"},
    {"id": 23, "technical_name": "show", "display_name": "展示"},
    {"id": 24, "technical_name": "run", "display_name": "跑步"},
    {"id": 25, "technical_name": "jump", "display_name": "跳跃"},
    {"id": 26, "technical_name": "clap", "display_name": "鼓掌"},
    {"id": 27, "technical_name": "point", "display_name": "指路"},
    {"id": 28, "technical_name": "yoga", "display_name": "瑜伽"}
]

# 模拟机器人位置数据
robot_position = {
    "x": 0.0,
    "y": 0.0,
    "yaw": 0.0
}

# 模拟机器人导航状态
robot_state = "IDLE"
current_target_point_id = None
arm_state = "IDLE"
current_posture = "stand"

def change_state(new_state, point_id=None):
    """更新机器人状态并记录日志，并主动推送到 phone 节点"""
    global robot_state, current_target_point_id
    robot_state = new_state
    current_target_point_id = point_id
    logging.info(f"\033[1;33m[状态变更]\033[0m -> \033[1;32m{robot_state}\033[0m (Point: {point_id})")
    
    # 主动推送状态给 phone 节点
    push_msg = {
        "from": "arm",
        "to": "phone",
        "type": "slam",
        "topic": "nav_status",
        "msg": {
            "state": robot_state,
            "current_point_id": current_target_point_id,
            "ros_enabled": True
        }
    }
    phone_writer = clients.get("phone")
    if phone_writer:
        try:
            phone_writer.write((json.dumps(push_msg) + '\n').encode('utf-8'))
        except:
            pass

def change_arm_state(new_state, action_id=None):
    """更新手臂状态并记录日志"""
    global arm_state
    arm_state = new_state
    logging.info(f"\033[1;33m[手臂状态变更]\033[0m -> \033[1;32m{arm_state}\033[0m (Action: {action_id})")

def get_local_ip():
    """获取本机局域网 IP 地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

def run_http_server(port=8080):
    """启动后台 HTTP 文件服务"""
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # 隐藏大量的 HTTP 请求明细日志，保持控制台整洁

    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, QuietHandler)
    logging.info(f"\033[1;35mHTTP 地图服务启动\033[0m: http://{get_local_ip()}:{port}")
    httpd.serve_forever()

async def handle_client(reader, writer):
    global current_posture
    addr = writer.get_extra_info('peername')
    logging.info(f"建立物理连接: {addr}")
    current_node = None

    try:
        while True:
            data = await reader.readline()
            if not data:
                break

            msg_str = data.decode('utf-8').strip()
            if not msg_str:
                continue

            logging.debug(f"[{current_node or addr}] 接收原始报文: {msg_str}")

            try:
                msg_json = json.loads(msg_str)
                from_node = msg_json.get("from")
                to_node = msg_json.get("to")

                # 提取 from 字段，动态绑定当前连接的节点标识。
                if from_node and current_node != from_node:
                    current_node = from_node
                    clients[current_node] = writer
                    logging.info(f"\033[1;32m节点注册成功\033[0m: {current_node} -> {addr}")

                # 丢弃缺少目标节点的无效报文。
                if not to_node:
                    logging.warning(f"异常报文，缺少 'to' 字段: {msg_str}")
                    continue

                # 拦截目标为 arm 的报文，交由本地业务处理。
                if to_node == "arm":
                    raw_type = msg_json.get('type', '')
                    topic = msg_json.get('topic', '')

                    # 兼容 "type/topic" 格式，例如 "slam/set_position"
                    if not topic and '/' in raw_type:
                        msg_type, topic = raw_type.split('/', 1)
                    else:
                        msg_type = raw_type

                    # 统一响应类型，兼容 webrtc 桥接模式。
                    resp_type = msg_type
                    logging.info(f"ARM 业务逻辑处理: type={msg_type}, topic={topic}")

                    response = None
                    msg_body = msg_json.get("msg", {})

                    # 1. 构造通用心跳回执。
                    if topic == "connection" or msg_type == "heartbeat":
                        response = {
                            "from": "arm",
                            "to": from_node,
                            "type": "heartbeat",
                            "topic": "connection",
                            "msg": {"receive": "true", "status": "ok"}
                        }

                    # 2. 导航核心状态 (Polling)
                    elif topic == "get_status" or msg_type == "navigation":
                        response = {
                            "from": "arm", "to": from_node, "type": resp_type, "topic": "get_status",
                            "msg": {
                                "state": robot_state,
                                "arm_state": arm_state,
                                "current_posture": current_posture,
                                "current_point_id": current_target_point_id,
                                "ros_enabled": True
                            }
                        }

                    # 3. SLAM 相关接口 (根据 navigation_api.md 更新)
                    elif msg_type == "slam" or topic in ["start_point", "stop_position", "stop_all", "get_position", "set_position", "point_query_all", "point_list", "point_add", "point_delete_by_pid", "route_query_all", "route_add", "route_delete_by_rid", "map_config", "get_scan", "point_cloud", "get_global_path", "get_local_path", "start_mapping", "stop_mapping", "cancel_navigation", "go_to_dock"]:
                        if topic in ["point_query_all", "point_list"]:
                            response = {
                                "from": "arm", "to": from_node, "type": resp_type, "topic": topic,
                                "msg": endpoints
                            }
                        elif topic == "point_add":
                            pid = msg_body.get("point_id")
                            found_p = next((p for p in endpoints if p["point_id"] == pid), None)
                            if found_p:
                                found_p.update(msg_body)
                                res_msg = found_p
                            else:
                                new_point = {
                                    "id": len(endpoints) + 1,
                                    "point_id": pid or f"point_{uuid.uuid4().hex[:8]}",
                                    "name": msg_body.get("name", "未命名"),
                                    "x": msg_body.get("x", 0.0),
                                    "y": msg_body.get("y", 0.0),
                                    "yaw": msg_body.get("yaw", 0.0),
                                    "broadcastContent": msg_body.get("broadcastContent", ""),
                                    "playOnArrival": msg_body.get("playOnArrival", True),
                                    "photoOnArrival": msg_body.get("photoOnArrival", False),
                                    "pointType": msg_body.get("pointType", 0),
                                    "status": "可达",
                                    "isReachable": True,
                                    "stayTime": msg_body.get("stayTime", 0.0),
                                    "needRotate": msg_body.get("needRotate", False)
                                }
                                endpoints.append(new_point)
                                res_msg = new_point
                            response = {
                                "from": "arm", "to": from_node, "type": resp_type, "topic": "point_add",
                                "msg": {"receive": "true", "data": res_msg}
                            }
                        elif topic == "point_delete_by_pid":
                            pid = msg_body.get("point_id")
                            original_len = len(endpoints)
                            endpoints[:] = [p for p in endpoints if p["point_id"] != pid]
                            if len(endpoints) < original_len:
                                response = {"from": "arm", "to": from_node, "type": resp_type, "topic": "point_delete_by_pid", "msg": {"receive": "true", "point_id": pid}}
                            else:
                                response = {"from": "arm", "to": from_node, "type": resp_type, "topic": "point_delete_by_pid", "msg": {"receive": "error", "message": f"点位 {pid} 不存在"}}
                        
                        elif topic == "route_query_all":
                            response = {
                                "from": "arm", "to": from_node, "type": resp_type, "topic": topic,
                                "msg": routes
                            }
                        elif topic == "route_add":
                            rid = msg_body.get("route_id")
                            found_r = next((r for r in routes if r["route_id"] == rid), None)
                            if found_r:
                                found_r.update(msg_body)
                                found_r["updateTime"] = int(time.time() * 1000)
                                res_msg = found_r
                            else:
                                new_route = {
                                    "id": len(routes) + 1,
                                    "route_id": rid or f"route_{uuid.uuid4().hex[:8]}",
                                    "route_name": msg_body.get("route_name", "未命名路线"),
                                    "description": msg_body.get("description", ""),
                                    "points": msg_body.get("points", []),
                                    "pointCount": len(msg_body.get("points", [])),
                                    "isActive": True,
                                    "createTime": int(time.time() * 1000),
                                    "updateTime": int(time.time() * 1000),
                                    "loopCount": msg_body.get("loopCount", 1)
                                }
                                routes.append(new_route)
                                res_msg = new_route
                            response = {
                                "from": "arm", "to": from_node, "type": resp_type, "topic": "route_add",
                                "msg": {"receive": "true", "data": res_msg}
                            }
                        elif topic == "route_delete_by_rid":
                            rid = msg_body.get("route_id")
                            original_len = len(routes)
                            routes[:] = [r for r in routes if r["route_id"] != rid]
                            if len(routes) < original_len:
                                response = {"from": "arm", "to": from_node, "type": resp_type, "topic": "route_delete_by_rid", "msg": {"receive": "true", "route_id": rid}}
                            else:
                                response = {"from": "arm", "to": from_node, "type": resp_type, "topic": "route_delete_by_rid", "msg": {"receive": "error", "message": "路线不存在"}}
                        
                        elif topic == "start_point":
                            pid = msg_body.get("point_id")
                            # 更新全局状态
                            change_state("NAVIGATING", pid)

                            # 确定目标位置，增加类型转换处理字符串输入
                            try:
                                target_x = float(msg_body.get("x")) if msg_body.get("x") is not None else None
                                target_y = float(msg_body.get("y")) if msg_body.get("y") is not None else None
                                target_yaw = float(msg_body.get("yaw")) if msg_body.get("yaw") is not None else None
                            except (ValueError, TypeError):
                                target_x, target_y, target_yaw = None, None, None

                            # 如果提供了 point_id 且缺少坐标，则从预设点位中查找
                            if pid and (target_x is None or target_y is None):
                                target_point = next((p for p in endpoints if p["point_id"] == pid), None)
                                if target_point:
                                    target_x = float(target_point.get("x", 0.0))
                                    target_y = float(target_point.get("y", 0.0))
                                    target_yaw = float(target_point.get("yaw", 0.0))

                            response = {
                                "from": "arm", "to": from_node, "type": resp_type,
                                "topic": "start_point", "msg": {"receive": "true", "point_id": pid, "message": "已开始平滑导航模拟"}
                            }

                            # 模拟平滑移动任务
                            async def simulate_navigation(tx, ty, tyaw, target_pid):
                                if tx is None or ty is None:
                                    logging.error("\033[1;31m[导航失败]\033[0m 目标坐标无效")
                                    return
                                
                                start_x, start_y, start_yaw = robot_position["x"], robot_position["y"], robot_position["yaw"]
                                duration = 5.0  # 模拟移动持续 5 秒
                                steps = 50      # 10Hz 更新频率
                                interval = duration / steps

                                logging.info(f"\033[1;35m[导航开始]\033[0m 从 ({start_x}, {start_y}) 前往 ({tx}, {ty})")

                                for i in range(1, steps + 1):
                                    if robot_state != "NAVIGATING":
                                        logging.info("\033[1;31m[导航中断]\033[0m 任务被取消或急停")
                                        return
                                    await asyncio.sleep(interval)
                                    ratio = i / steps
                                    # 线性插值计算当前位置
                                    robot_position["x"] = round(start_x + (tx - start_x) * ratio, 3)
                                    robot_position["y"] = round(start_y + (ty - start_y) * ratio, 3)
                                    if tyaw is not None:
                                        robot_position["yaw"] = round(start_yaw + (tyaw - start_yaw) * ratio, 3)

                                # 到达后推送通知
                                push_msg = {
                                    "from": "arm", "to": from_node, "type": resp_type,
                                    "topic": "arrived",
                                    "msg": {"receive": "true", "point_id": target_pid}
                                }
                                try:
                                    writer.write((json.dumps(push_msg) + '\n').encode('utf-8'))
                                    await writer.drain()
                                    logging.info(f"\033[1;35m[导航到达]\033[0m 已到达: {target_pid or '目标点'}")
                                    change_state("NAV_READY")
                                except:
                                    pass

                            asyncio.create_task(simulate_navigation(target_x, target_y, target_yaw, pid))

                        elif topic == "stop_position" or topic == "cancel_navigation":
                            change_state("NAV_READY")
                            response = {"from": "arm", "to": from_node, "type": resp_type, "topic": topic, "msg": {"receive": "true", "message": "任务已停止"}}
                        elif topic == "stop_all":
                            change_state("EMERGENCY_STOP")
                            change_arm_state("IDLE")
                            response = {"from": "arm", "to": from_node, "type": resp_type, "topic": "stop_all", "msg": {"receive": "true", "message": "急停已触发"}}
                        elif topic == "go_to_dock":
                            change_state("NAVIGATING", "dock")
                            response = {"from": "arm", "to": from_node, "type": resp_type, "topic": "go_to_dock", "msg": {"receive": "true", "message": "正在回充"}}
                            # 模拟回充导航 (到 0,0)
                            asyncio.create_task(simulate_navigation(0.0, 0.0, 0.0, "dock"))

                        elif topic == "map_config":
                            local_ip = get_local_ip()
                            response = {
                                "from": "arm", "to": from_node, "type": resp_type, "topic": "map_config",
                                "msg": {
                                    "receive": "true",
                                    "image": f"http://{local_ip}:8080/maps.pgm",
                                    "resolution": 0.050000,
                                    "origin": [-23.750000, -21.400000, 0],
                                    "negate": 0,
                                    "occupied_thresh": 0.65,
                                    "free_thresh": 0.196
                                }
                            }
                        elif topic in ["get_scan", "point_cloud"]:
                            # 模拟点云数据：在机器人当前位置附近生成 60 个随机偏移点，模拟激光雷达扫描
                            scan_points = [
                                {
                                    "x": round(robot_position["x"] + random.uniform(-5.0, 5.0), 3),
                                    "y": round(robot_position["y"] + random.uniform(-5.0, 5.0), 3)
                                }
                                for _ in range(60)
                            ]
                            response = {
                                "from": "arm", "to": from_node, "type": resp_type, "topic": topic,
                                "msg": scan_points
                            }
                        elif topic in ["get_global_path", "get_local_path"]:
                            # 模拟路径数据：从当前位置延伸的一串点
                            path_points = [
                                {
                                    "x": round(robot_position["x"] + i * 0.2, 3),
                                    "y": round(robot_position["y"] + i * 0.1, 3)
                                }
                                for i in range(15)
                            ]
                            response = {
                                "from": "arm", "to": from_node, "type": resp_type, "topic": topic,
                                "msg": path_points
                            }
                        elif topic in ["get_position", "getPositionh"]:
                            response = {
                                "from": "arm", "to": from_node, "type": resp_type, "topic": topic,
                                "msg": {"receive": "true", "x": robot_position["x"], "y": robot_position["y"], "yaw": robot_position["yaw"]}
                            }
                        elif topic in ["set_position", "setPosition"]:
                            try:
                                change_state("RELOCALIZING")
                                robot_position["x"] = float(msg_body.get("x", 0.0))
                                robot_position["y"] = float(msg_body.get("y", 0.0))
                                robot_position["yaw"] = float(msg_body.get("yaw", 0.0))
                                
                                # 模拟重定位过程，2秒后恢复 NAV_READY
                                async def finish_relocalization():
                                    await asyncio.sleep(2.0)
                                    if robot_state == "RELOCALIZING":
                                        change_state("NAV_READY")
                                
                                asyncio.create_task(finish_relocalization())
                                response = {"from": "arm", "to": from_node, "type": resp_type, "topic": topic, "msg": {"receive": "true"}}
                            except Exception as e:
                                response = {"from": "arm", "to": from_node, "type": resp_type, "topic": "error", "msg": {"receive": "error", "message": f"位置格式错误: {e}"}}

                        elif topic == "start_mapping":
                            change_state("MAPPING")
                            response = {"from": "arm", "to": from_node, "type": resp_type, "topic": "start_mapping", "msg": {"receive": "true", "message": "进入扫图模式"}}
                        elif topic == "stop_mapping":
                            change_state("NAV_READY")
                            response = {"from": "arm", "to": from_node, "type": resp_type, "topic": "stop_mapping", "msg": {"receive": "true", "message": "退出扫图模式"}}

                    # 3. 运行状态查询 (Type: offline)
                    elif msg_type == "offline":
                        if topic == "get_state":
                            response = {
                                "from": "arm", "to": from_node, "type": "offline", "topic": "get_state",
                                "msg": {
                                    "receive": "true",
                                    "status": "RUNNING",
                                    "mode": "AUTO",
                                    "battery": 85
                                }
                            }

                    # 4. 语音播报 (Type: state)
                    elif msg_type == "state":
                        if topic == "tts":
                            text = msg_body.get("text", "")
                            logging.info(f"\033[1;34m[语音播报]\033[0m: {text}")
                            response = {
                                "from": "arm", "to": from_node, "type": "state", "topic": "tts",
                                "msg": {"receive": "true", "message": f"正在播报: {text}"}
                            }

                    # 5. 手臂动作与姿态 (支持 get/set 指令)
                    elif topic in ["get_arm", "get_posture", "set_arm", "set_posture", "play_arm", "play_posture", "stop_arm"] or msg_type in ["arm", "webrtc"]:
                        if topic == "get_arm":
                            response = {
                                "from": "arm", "to": from_node, "type": msg_type, "topic": "get_arm",
                                "msg": arm_actions
                            }
                        elif topic == "get_posture":
                            response = {
                                "from": "arm", "to": from_node, "type": msg_type, "topic": "get_posture",
                                "msg": postures
                            }
                        elif topic in ["set_arm", "play_arm"]:
                            arm_id = msg_body.get("id") or msg_body.get("arm_id")
                            action = next((a for a in arm_actions if a["id"] == arm_id), None)
                            dur = action["time"] if action else 2.0
                            
                            change_arm_state("BUSY", arm_id)
                            response = {
                                "from": "arm", "to": from_node, "type": msg_type, "topic": topic,
                                "msg": {"receive": "true", "id": arm_id, "message": "手臂动作执行中"}
                            }
                            
                            async def simulate_arm_action(aid, d):
                                await asyncio.sleep(d)
                                if arm_state == "BUSY":
                                    change_arm_state("IDLE")
                                    # 推送完成通知
                                    push = {"from": "arm", "to": from_node, "type": msg_type, "topic": "arm_action_finished", "msg": {"receive": "true", "id": aid}}
                                    try:
                                        writer.write((json.dumps(push) + '\n').encode('utf-8'))
                                        await writer.drain()
                                    except: pass
                            
                            asyncio.create_task(simulate_arm_action(arm_id, dur))

                        elif topic in ["set_posture", "play_posture"]:
                            posture_id = msg_body.get("id") or msg_body.get("posture_id") or msg_body.get("posture_name")
                            # 尝试匹配 technical_name
                            target_p = next((p for p in postures if str(p["id"]) == str(posture_id) or p["technical_name"] == posture_id), None)
                            if target_p:
                                current_posture = target_p["technical_name"]
                            
                            response = {
                                "from": "arm", "to": from_node, "type": msg_type, "topic": topic,
                                "msg": {"receive": "true", "id": posture_id, "message": f"姿态切换至: {current_posture}"}
                            }
                        elif topic == "stop_arm":
                            change_arm_state("IDLE")
                            response = {"from": "arm", "to": from_node, "type": msg_type, "topic": "stop_arm", "msg": {"receive": "true"}}

                    # 6. 其他硬件控制 (Type: chassis / sensor)
                    elif msg_type == "chassis":
                        if topic == "cmd_vel":
                            vx = msg_body.get("x", 0.0)
                            vaz = msg_body.get("yaw", 0.0)
                            logging.info(f"\033[1;36m[底盘控制]\033[0m 线速度: {vx}, 角速度: {vaz}")
                            response = {"from": "arm", "to": from_node, "type": "chassis", "topic": "cmd_vel", "msg": {"receive": "true"}}

                    # 保持旧接口兼容性 (可选)
                    elif msg_type == "location":
                        # 转换并重定向到 slam 逻辑或直接处理
                        if topic == "get_endpoints":
                            response = {"from": "arm", "to": from_node, "type": "location", "topic": "get_endpoints", "msg": endpoints}
                    
                    if response:
                        if "id" not in response and "id" in msg_json:
                            response["id"] = msg_json["id"]
                        resp_str = json.dumps(response)
                        writer.write((resp_str + '\n').encode('utf-8'))
                        await writer.drain()
                        logging.info(f"\033[1;32m[发送响应]\033[0m -> {from_node}: {resp_str}")

                # 匹配目标节点，执行报文的透明转发。
                else:
                    target_writer = clients.get(to_node)
                    if target_writer:
                        logging.info(f"\033[1;34m[路由转发]\033[0m: {from_node} -> {to_node}, topic: {msg_json.get('topic')}")
                        target_writer.write((msg_str + '\n').encode('utf-8'))
                        await target_writer.drain()
                    else:
                        logging.warning(f"目标节点 {to_node} 离线，报文丢弃")

            except json.JSONDecodeError:
                logging.error(f"JSON 格式错误，无法解析: {msg_str}")


    except Exception as e:
        logging.error(f"连接异常断开 [{addr}]: {e}")

    finally:
        # 清除失效的节点映射。
        if current_node and clients.get(current_node) == writer:
            del clients[current_node]
            logging.info(f"注销节点: {current_node}")

        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

        logging.info(f"销毁物理连接: {addr}")


async def main():
    # 1. 启动 HTTP 地图文件服务 (端口 8080)
    threading.Thread(target=run_http_server, args=(8080,), daemon=True).start()

    # 2. 启动异步 TCP 路由服务 (端口 9002)
    server = await asyncio.start_server(handle_client, '0.0.0.0', 9002)
    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    logging.info(f"Mock ARM 路由服务启动完毕，监听地址: {addrs}")

    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("进程结束")
