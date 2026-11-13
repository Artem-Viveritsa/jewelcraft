# SPDX-FileCopyrightText: 2021-2025 Mikhail Rachinskiy
# SPDX-License-Identifier: GPL-3.0-or-later

# v1.3.0

from pathlib import Path
from typing import Any

import bpy


def get_classes(modules: tuple[Any]) -> tuple[type]:
    bases = {
        bpy.types.AddonPreferences,
        bpy.types.Menu,
        bpy.types.Operator,
        bpy.types.Panel,
        bpy.types.PropertyGroup,
        bpy.types.UIList,
    }

    classes = []

    for module in modules:
        for cls in module.__dict__.values():
            if isinstance(cls, type):
                for base in cls.__bases__:
                    if base in bases:
                        classes.append(cls)
                        break

    return tuple(classes)


def unload_submodules(package: str, namespace: dict[str, Any]) -> None:
    import sys

    prefix = f"{package}."

    for name in [name for name in sys.modules if name.startswith(prefix)]:
        del sys.modules[name]
        namespace.pop(name.removeprefix(prefix).partition(".")[0], None)


def check_integrity(path: Path) -> None:
    """:raises FileNotFoundError:"""

    if not path.exists():
        raise FileNotFoundError("Incorrect package, follow installation guide")
