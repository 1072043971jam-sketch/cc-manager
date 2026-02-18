import os
import asyncio
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from task_queue import TaskQueue
from cc_runner import CCRunner

app = FastAPI(title="CC Manager API")

# 初始化任务队列
tq = TaskQueue()
cc = CCRunner()

# 数据模型
class TaskCreate(BaseModel):
    project: str
    title: str
    prompt: str
    mode: str = "execute"
    priority: int = 0

class TaskResponse(BaseModel):
    id: int
    project: str
    title: str
    status: str
    mode: str
    created_at: datetime

# API 路由
@app.post("/api/tasks", response_model=dict)
async def create_task(task: TaskCreate):
    task_id = tq.add_task(
        project=task.project,
        title=task.title,
        prompt=task.prompt,
        mode=task.mode,
        priority=task.priority
    )
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
                "created_at": task.created_at.isoformat(),
            }
    raise HTTPException(status_code=404, detail="Task not found")

@app.get("/health")
async def health():
    return {"status": "ok"}

# 静态文件 (PWA 前端)
static_dir = os.path.join(os.path.dirname(__file__), "../frontend")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("CC_MANAGER_PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
