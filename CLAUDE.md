# CC Manager Implementation Guide

This document guides Claude Code through implementing the CC Manager system.

## Architecture Overview

- **Backend**: FastAPI + SQLite task queue
- **Workers**: 2-3 parallel git worktrees, each running Claude Code
- **Frontend**: Vue 3 CDN PWA (no build step)
- **Integration**: Ralph Loop for continuous task distribution

## Key Components

1. **task_queue.py**: SQLite task persistence
2. **cc_runner.py**: Claude Code subprocess orchestration
3. **worker_manager.py**: Worker lifecycle + worktree binding
4. **ralph_loop.py**: Background task distribution loop
5. **frontend/**: Vue 3 responsive PWA

See steps in plan file for implementation order.

