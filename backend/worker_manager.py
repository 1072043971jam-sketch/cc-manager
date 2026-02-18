"""
Worker Manager - Worker 生命周期管理
管理 2 个 worker slot + Git worktree 绑定
"""
import asyncio
import logging
import os
from typing import List, Optional, Dict

log = logging.getLogger(__name__)


class WorkerManager:
    def __init__(self, num_workers: int = 2):
        self.num_workers = num_workers
        self.workspace_root = "/root/workspaces"
        
        # Worker 状态表（内存）
        self.workers: Dict[int, dict] = {}
        for i in range(1, num_workers + 1):
            self.workers[i] = {
                "id": i,
                "status": "idle",
                "current_task_id": None,
                "worktree_path": None,
                "project": None,
            }
        
        log.info(f"WorkerManager initialized with {num_workers} workers")

    def get_idle_workers(self) -> List[dict]:
        """返回所有空闲 worker"""
        return [w for w in self.workers.values() if w["status"] == "idle"]

    def set_worker_running(self, worker_id: int, task_id: int):
        """标记 worker 为运行中"""
        if worker_id in self.workers:
            self.workers[worker_id]["status"] = "running"
            self.workers[worker_id]["current_task_id"] = task_id

    def set_worker_idle(self, worker_id: int):
        """释放 worker，恢复空闲"""
        if worker_id in self.workers:
            self.workers[worker_id]["status"] = "idle"
            self.workers[worker_id]["current_task_id"] = None

    def get_all_workers(self) -> List[dict]:
        """返回所有 worker 状态"""
        return list(self.workers.values())

    async def get_worktree(self, worker_id: int, project: str) -> str:
        """获取或创建 worker 对应的 worktree"""
        # 非 Git 项目或无项目配置时，使用临时工作目录
        work_dir = f"/root/workspaces/worker-{worker_id}"
        os.makedirs(work_dir, exist_ok=True)
        
        self.workers[worker_id]["worktree_path"] = work_dir
        self.workers[worker_id]["project"] = project
        
        return work_dir

    async def setup_project_worktrees(self, project: str, repo_url: str, branch: str = "main"):
        """为项目初始化 worktree 池"""
        project_dir = f"{self.workspace_root}/{project}"
        main_dir = f"{project_dir}/main"
        
        os.makedirs(project_dir, exist_ok=True)
        
        # 克隆主仓库（如果不存在）
        if not os.path.exists(f"{main_dir}/.git"):
            proc = await asyncio.create_subprocess_shell(
                f"git clone {repo_url} {main_dir}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            log.info(f"Cloned {repo_url} to {main_dir}")
        
        # 为每个 worker 创建 worktree
        for i in range(1, self.num_workers + 1):
            worker_dir = f"{project_dir}/worker-{i}"
            if not os.path.exists(worker_dir):
                proc = await asyncio.create_subprocess_shell(
                    f"cd {main_dir} && git worktree add {worker_dir} -b worker-{i}-branch",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
                log.info(f"Created worktree for worker {i}: {worker_dir}")
        
        log.info(f"Project '{project}' worktrees ready")
