"""
Ralph Loop - 后台持续任务分发循环
每 5 秒检查一次队列，找到空闲 worker 就分配任务
"""
import asyncio
import logging
import os
import shlex
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
        self.interval = 5

    async def start(self):
        self.running = True
        log.info(f"Ralph Loop started with {self.wm.num_workers} workers")
        while self.running:
            try:
                await self._tick()
            except Exception as e:
                log.error(f"Tick error: {e}")
            await asyncio.sleep(self.interval)

    async def stop(self):
        self.running = False

    async def _tick(self):
        idle_workers = self.wm.get_idle_workers()
        if not idle_workers:
            return
        log.info(f"Idle workers: {[w['id'] for w in idle_workers]}")
        for worker in idle_workers:
            task = self.tq.get_next_task()
            if not task:
                break
            log.info(f"Assigning task #{task['id']} to worker #{worker['id']}")
            self.tq.update_task_status(task_id=task["id"], status="running", worker_id=worker["id"])
            asyncio.create_task(self._run_task(worker, task))

    async def _run_task(self, worker: dict, task: dict):
        worker_id = worker["id"]
        task_id = task["id"]
        try:
            self.wm.set_worker_running(worker_id, task_id)
            log.info(f"Worker #{worker_id} starting task #{task_id}: {task['title']}")
            worktree_path = await self.wm.get_worktree(worker_id, task["project"])
            result = await self._execute_cc(task, worktree_path)
            if result["success"]:
                log.info(f"Task #{task_id} completed OK")
                self.tq.update_task_status(task_id=task_id, status="done", result=result.get("stdout", "")[:2000])
                await self._auto_commit(worktree_path, task)
            else:
                err = result.get("stderr") or result.get("error", "Unknown")
                log.error(f"Task #{task_id} FAILED: {err[:300]}")
                self.tq.update_task_status(task_id=task_id, status="failed", result=err[:2000])
                self._log_failure_to_progress(task, {"error": err})
        except Exception as e:
            log.error(f"Worker #{worker_id} exception: {e}")
            self.tq.update_task_status(task_id=task_id, status="failed", result=str(e))
        finally:
            self.wm.set_worker_idle(worker_id)
            log.info(f"Worker #{worker_id} idle")

    async def _execute_cc(self, task: dict, worktree_path: str) -> dict:
        """以 ccuser stdin 方式执行 Claude Code（避免复杂引号嵌套）"""
        prompt = task["prompt"]
        mode = task.get("mode", "execute")
        if mode == "plan":
            prompt = "请先分析并输出实施计划，不要写代码。\n\n" + prompt

        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN", api_key)

        # 把命令写到临时脚本文件，避免引号嵌套问题
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False, dir="/tmp") as f:
            script_path = f.name
            f.write(f"""#!/bin/bash
export ANTHROPIC_API_KEY='{api_key}'
export ANTHROPIC_BASE_URL='{base_url}'
export ANTHROPIC_AUTH_TOKEN='{auth_token}'
export HOME=/home/ccuser
cd {shlex.quote(worktree_path)}
exec claude -p {shlex.quote(prompt)} --dangerously-skip-permissions --output-format text --model claude-opus-4-6
""")

        try:
            os.chmod(script_path, 0o755)
            # 把脚本所有权给 ccuser
            os.system(f"chown ccuser:ccuser {script_path}")

            log.info(f"Running script as ccuser: {script_path}")
            proc = await asyncio.create_subprocess_shell(
                f"su -s /bin/bash ccuser {script_path}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=3600)

            out = stdout.decode("utf-8", errors="replace")
            err = stderr.decode("utf-8", errors="replace")

            if proc.returncode != 0:
                log.error(f"claude rc={proc.returncode}, stderr={err[:300]}")

            return {
                "success": proc.returncode == 0,
                "stdout": out,
                "stderr": err,
                "returncode": proc.returncode
            }
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return {"success": False, "error": "Task timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            try:
                os.unlink(script_path)
            except Exception:
                pass

    async def _auto_commit(self, worktree_path: str, task: dict):
        try:
            msg = f"Task #{task['id']}: {task['title']}"
            proc = await asyncio.create_subprocess_shell(
                f"cd {shlex.quote(worktree_path)} && git add -A && "
                f"git diff --cached --quiet || git commit -m {shlex.quote(msg)} && git push origin HEAD 2>/dev/null || true",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            log.info(f"Auto-committed in {worktree_path}")
        except Exception as e:
            log.error(f"Auto-commit failed: {e}")

    def _log_failure_to_progress(self, task: dict, result: dict):
        progress_path = "/root/cc-manager/PROGRESS.md"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n## {ts} - Task #{task['id']} Failed\n\n**Task**: {task['title']}\n**Error**: {result.get('error', '')[:300]}\n\n---\n"
        try:
            with open(progress_path, "a") as f:
                f.write(entry)
        except Exception as e:
            log.error(f"PROGRESS.md write failed: {e}")
