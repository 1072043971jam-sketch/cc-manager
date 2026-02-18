import os
import asyncio
import logging
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from task_queue import TaskQueue
from worker_manager import WorkerManager
from ralph_loop import RalphLoop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="CC Manager API v2")

# 全局状态
tq = TaskQueue()
wm = WorkerManager(num_workers=2)
ralph = RalphLoop(num_workers=2)

# WebSocket 连接池
ws_connections: List[WebSocket] = []


async def broadcast_log(message: str):
    """广播日志到所有 WebSocket 客户端"""
    dead = []
    for ws in ws_connections:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_connections.remove(ws)


# 数据模型
class TaskCreate(BaseModel):
    project: str
    title: str
    prompt: str
    mode: str = "execute"
    priority: int = 0


# ===== 任务 API =====
@app.post("/api/tasks")
async def create_task(task: TaskCreate):
    task_id = tq.add_task(
        project=task.project,
        title=task.title,
        prompt=task.prompt,
        mode=task.mode,
        priority=task.priority
    )
    await broadcast_log(f"New task #{task_id}: {task.title}")
    return {"id": task_id, "status": "queued"}


@app.get("/api/tasks")
async def list_tasks(status: Optional[str] = None, limit: int = 50):
    tasks = tq.list_tasks(status=status, limit=limit)
    return [
        {
            "id": t.id,
            "project": t.project,
            "title": t.title,
            "status": t.status,
            "mode": t.mode,
            "worker_id": t.worker_id,
            "created_at": t.created_at.isoformat(),
            "finished_at": t.finished_at.isoformat() if t.finished_at else None,
        }
        for t in tasks
    ]


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: int):
    tasks = tq.list_tasks(limit=10000)
    for task in tasks:
        if task.id == task_id:
            return {
                "id": task.id,
                "project": task.project,
                "title": task.title,
                "prompt": task.prompt,
                "status": task.status,
                "result": task.result,
                "plan_text": task.plan_text,
                "created_at": task.created_at.isoformat(),
            }
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    tq.update_task_status(task_id=task_id, status="cancelled")
    return {"ok": True}


# ===== Worker API =====
@app.get("/api/workers")
async def get_workers():
    return wm.get_all_workers()


# ===== 健康检查 =====
@app.get("/health")
async def health():
    return {"status": "ok", "workers": len(wm.workers)}


# ===== WebSocket 日志流 =====
@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    ws_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # 可以接受来自前端的 ping
    except WebSocketDisconnect:
        if websocket in ws_connections:
            ws_connections.remove(websocket)


# ===== 生命周期管理 =====
@app.on_event("startup")
async def startup():
    log.info("Starting CC Manager...")
    # 后台启动 Ralph Loop
    asyncio.create_task(ralph.start())
    log.info("Ralph Loop started in background")


@app.on_event("shutdown")
async def shutdown():
    await ralph.stop()


# 静态前端
static_dir = os.path.join(os.path.dirname(__file__), "../frontend")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("CC_MANAGER_PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
