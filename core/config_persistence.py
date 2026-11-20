"""DATA_DIR/.env 配置持久化（打包 spec §5.3 / §9-Q1）。

首跑向导/模型配置面板保存成功后，把配置键合并写回 DATA_DIR/.env，跨重启存活：
- 只覆盖 updates 中的键；注释、空行、其余键与行序原样保留；
- 值统一转 str 原样写入（dotenv 负责解析，API Key 特殊字符不做转义）；
- 同目录临时文件 + os.replace 原子替换：写失败不损坏既有 .env，异常上抛由
  调用方决定降级策略。

位置约定：开发态 DATA_DIR=PROJECT_ROOT/data → 写 data/.env（不碰根目录用户
.env）；冻结态 DATA_DIR=用户数据目录 → 写用户数据目录/.env。DATA_DIR 在调用时
动态读取（与 launcher helper 一致），便于测试重定向。
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

import config

# 匹配 KEY=VALUE / export KEY=VALUE 行（注释与空行不匹配，原样保留）
_ENV_LINE_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")


def write_env_config(updates: dict) -> None:
    """把 updates 合并写入 config.DATA_DIR/.env（原子写，保留其余内容）。

    已存在的同名键就地更新（重复出现则全部更新，避免 dotenv 后值覆盖让旧值
    复活）；新键追加到文件末尾。无 .env 时按 updates 新建。
    """
    if not updates:
        return
    env_path = Path(config.DATA_DIR) / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    values = {str(key): str(value) for key, value in updates.items()}

    lines = (
        env_path.read_text(encoding="utf-8").splitlines()
        if env_path.exists()
        else []
    )
    merged: list[str] = []
    seen: set[str] = set()
    for line in lines:
        match = _ENV_LINE_RE.match(line)
        key = match.group(1) if match else None
        if key is not None and key in values:
            merged.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            merged.append(line)
    merged.extend(f"{key}={value}" for key, value in values.items() if key not in seen)
    content = "\n".join(merged) + "\n"

    # 原子写：同目录临时文件落盘（fsync）后 os.replace 替换目标
    fd, tmp_name = tempfile.mkstemp(
        prefix=".env-", suffix=".tmp", dir=str(env_path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(content)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_name, env_path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
