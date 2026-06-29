import asyncio
import json
import logging
import uuid
import socket
import threading
import time
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
        "pointId": "point_1",
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
        "pointId": "point_2",
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
        "routeId": "route_001",
        "name": "每日巡检路线",
        "description": "覆盖办公区和休息区的例行巡检",
        "pointIds": "point_1,point_2",
        "pointCount": 2,
        "isActive": True,
        "createTime": int(time.time() * 1000),
        "updateTime": int(time.time() * 1000),
        "loopCount": 2
    }
]

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
                    topic = msg_json.get('topic')
                    msg_type = msg_json.get('type')
                    logging.info(f"ARM 业务逻辑处理: type={msg_type}, topic={topic}")

                    response = None

                    # 1. 构造通用心跳回执。
                    if topic == "connection":
                        response = {
                            "from": "arm",
                            "to": from_node,
                            "type": "heartbeat",
                            "topic": "connection",
                            "msg": {"status": "ok"}
                        }

                    # 2. 巡检点接口处理 (location type)
                    elif msg_type == "location":
                        if topic == "get_endpoints":
                            response = {
                                "from": "arm",
                                "to": from_node,
                                "op": "location",
                                "topic": "get_endpoints",
                                "status": "ok",
                                "msg": endpoints
                            }
                        elif topic == "add_endpoint":
                            new_msg = msg_json.get("msg", {})
                            new_point = {
                                "id": len(endpoints) + 1,
                                "pointId": f"point_{uuid.uuid4().hex[:8]}",
                                "name": new_msg.get("name", "未命名"),
                                "x": new_msg.get("position", {}).get("x", 0.0),
                                "y": new_msg.get("position", {}).get("y", 0.0),
                                "yaw": new_msg.get("position", {}).get("yaw", 0.0),
                                "broadcastContent": new_msg.get("broadcastContent", ""),
                                "playOnArrival": new_msg.get("playOnArrival", True),
                                "photoOnArrival": new_msg.get("photoOnArrival", False),
                                "pointType": new_msg.get("pointType", 0),
                                "status": "可达",
                                "isReachable": True,
                                "stayTime": 0.0,
                                "needRotate": False
                            }
                            endpoints.append(new_point)
                            response = {
                                "from": "arm",
                                "to": from_node,
                                "op": "location",
                                "topic": "add_endpoint",
                                "status": "ok",
                                "msg": new_point
                            }
                        elif topic == "update_endpoint":
                            update_msg = msg_json.get("msg", {})
                            pid = update_msg.get("pointId")
                            found_p = next((p for p in endpoints if p["pointId"] == pid), None)
                            if found_p:
                                found_p.update({
                                    "name": update_msg.get("name", found_p["name"]),
                                    "broadcastContent": update_msg.get("broadcastContent", found_p["broadcastContent"]),
                                    "playOnArrival": update_msg.get("playOnArrival", found_p["playOnArrival"]),
                                    "photoOnArrival": update_msg.get("photoOnArrival", found_p["photoOnArrival"]),
                                    "pointType": update_msg.get("pointType", found_p["pointType"]),
                                })
                                if "position" in update_msg:
                                    pos = update_msg["position"]
                                    found_p["x"] = pos.get("x", found_p["x"])
                                    found_p["y"] = pos.get("y", found_p["y"])
                                    found_p["yaw"] = pos.get("yaw", found_p["yaw"])
                                response = {
                                    "from": "arm",
                                    "to": from_node,
                                    "op": "location",
                                    "topic": "update_endpoint",
                                    "status": "ok",
                                    "msg": found_p
                                }
                            else:
                                response = {"from": "arm", "to": from_node, "op": "location", "topic": "error", "status": "error", "msg": {"errorMessage": f"点位 {pid} 不存在"}}
                        elif topic == "delete_endpoint":
                            pid = msg_json.get("msg", {}).get("pointId")
                            original_len = len(endpoints)
                            endpoints[:] = [p for p in endpoints if p["pointId"] != pid]
                            if len(endpoints) < original_len:
                                response = {"from": "arm", "to": from_node, "op": "location", "topic": "delete_endpoint", "status": "ok", "msg": {"pointId": pid}}
                            else:
                                response = {"from": "arm", "to": from_node, "op": "location", "topic": "error", "status": "error", "msg": {"errorMessage": f"点位 {pid} 不存在"}}
                        elif topic == "start_point":
                            pid = msg_json.get("msg", {}).get("pointId")
                            response = {"from": "arm", "to": from_node, "op": "location", "topic": "start_point", "status": "ok", "msg": {"pointId": pid, "message": "已开始导航"}}

                    # 3. 路线管理接口 (2dpath type)
                    elif msg_type == "2dpath":
                        if topic == "get_routes":
                            response = {
                                "from": "arm", "to": from_node, "op": "2dpath",
                                "topic": "get_routes", "status": "ok", "msg": routes
                            }
                        elif topic == "add_route":
                            new_msg = msg_json.get("msg", {})
                            points_list = new_msg.get("points", [])
                            new_route = {
                                "id": len(routes) + 1,
                                "routeId": f"route_{uuid.uuid4().hex[:8]}",
                                "name": new_msg.get("name", "未命名路线"),
                                "description": new_msg.get("description", ""),
                                "pointIds": ",".join(points_list),
                                "pointCount": len(points_list),
                                "isActive": new_msg.get("isActive", True),
                                "createTime": int(time.time() * 1000),
                                "updateTime": int(time.time() * 1000),
                                "loopCount": new_msg.get("loopCount", 1)
                            }
                            routes.append(new_route)
                            response = {"from": "arm", "to": from_node, "op": "2dpath", "topic": "add_route", "status": "success", "msg": new_route}
                        elif topic == "update_route":
                            update_msg = msg_json.get("msg", {})
                            rid = update_msg.get("routeId")
                            found_r = next((r for r in routes if r["routeId"] == rid), None)
                            if found_r:
                                points_list = update_msg.get("points", [])
                                found_r.update({
                                    "name": update_msg.get("name", found_r["name"]),
                                    "description": update_msg.get("description", found_r["description"]),
                                    "isActive": update_msg.get("isActive", found_r["isActive"]),
                                    "loopCount": update_msg.get("loopCount", found_r["loopCount"]),
                                    "updateTime": int(time.time() * 1000)
                                })
                                if "points" in update_msg:
                                    found_r["pointIds"] = ",".join(points_list)
                                    found_r["pointCount"] = len(points_list)
                                response = {"from": "arm", "to": from_node, "op": "2dpath", "topic": "update_route", "status": "success", "msg": found_r}
                            else:
                                response = {"from": "arm", "to": from_node, "op": "2dpath", "topic": "error", "status": "error", "msg": "路线不存在"}
                        elif topic == "delete_route":
                            rid = msg_json.get("msg", {}).get("routeId")
                            original_len = len(routes)
                            routes[:] = [r for r in routes if r["routeId"] != rid]
                            if len(routes) < original_len:
                                response = {"from": "arm", "to": from_node, "op": "2dpath", "topic": "delete_route", "status": "success", "msg": {"routeId": rid}}
                            else:
                                response = {"from": "arm", "to": from_node, "op": "2dpath", "topic": "error", "status": "error", "msg": "路线不存在"}

                    # 4. 导航控制接口 (navigation type)
                    elif msg_type == "navigation":
                        if topic == "start_route":
                            rid = msg_json.get("msg", {}).get("routeId")
                            response = {"from": "arm", "to": from_node, "op": "navigation", "topic": "start_route", "status": "success", "msg": {"routeId": rid}}
                            # 模拟异步通知：1秒后发送完成通知
                            async def delayed_push():
                                await asyncio.sleep(2)
                                push_msg = {
                                    "from": "arm", "to": from_node, "op": "navigation",
                                    "topic": "status_push", "status": "ok",
                                    "msg": {"state": "COMPLETED", "routeId": rid}
                                }
                                writer.write((json.dumps(push_msg) + '\n').encode('utf-8'))
                                await writer.drain()
                                logging.info(f"\033[1;35m[异步通知]\033[0m -> {from_node}: {push_msg}")
                            asyncio.create_task(delayed_push())
                        elif topic == "get_status":
                            response = {
                                "from": "arm", "to": from_node, "op": "navigation",
                                "topic": "get_status", "status": "ok",
                                "msg": {"state": "IDLE", "routeId": ""}
                            }

                    # 5. slam 接口处理 (地图配置)
                    elif msg_type == "slam":
                        if topic == "map_config":
                            local_ip = get_local_ip()
                            response = {
                                "from": "arm",
                                "to": from_node,
                                "type": "slam",
                                "topic": "map_config",
                                "status": "ok",
                                "msg": {
                                    "image": f"http://{local_ip}:8080/maps.pgm",
                                    "resolution": 0.050000,
                                    "origin": [-23.750000, -21.400000, 0],
                                    "negate": 0,
                                    "occupied_thresh": 0.65,
                                    "free_thresh": 0.196
                                }
                            }

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

        # 捕获并忽略失效 Socket 引引发的二次关闭异常。
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
