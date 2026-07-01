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
- **Topic**: `point_query_all` 或 `point_list`
- **Request**: `{"type": "slam", "topic": "point_query_all", "msg": {}}`
- **Response**: 
  ```json
  {
    "type": "slam",
    "topic": "point_query_all",
    "msg": [
      {"point_id": "1001", "name": "充电桩", "x": 0.0, "y": 0.0, "yaw": 0.0},
      {"point_id": "1002", "name": "会议室", "x": 5.0, "y": -2.0, "yaw": 0.0}
    ]
  }
  ```

### 2.2 添加或增量更新 (Upsert)
- **Type**: `slam`
- **Topic**: `point_add`
- **说明**: **添加与更新共用此接口**。若 `point_id` 已存在则覆盖更新，不存在则新建。
- **Request**: `{"type": "slam", "topic": "point_add", "msg": {"point_id": "1002", "name": "会议室", "x": 5.0, "y": -2.0, "yaw": 0.0}}`

### 2.3 删除导览点
- **Type**: `slam`
- **Topic**: `point_delete_by_pid`
- **Request**: `{"type": "slam", "topic": "point_delete_by_pid", "msg": {"point_id": "1002"}}`

---

## 3. 路线管理 (Route Management)

### 3.1 查询所有路线
- **Type**: `slam`
- **Topic**: `route_query_all`
- **Request**: `{"type": "slam", "topic": "route_query_all", "msg": {}}`
- **Response**: 
  ```json
  {
    "type": "slam",
    "topic": "route_query_all",
    "msg": [
      {"route_id": "2001", "route_name": "巡检路线", "points": ["1001", "1002"]}
    ]
  }
  ```

### 3.2 添加/更新路线 (Upsert)
- **Type**: `slam`
- **Topic**: `route_add`
- **说明**: 添加或更新路线。如果 `route_id` 已存在则更新点位序列，不存在则新建。
- **Request**: `{"type": "slam", "topic": "route_add", "msg": {"route_id": "2001", "route_name": "演示路线", "points": ["1001", "1002"]}}`

### 3.3 删除路线
- **Type**: `slam`
- **Topic**: `route_delete_by_rid`
- **Request**: `{"type": "slam", "topic": "route_delete_by_rid", "msg": {"route_id": "2001"}}`

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

### 4.2 停止与取消
- **停止当前运动**: `{"type": "slam", "topic": "stop_position", "msg": {}}`
- **取消导航任务**: `{"type": "slam", "topic": "cancel_navigation", "msg": {}}`
- **回充电桩**: `{"type": "slam", "topic": "go_to_dock", "msg": {}}`
- **紧急停止 (锁定)**: `{"type": "slam", "topic": "stop_all", "msg": {}}`

### 4.3 到达通知 (Server Push)
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

---

## 6. 地图与感知 (Map & Perception)

### 6.1 获取实时点云 (Point Cloud / Scan)
- **Type**: `slam`
- **Topic**: `point_cloud` 或 `get_scan`
- **说明**: 获取当前环境激光雷达扫描的实时点云数据快照。
- **Request**: `{"type": "slam", "topic": "point_cloud", "msg": {}}`
- **Response**: 
  ```json
  {
    "type": "slam",
    "topic": "point_cloud",
    "msg": [
      {"x": 1.2, "y": 0.5},
      {"x": 1.5, "y": -0.2}
    ]
  }
  ```

### 6.2 路径数据 (Path Planning)
- **Type**: `slam`
- **Topic**: `get_global_path` 或 `get_local_path`
- **说明**: 获取机器人当前规划的全局或局部路径点集。
- **Request**: `{"type": "slam", "topic": "get_global_path", "msg": {}}`
- **Response**: 
  ```json
  {
    "type": "slam",
    "topic": "get_global_path",
    "msg": [
      {"x": 0.0, "y": 0.0},
      {"x": 0.2, "y": 0.1}
    ]
  }
  ```

---

## 7. 机器人手臂与姿态控制 (Arm & Posture)

### 7.1 获取手臂动作列表
- **Type**: `arm` 或 `webrtc`
- **Topic**: `get_arm`
- **Response**: 
  ```json
  {
    "type": "arm",
    "topic": "get_arm",
    "msg": [
      {"id": 1, "name": "握手", "time": 3.0},
      {"id": 2, "name": "招手", "time": 2.5}
    ]
  }
  ```

### 7.2 获取姿态列表
- **Type**: `arm` 或 `webrtc`
- **Topic**: `get_posture`
- **Response**: 
  ```json
  {
    "type": "arm",
    "topic": "get_posture",
    "msg": [
      {"id": 1, "technical_name": "stand", "display_name": "立正"},
      {"id": 3, "technical_name": "sit", "display_name": "坐下"}
    ]
  }
  ```

### 7.3 执行手臂动作
- **Type**: `arm`
- **Topic**: `set_arm` 或 `play_arm`
- **Request**: `{"type": "arm", "topic": "set_arm", "msg": {"id": 1}}`
- **Response**: `{"receive": "true", "id": 1, "message": "手臂动作执行中"}`
- **动作结束通知 (Push)**: `{"type": "arm", "topic": "arm_action_finished", "msg": {"id": 1}}`

### 7.4 切换机器人姿态
- **Type**: `arm`
- **Topic**: `set_posture` 或 `play_posture`
- **Request**: `{"type": "arm", "topic": "set_posture", "msg": {"id": 3}}`
- **Response**: `{"receive": "true", "id": 3, "message": "姿态切换至: sit"}`

### 7.5 停止动作
- **Type**: `arm`
- **Topic**: `stop_arm`
- **Request**: `{"type": "arm", "topic": "stop_arm", "msg": {}}`

---

## 8. 导览核心状态查询 (Polling)

### 8.1 获取核心状态
- **Type**: `navigation` 或 `webrtc`
- **Topic**: `get_status`
- **说明**: 主动获取机器人当前的导航核心状态、目标点信息及硬件/系统就绪状态。
- **Request**: `{"type": "navigation", "topic": "get_status", "msg": {}}`
- **Response**:
  ```json
  {
    "type": "navigation",
    "topic": "get_status",
    "msg": {
      "state": "NAVIGATING",
      "current_point_id": "point_2",
      "ros_enabled": true
    }
  }
  ```
- **State 枚举值详解**:
  - `IDLE`: 初始空闲状态。
  - `NAV_READY`: 导航系统已就绪，已完成重定位或扫图，等待指令。
  - `NAVIGATING`: 正在前往目标的平滑移动模拟中。
  - `RELOCALIZING`: 正在执行 `set_position` 重定位模拟（通常持续 2 秒）。
  - `EMERGENCY_STOP`: 急停触发状态，需手动清除任务恢复。
  - `MAPPING`: 正在进行扫图环境构建。

### 8.2 状态主动推送 (Status Push)
- **Type**: `slam`
- **Topic**: `nav_status`
- **说明**: 每当导览状态 `state` 发生切换或目标点改变时，服务端会自动推送此快照消息。
- **Message**:
  ```json
  {
    "type": "slam",
    "topic": "nav_status",
    "msg": {
      "state": "NAVIGATING",
      "current_point_id": "1001",
      "ros_enabled": true
    }
  }
  ```

---

## 9. 扫图管理 (Mapping)

### 9.1 开始扫图
- **Type**: `slam`
- **Topic**: `start_mapping`
- **Request**: `{"type": "slam", "topic": "start_mapping", "msg": {}}`
- **Response**: `{"receive": "true", "message": "进入扫图模式"}`

### 9.2 停止扫图
- **Type**: `slam`
- **Topic**: `stop_mapping`
- **Request**: `{"type": "slam", "topic": "stop_mapping", "msg": {}}`
- **Response**: `{"receive": "true", "message": "退出扫图模式"}`
