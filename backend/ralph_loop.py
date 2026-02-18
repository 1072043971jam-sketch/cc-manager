"""
Ralph Loop - 后台持续任务分发循环
每 5 秒检查一次队列，找到空闲 worker 就分配任务
"""
import asyncio
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from task_queue import TaskQueue
from worker_manager import WorkerManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Ralph] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)


class RalphLoop:
    def __init__(self, num_workers: int = 2):
        self.tq = TaskQueue()
        self.wm = WorkerManager(num_workers=num_workers)
        self.running = False
        self.interval = 5  # 检查间隔（秒）

    async def start(self):
        """启动 Ralph Loop"""
        self.running = True
        log.info(f"Ralph Loop started with {self.wm.num_workers} workers")
        
        while self.running:
            try:
                await self._tick()
            except Exception as e:
                log.error(f"Ralph Loop error: {e}")
            
            await asyncio.sleep(self.interval)

    async def stop(self):
        self.running = False
        log.info("Ralph Loop stopped")

    async def _tick(self):
        """单次循环：检查 worker + 分配任务"""
        # 获取所有空闲 worker
        idle_workers = self.wm.get_idle_workers()
        
        if not idle_workers:
            return
        
        log.info(f"Idle workers: {[w['id'] for w in idle_workers]}")
        
        for worker in idle_workers:
            # 从队列取下一个任务
            task = self.tq.get_next_task()
            if not task:
                break
            
            log.info(f"Assigning task #{task['id']} to worker #{worker['id']}")
            
            # 标记任务为运行中
            self.tq.update_task_status(
                task_id=task["id"],
                status="running",
                worker_id=worker["id"]
            )
            
            # 在后台执行任务
            asyncio.create_task(
                self._run_task(worker, task)
            )

    async def _run_task(self, worker: dict, task: dict):
        """在 worker 上执行任务"""
        worker_id = worker["id"]
        task_id = task["id"]
        
        try:
            # 标记 worker 为运行中
            self.wm.set_worker_running(worker_id, task_id)
            
            log.info(f"Worker #{worker_id} starting task #{task_id}: {task['title']}")
            
            # 获取或创建 worktree
            worktree_path = await self.wm.get_worktree(worker_id, task["project"])
            
            # 执行 Claude Code 任务
            result = await self._execute_cc(task, worktree_path)
            
            # 任务完成
            if result["success"]:
                log.info(f"Task #{task_id} completed successfully")
                self.tq.update_task_status(
                    task_id=task_id,
                    status="done",
                    result=result.get("stdout", "")[:2000]
                )
                
                # 自动 git commit & push
                if worktree_path:
                    await self._auto_commit(worktree_path, task)
            else:
                log.error(f"Task #{task_id} failed: {result.get('error', 'Unknown error')}")
                self.tq.update_task_status(
                    task_id=task_id,
                    status="failed",
                    result=result.get("error", "")[:2000]
                )
                
                # 记录失败到 PROGRESS.md
                self._log_failure_to_progress(task, result)
        
        except Exception as e:
            log.error(f"Worker #{worker_id} error: {e}")
            self.tq.update_task_status(task_id=task_id, status="failed", result=str(e))
        
        finally:
            # 释放 worker
            self.wm.set_worker_idle(worker_id)
            log.info(f"Worker #{worker_id} is now idle")

    async def _execute_cc(self, task: dict, worktree_path: str) -> dict:
        """异步执行 Claude Code 任务"""
        prompt = task["prompt"]
        mode = task.get("mode", "execute")
        
        if mode == "plan":
            prompt = "请先分析并输出实施计划，不要写代码。\n\n" + prompt
        
        cmd = [
            "claude",
            "-p", prompt,
            "--dangerously-skip-permissions",
            "--output-format", "stream-json",
            "--model", "claude-sonnet-4-20250514",
        ]
        
        env = os.environ.copy()
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=worktree_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=3600  # 1小时超时
            )
            
            return {
                "success": proc.returncode == 0,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "returncode": proc.returncode
            }
        
        except asyncio.TimeoutError:
            proc.kill()
            return {"success": False, "error": "Task timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _auto_commit(self, worktree_path: str, task: dict):
        """自动 git add + commit + push"""
        try:
            commit_msg = f"Task #{task['id']}: {task['title']}\n\nCo-Authored-By: Claude Code <noreply@anthropic.com>"
            
            proc = await asyncio.create_subprocess_shell(
                f'cd "{worktree_path}" && git add -A && git diff --cached --quiet || git commit -m "{commit_msg}" && git push origin HEAD',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            log.info(f"Auto-committed changes in {worktree_path}")
        except Exception as e:
            log.error(f"Auto-commit failed: {e}")

    def _log_failure_to_progress(self, task: dict, result: dict):
        """记录失败任务到 PROGRESS.md"""
        progress_path = "/root/cc-manager/PROGRESS.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n## {timestamp} - Task #{task['id']} Failed\n\n**Task**: {task['title']}\n**Error**: {result.get('error', 'Unknown')}\n\n---\n"
        
        try:
            with open(progress_path, "a") as f:
                f.write(entry)
        except Exception as e:
            log.error(f"Failed to write PROGRESS.md: {e}")
