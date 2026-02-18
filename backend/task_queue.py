import os
import sqlite3
from datetime import datetime
from typing import List, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Task

class TaskQueue:
    def __init__(self, db_path: str = "/root/cc-manager/tasks.db"):
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    def add_task(self, project: str, title: str, prompt: str, mode: str = "execute", priority: int = 0) -> int:
        session = self.Session()
        task = Task(project=project, title=title, prompt=prompt, mode=mode, priority=priority)
        session.add(task)
        session.commit()
        task_id = task.id
        session.close()
        return task_id
    
    def get_next_task(self) -> Optional[Task]:
        session = self.Session()
        # 按优先级 DESC, ID ASC 获取队列中第一个任务
        task = session.query(Task).filter(
            Task.status == "queued"
        ).order_by(Task.priority.desc(), Task.id.asc()).first()
        
        if task:
            task_dict = {
                "id": task.id,
                "project": task.project,
                "title": task.title,
                "prompt": task.prompt,
                "mode": task.mode,
            }
            session.close()
            return task_dict
        
        session.close()
        return None
    
    def update_task_status(self, task_id: int, status: str, result: str = None, worker_id: int = None):
        session = self.Session()
        task = session.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = status
            if result:
                task.result = result
            if worker_id:
                task.worker_id = worker_id
            if status in ["done", "failed"]:
                task.finished_at = datetime.utcnow()
            session.commit()
        session.close()
    
    def list_tasks(self, status: str = None, limit: int = 50) -> List[Task]:
        session = self.Session()
        query = session.query(Task)
        if status:
            query = query.filter(Task.status == status)
        tasks = query.order_by(Task.created_at.desc()).limit(limit).all()
        session.close()
        return tasks
