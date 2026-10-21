"""用户级配置模块。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.storage.postgres.models_business import UserConfig as UserConfigRecord
from yuxi.utils.datetime_utils import format_utc_datetime, utc_now_naive


class UserConfigSchema(BaseModel):
    """用户专属配置 schema。"""

    enable_memory: bool | None = Field(default=None, description="是否启用 Memory")
    default_agent_id: str | None = Field(default=None, max_length=80, description="个人默认智能体 slug")

    @field_validator("enable_memory")
    @classmethod
    def validate_enable_memory(cls, value: bool | None) -> bool | None:
        """显式更新 Memory 时只接受布尔值，缺省仍表示不修改。"""
        if value is None:
            raise ValueError("enable_memory 必须为布尔值")
        return value

    model_config = ConfigDict(extra="forbid")


class UserConfig:
    """用户级配置访问器。每次加载都从 PostgreSQL 查询，不做进程缓存。"""

    def __init__(self, uid: str, schema: UserConfigSchema | None = None, updated_at: datetime | None = None):
        self.uid = uid
        self.schema = schema or UserConfigSchema()
        self.updated_at = updated_at

    @classmethod
    async def load(cls, db: AsyncSession, uid: str) -> UserConfig:
        result = await db.execute(select(UserConfigRecord).filter(UserConfigRecord.uid == uid))
        record = result.scalar_one_or_none()
        if record is None:
            return cls(uid=uid, schema=UserConfigSchema(enable_memory=False, default_agent_id=None))
        return cls(
            uid=uid,
            schema=UserConfigSchema(
                enable_memory=bool(record.enable_memory),
                default_agent_id=record.default_agent_id,
            ),
            updated_at=record.updated_at,
        )

    async def save(self, db: AsyncSession) -> UserConfig:
        fields = self.schema.model_fields_set
        values = {
            field: getattr(self.schema, field) for field in ("enable_memory", "default_agent_id") if field in fields
        }
        if not values:
            return await type(self).load(db, self.uid)

        now = utc_now_naive()
        values["updated_at"] = now
        result = await db.execute(update(UserConfigRecord).where(UserConfigRecord.uid == self.uid).values(**values))
        if result.rowcount == 0:
            db.add(
                UserConfigRecord(
                    uid=self.uid,
                    enable_memory=self.schema.enable_memory if self.schema.enable_memory is not None else False,
                    default_agent_id=self.schema.default_agent_id,
                    created_at=now,
                    updated_at=now,
                )
            )
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            now = utc_now_naive()
            values["updated_at"] = now
            retry_result = await db.execute(
                update(UserConfigRecord).where(UserConfigRecord.uid == self.uid).values(**values)
            )
            if retry_result.rowcount == 0:
                raise
            await db.commit()
        return await type(self).load(db, self.uid)

    def dump_config(self) -> dict[str, str | bool | None]:
        return {
            "uid": self.uid,
            "enable_memory": self.schema.enable_memory,
            "default_agent_id": self.schema.default_agent_id,
            "updated_at": format_utc_datetime(self.updated_at),
        }
