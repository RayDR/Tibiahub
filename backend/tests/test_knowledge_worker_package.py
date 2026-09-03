from pathlib import Path
import subprocess
import sys


def test_worker_package_does_not_preload_module_before_runpy_execution():
    probe = """
import runpy
import sys

import app.knowledge.workers

assert 'app.knowledge.workers.knowledge_worker' not in sys.modules
runpy.run_module('app.knowledge.workers.knowledge_worker', run_name='knowledge_worker_probe')
"""
    result = subprocess.run(
        [sys.executable, "-W", "error::RuntimeWarning", "-c", probe],
        capture_output=True,
        text=True,
        check=False,
        cwd=Path(__file__).resolve().parents[1],
    )

    assert result.returncode == 0, result.stderr


def test_worker_package_keeps_public_knowledge_worker_export():
    from app.knowledge.workers import KnowledgeWorker

    assert KnowledgeWorker.__name__ == "KnowledgeWorker"
