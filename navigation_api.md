# 机器人导览接口文档 (Navigation API)

本文档描述了机器人导览系统、路径管理及位姿控制的 JSON 接口协议。所有消息均通过 TCP 或 WebSocket 以 JSON 字符串形式传输。

## 1. 基础消息格式

- **发送格式 (Request)**:
  ```json
  {
    "type": "接口分类 (如 slam, state, navigation)",
    "topic": "具体指令名称",
    "msg": { "参数对象" }
  }
  ```

- **接收格式 (Response)**:
  ```json
  {
    "type": "接口分类",
    "topic": "指令名称",
    "msg": {
      "receive": "true/error",
      "message": "错误描述 (可选)",
      ...其他数据
    }
  }
  ```

---

## 2. 导览点管理 (Point Management)

### 2.1 获取所有导览点
- **Type**: `slam`
- **Topic**: `point_query_all` 或 `point_list` (不传 msg 时)
- **Request**: `{"type": "slam", "topic": "point_query_all", "msg": {导览点实体 1，导览点实体 2}}`
- **Response**: 返回点位对象数组。

### 2.2 添加或增量更新 (Upsert)
- **Type**: `slam`
- **Topic**: `point_add`
- **说明**: **添加与更新共用此接口**。若 `point_id` 已存在则覆盖更新，不存在则新建。此操作为“增量”性质，不会影响数据库中其他的点位。
- **Request**: `{"type": "slam", "topic": "point_add", "msg": {"point_id": 1002, "name": "会议室", "x": 5.0, "y": -2.0, "yaw": 0.0}}`
- 
### 2.5 删除导览点
- **Type**: `slam`
- **Topic**: `point_delete_by_pid`
- **Request**: `{"type": "slam", "topic": "point_delete_by_pid", "msg": {"point_id": 1002}}`

---

## 3. 路线管理 (Route Management)

### 3.1 查询所有路线
- **Type**: `slam`
- **Topic**: `route_query_all`
- **Response**: 返回路线对象数组（含 points ID 列表）。

### 3.2 添加/更新路线 (Upsert)
- **Type**: `slam`
- **Topic**: `route_add`
- **说明**: 添加或更新路线。如果 `route_id` 已存在则更新点位序列，不存在则新建。
- **Request**: `{"type": "slam", "topic": "route_add", "msg": {"route_id": 2001, "route_name": "演示路线", "points": [1001, 1002]}}`

### 3.3 删除路线
- **删除单条**: `{"type": "slam", "topic": "route_delete_by_rid", "msg": {"route_id": 2001}}`

---

## 4. 导览执行 (Navigation Execution)

### 4.1 去某个点 (Start Navigation)
- **Type**: `slam`
- **Topic**: `start_point`
- **说明**: 核心导航接口。支持按点位 ID 或直接给定坐标。
- **Request**: 
  ```json
  {
    "type": "slam",
    "topic": "start_point",
    "msg": {
      "point_id": "1001",
      "x": 1.25, 
      "y": 0.5,
      "yaw": 1.57
    }
  }
  ```

### 4.3 停止与急停
- **停止任务**: `{"type": "slam", "topic": "stop_position", "msg": {}}`
- **急停**: `{"type": "slam", "topic": "stop_all", "msg": {}}`

### 4.4 到达通知 (Server Push)
- **说明**: 机器人到达目的地后，服务端会主动推送此消息。
- **Type**: `slam`
- **Topic**: `arrived`
- **Message**:
  ```json
  {
    "type": "slam",
    "topic": "arrived",
    "msg": { "point_id": "1001" }
  }
  ```

---

## 5. 位姿与状态查询

### 5.1 当前位姿与状态
- **获取坐标**: `{"type": "slam", "topic": "get_position", "msg": {}}`
- **重定位**: `{"type": "slam", "topic": "set_position", "msg": {"x": 0.0, "y": 0.0, "yaw": 0.0}}`
- **运行状态**: `{"type": "offline", "topic": "get_state", "msg": {}}`

### 5.2 语音播报 (TTS)
- **Type**: `state`
- **Topic**: `tts`
- **Request**: `{"type": "state", "topic": "tts", "msg": {"text": "开始导览"}}`
