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

# 模拟机器人位置数据
robot_position = {
    "x": 0.0,
    "y": 0.0,
    "yaw": 0.0
}

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

                    # 2. SLAM 相关接口 (根据 navigation_api.md 更新)
                    elif msg_type == "slam":
                        if topic in ["point_query_all", "point_list"]:
                            response = {
                                "from": "arm", "to": from_node, "type": "slam", "topic": topic,
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
                                "from": "arm", "to": from_node, "type": "slam", "topic": "point_add",
                                "msg": {"receive": "true", "data": res_msg}
                            }
                        elif topic == "point_delete_by_pid":
                            pid = msg_body.get("point_id")
                            original_len = len(endpoints)
                            endpoints[:] = [p for p in endpoints if p["point_id"] != pid]
                            if len(endpoints) < original_len:
                                response = {"from": "arm", "to": from_node, "type": "slam", "topic": "point_delete_by_pid", "msg": {"receive": "true", "point_id": pid}}
                            else:
                                response = {"from": "arm", "to": from_node, "type": "slam", "topic": "point_delete_by_pid", "msg": {"receive": "error", "message": f"点位 {pid} 不存在"}}
                        
                        elif topic == "route_query_all":
                            response = {
                                "from": "arm", "to": from_node, "type": "slam", "topic": topic,
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
                                "from": "arm", "to": from_node, "type": "slam", "topic": "route_add",
                                "msg": {"receive": "true", "data": res_msg}
                            }
                        elif topic == "route_delete_by_rid":
                            rid = msg_body.get("route_id")
                            original_len = len(routes)
                            routes[:] = [r for r in routes if r["route_id"] != rid]
                            if len(routes) < original_len:
                                response = {"from": "arm", "to": from_node, "type": "slam", "topic": "route_delete_by_rid", "msg": {"receive": "true", "route_id": rid}}
                            else:
                                response = {"from": "arm", "to": from_node, "type": "slam", "topic": "route_delete_by_rid", "msg": {"receive": "error", "message": "路线不存在"}}
                        
                        elif topic == "start_point":
                            pid = msg_body.get("point_id")
                            response = {
                                "from": "arm", "to": from_node, "type": "slam",
                                "topic": "start_point", "msg": {"receive": "true", "point_id": pid, "message": "已开始导航"}
                            }
                            # 模拟导航到达通知
                            async def delayed_point_push():
                                await asyncio.sleep(3)
                                push_msg = {
                                    "from": "arm", "to": from_node, "type": "slam",
                                    "topic": "arrived",
                                    "msg": {"receive": "true", "point_id": pid}
                                }
                                writer.write((json.dumps(push_msg) + '\n').encode('utf-8'))
                                await writer.drain()
                                logging.info(f"\033[1;35m[导航到达通知]\033[0m -> {from_node}: {push_msg}")
                            asyncio.create_task(delayed_point_push())

                        elif topic == "stop_position":
                            response = {"from": "arm", "to": from_node, "type": "slam", "topic": "stop_position", "msg": {"receive": "true", "message": "任务已停止"}}
                        elif topic == "stop_all":
                            response = {"from": "arm", "to": from_node, "type": "slam", "topic": "stop_all", "msg": {"receive": "true", "message": "急停已触发"}}

                        elif topic == "map_config":
                            local_ip = get_local_ip()
                            response = {
                                "from": "arm", "to": from_node, "type": "slam", "topic": "map_config",
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
                                "from": "arm", "to": from_node, "type": "slam", "topic": topic,
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
                                "from": "arm", "to": from_node, "type": "slam", "topic": topic,
                                "msg": path_points
                            }
                        elif topic in ["get_position", "getPositionh"]:
                            response = {
                                "from": "arm", "to": from_node, "type": "slam", "topic": topic,
                                "msg": {"receive": "true", "x": robot_position["x"], "y": robot_position["y"], "yaw": robot_position["yaw"]}
                            }
                        elif topic in ["set_position", "setPosition"]:
                            try:
                                robot_position["x"] = float(msg_body.get("x", 0.0))
                                robot_position["y"] = float(msg_body.get("y", 0.0))
                                robot_position["yaw"] = float(msg_body.get("yaw", 0.0))
                                response = {"from": "arm", "to": from_node, "type": "slam", "topic": topic, "msg": {"receive": "true"}}
                            except:
                                response = {"from": "arm", "to": from_node, "type": "slam", "topic": "error", "msg": {"receive": "error", "message": "位置格式错误"}}

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
