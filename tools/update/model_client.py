"""Тонкая обёртка вызова модели через `claude -p` (headless Claude Code). Промпт — в stdin."""
import subprocess


class ModelError(Exception):
    """Вызов модели не удался (ненулевой код, таймаут, пустой ответ)."""


def run_model(prompt: str, *, timeout: int = 180) -> str:
    try:
        proc = subprocess.run(["claude", "-p"], input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise ModelError(f"claude -p таймаут ({timeout}s)") from e
    if proc.returncode != 0:
        raise ModelError(f"claude -p код {proc.returncode}: {proc.stderr.strip()[:200]}")
    out = proc.stdout.strip()
    if not out:
        raise ModelError("claude -p вернул пустой ответ")
    return out
