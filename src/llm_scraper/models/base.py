from __future__ import annotations

import json
from typing import Any, Type, TypeVar

from pydantic import BaseModel as _BaseModel
from pydantic import ConfigDict, ValidationError
from pydantic.fields import ModelPrivateAttr

from ..exceptions import ParserError
from ..utils.aliases import AliasGenerator

__all__ = ("BaseModel",)

T = TypeVar("T", bound="BaseModel")


class BaseModel(_BaseModel):
    model_config = ConfigDict(
        alias_generator=AliasGenerator.to_snake_case,
        populate_by_name=True,
        extra="forbid",
        frozen=False,
        arbitrary_types_allowed=True,
    )

    @classmethod
    def from_string(cls: Type[T], value: str | bytes) -> T:
        if isinstance(value, bytes):
            value = value.decode("utf-8")

        if isinstance(value, str):
            try:
                data = json.loads(value)
                return cls.model_validate(data)
            except (json.JSONDecodeError, ValidationError) as e:
                raise ParserError(f"Cannot parse JSON string to {cls.__name__}: {e}") from e

        raise ParserError(f"Input must be a valid JSON string or bytes, not {type(value).__name__}")

    @classmethod
    def from_kwargs(cls: Type[T], **kwargs: Any) -> T:
        try:
            return cls.model_validate(kwargs)
        except ValidationError as e:
            raise ParserError(f"Cannot parse kwargs to {cls.__name__}: {e}") from e

    @classmethod
    def from_dict(cls: Type[T], data: dict | Any) -> T:
        if isinstance(data, cls):
            return data
        if isinstance(data, dict):
            return cls.from_kwargs(**data)
        raise ParserError(f"Input must be a dictionary or an instance of {cls.__name__}")

    def to_dict(self, **kwargs: Any) -> dict[str, Any]:
        return self.model_dump(**kwargs)

    def to_json(self, **kwargs: Any) -> str:
        return self.model_dump_json(**kwargs)

    @classmethod
    def to_list(cls, obj: Any) -> list[Any]:
        return obj if isinstance(obj, (list, tuple, set)) else [obj]

    @classmethod
    def get_private_field(cls, field: str) -> Any:
        private_attr = getattr(cls, field, None)
        if isinstance(private_attr, ModelPrivateAttr):
            return private_attr.get_default()
        return private_attr
