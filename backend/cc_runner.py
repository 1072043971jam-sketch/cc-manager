import json
import subprocess
import os
from typing import Dict, Any

class CCRunner:
    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = base_url or os.getenv("ANTHROPIC_BASE_URL")
        self.auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
    
    def run_task(self, prompt: str, working_dir: str, mode: str = "execute") -> Dict[str, Any]:
        """Run a Claude Code task in the specified directory."""
        
        # 构建 Claude Code 命令
        env = os.environ.copy()
        env["ANTHROPIC_API_KEY"] = self.api_key
        env["ANTHROPIC_BASE_URL"] = self.base_url
        env["ANTHROPIC_AUTH_TOKEN"] = self.auth_token
        
        # 根据 mode 调整 prompt
        if mode == "plan":
            prompt_prefix = "请先分析并输出实施计划，不要写代码。\n\n"
        else:
            prompt_prefix = ""
        
        full_prompt = prompt_prefix + prompt
        
        cmd = [
            "claude",
            "-p", full_prompt,
            "--dangerously-skip-permissions",
            "--output-format", "stream-json",
            "--model", "claude-opus-4-6",
        ]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=3600,
                env=env,
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Task timed out after 1 hour",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
