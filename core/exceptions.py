"""统一异常体系 — 模块化错误根因。

设计目标：
- **细粒度**：调用者可针对不同失败类型（配置错误 / 资源缺失 / 处理器内部错误）
  捕获并分别处理，而不是统统抓 ``Exception``。
- **可序列化**：用于 ``ProcessPoolExecutor`` 跨进程返回时，需要消息够独立可读。
- **轻量**：不依赖第三方库，只继承内置 ``Exception``。

继承关系::

    AkaSemiUtilsError                  # 项目根异常
    ├── ConfigError                    # 配置 / 模板 / user.json 相关
    │   ├── ConfigKeyError             # 必需 key 缺失
    │   └── ConfigValueError           # 值格式错误
    ├── ResourceError                  # 文件 / IO / 外部进程
    │   ├── ResourceNotFoundError      # 文件不存在
    │   └── ExifToolError              # exiftool 调用失败
    └── ProcessorError                 # 处理器执行失败
        ├── ProcessorNotFoundError     # 注册表查不到 key
        └── ProcessorRuntimeError      # 处理器 process() 内部抛错

约定：
- 抛出时**必须**带可读的 ``message``，建议同时附 ``context`` dict 以便日志。
- 上层捕获后可调用 ``str(exc)`` 直接打日志；细节字段通过属性访问。
"""

from __future__ import annotations

from typing import Any


class AkaSemiUtilsError(Exception):
    """项目根异常 — 所有自定义异常的共同基类。"""

    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict[str, Any] = context or {}

    def __str__(self) -> str:
        if self.context:
            ctx_str = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            return f"{self.message} ({ctx_str})"
        return self.message


# ---------------------------------------------------------------- Config 系列
class ConfigError(AkaSemiUtilsError):
    """配置类错误的基类（config.ini / user.json / 模板 JSON）。"""


class ConfigKeyError(ConfigError):
    """必需的配置 key 缺失。"""

    def __init__(self, key: str, source: str | None = None) -> None:
        super().__init__(
            f"配置缺少必需 key: {key!r}",
            context={"key": key, "source": source} if source else {"key": key},
        )
        self.key = key
        self.source = source


class ConfigValueError(ConfigError):
    """配置值类型 / 格式错误。"""

    def __init__(self, key: str, value: Any, expected: str) -> None:
        super().__init__(
            f"配置值类型错误: key={key!r}, value={value!r}, expected={expected}",
            context={"key": key, "value": value, "expected": expected},
        )
        self.key = key
        self.value = value
        self.expected = expected


# -------------------------------------------------------------- Resource 系列
class ResourceError(AkaSemiUtilsError):
    """资源访问 / IO 错误的基类。"""


class ResourceNotFoundError(ResourceError):
    """文件 / 目录不存在。"""

    def __init__(self, path: str, kind: str = "file") -> None:
        super().__init__(
            f"{kind} 不存在: {path}",
            context={"path": path, "kind": kind},
        )
        self.path = path
        self.kind = kind


class ExifToolError(ResourceError):
    """exiftool 子进程调用失败。"""

    def __init__(self, message: str, returncode: int | None = None, stderr: str = "") -> None:
        super().__init__(
            f"exiftool 调用失败: {message}",
            context={"returncode": returncode, "stderr": stderr[:200]} if returncode is not None else None,
        )
        self.returncode = returncode
        self.stderr = stderr


# ------------------------------------------------------------- Processor 系列
class ProcessorError(AkaSemiUtilsError):
    """处理器相关错误的基类。"""


class ProcessorNotFoundError(ProcessorError):
    """注册表中找不到指定 key 的处理器。"""

    def __init__(self, key: str) -> None:
        super().__init__(
            f"未注册的处理器: {key!r}",
            context={"key": key},
        )
        self.key = key


class ProcessorRuntimeError(ProcessorError):
    """处理器 ``process()`` 执行过程中抛出的错误（包装层）。"""

    def __init__(self, processor_name: str, original: BaseException) -> None:
        super().__init__(
            f"处理器 {processor_name!r} 执行失败: {original}",
            context={"processor_name": processor_name, "original_type": type(original).__name__},
        )
        self.processor_name = processor_name
        self.original = original


__all__ = [
    "AkaSemiUtilsError",
    "ConfigError",
    "ConfigKeyError",
    "ConfigValueError",
    "ExifToolError",
    "ProcessorError",
    "ProcessorNotFoundError",
    "ProcessorRuntimeError",
    "ResourceError",
    "ResourceNotFoundError",
]
