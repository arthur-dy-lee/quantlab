"""异常层级（详细设计 §2）。

传播原则：
- `SourceUnavailable` 在 registry/适配器处被捕获并降级（缺库不崩）。
- `FetchError` 经 `with_retry` 重试；耗尽后由调用方（如 watch）记日志、不崩整轮。
- 其余异常默认向上传播。
"""

from __future__ import annotations


class QuantLabError(Exception):
    """所有自定义异常的基类。"""


class SymbolParseError(QuantLabError):
    """统一代码格式错误，如缺少 ``市场:`` 前缀。"""


class SourceUnavailable(QuantLabError):
    """数据源不可用：第三方库未安装，或该源不支持请求的市场。"""


class FetchError(QuantLabError):
    """联网取数失败 / 限流 —— 可重试（``with_retry`` 的默认目标）。"""


class DataQualityError(QuantLabError):
    """数据校验失败且无法修复（如坏行比例超阈值）。"""


class InsufficientData(QuantLabError):
    """历史或样本不足以完成计算（如概率统计样本为 0）。"""


class NotifyError(QuantLabError):
    """单个通知通道推送失败（不影响其它通道）。"""
