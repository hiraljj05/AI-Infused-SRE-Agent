from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"

    @property
    def is_severe(self) -> bool:
        return self in (LogLevel.ERROR, LogLevel.FATAL)


@dataclass(frozen=True, slots=True)
class LogLine:
    timestamp: datetime
    level: LogLevel
    message: str
    source: str

    def matches_pattern(self, pattern: str) -> bool:
        return pattern.lower() in self.message.lower()
