from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True)
    project = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    prompt = Column(Text, nullable=False)
    priority = Column(Integer, default=0)
    status = Column(String(50), default="queued")  # queued, running, done, failed
    mode = Column(String(50), default="execute")  # execute, plan
    plan_text = Column(Text, nullable=True)
    result = Column(Text, nullable=True)
    worker_id = Column(Integer, nullable=True)
    branch_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

class Worker(Base):
    __tablename__ = "workers"
    
    id = Column(Integer, primary_key=True)
    status = Column(String(50), default="idle")  # idle, running, committing
    current_task_id = Column(Integer, nullable=True)
    worktree_path = Column(String(255), nullable=True)
    project = Column(String(255), nullable=True)
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
