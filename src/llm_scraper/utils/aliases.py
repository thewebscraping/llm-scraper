from __future__ import annotations

import re
from string import punctuation


class AliasGenerator:
    @staticmethod
    def clean(name: str, is_stripped: bool = False) -> str:
        for pattern in punctuation:
            name = name.replace(pattern, "_")

        name = re.sub(r" +", "_", name)
        name = re.sub(r"_+", "_", re.sub(r" +", "_", name))
        if is_stripped:
            if name.startswith("_"):
                return name[1:]
        return name

    @classmethod
    def to_snake_case(cls, name: str) -> str:
        """
        Convert a string to snake_case.
        Reference: https://github.com/pydantic/pydantic/blob/main/pydantic/alias_generators.py
        """
        name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
        name = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name)
        name = name.replace("-", "_")
        return name.lower()

    @classmethod
    def to_camel_case(cls, name: str) -> str:
        """Convert a string to camelCase."""
        return "".join(word.capitalize() if i > 0 else word for i, word in enumerate(name.split("_")))

    @classmethod
    def to_pascal_case(cls, name: str) -> str:
        """Convert a string to PascalCase."""
        return "".join(word.capitalize() for word in name.split("_"))
