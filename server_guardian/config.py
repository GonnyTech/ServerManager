"""
Configuration Manager for Server Guardian.
Handles loading, saving and encrypting/decrypting sensitive configurations.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Any

from server_guardian.security import (
    get_config_dir,
    encrypt_secret,
    decrypt_secret,
)

CONFIG_FILENAME = "config.json"


@dataclass
class SMTPConfig:
    host: str = "smtp.gmail.com"
    port: int = 587
    use_tls: bool = True
    use_ssl: bool = False
    username: str = ""
    password_encrypted: str = ""
    primary_email: str = ""
    backup_email: str = ""


@dataclass
class LLMConfig:
    provider: str = "generic"
    api_key_encrypted: str = ""
    model_name: str = "default"


@dataclass
class ScheduleConfig:
    hour: int = 2
    minute: int = 0


@dataclass
class GuardianConfig:
    system_password_encrypted: str = ""
    smtp: SMTPConfig = field(default_factory=SMTPConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    socket_path: str = ""

    def __post_init__(self):
        if not self.socket_path:
            # Default to unix domain socket in config dir
            config_dir = get_config_dir()
            self.socket_path = str(config_dir / "guardian.sock")

    @classmethod
    def get_config_path(cls) -> Path:
        return get_config_dir() / CONFIG_FILENAME

    @classmethod
    def load(cls) -> "GuardianConfig":
        path = cls.get_config_path()
        if not path.exists():
            cfg = cls()
            cfg.save()
            return cfg

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            smtp_data = data.get("smtp", {})
            llm_data = data.get("llm", {})
            schedule_data = data.get("schedule", {})

            return cls(
                system_password_encrypted=data.get("system_password_encrypted", ""),
                smtp=SMTPConfig(**smtp_data),
                llm=LLMConfig(**llm_data),
                schedule=ScheduleConfig(**schedule_data),
                socket_path=data.get("socket_path", ""),
            )
        except Exception:
            # Fallback on fresh instance
            return cls()

    def save(self) -> None:
        path = self.get_config_path()
        data = {
            "system_password_encrypted": self.system_password_encrypted,
            "smtp": asdict(self.smtp),
            "llm": asdict(self.llm),
            "schedule": asdict(self.schedule),
            "socket_path": self.socket_path,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        try:
            path.chmod(0o600)
        except (PermissionError, OSError):
            pass

    # Helper getters/setters for decrypted values
    def set_system_password(self, password: str) -> None:
        self.system_password_encrypted = encrypt_secret(password)

    def get_system_password(self) -> str:
        return decrypt_secret(self.system_password_encrypted)

    def set_smtp_password(self, password: str) -> None:
        self.smtp.password_encrypted = encrypt_secret(password)

    def get_smtp_password(self) -> str:
        return decrypt_secret(self.smtp.password_encrypted)

    def set_llm_api_key(self, api_key: str) -> None:
        self.llm.api_key_encrypted = encrypt_secret(api_key)

    def get_llm_api_key(self) -> str:
        return decrypt_secret(self.llm.api_key_encrypted)
