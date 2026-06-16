# SPDX-License-Identifier: GPL-3.0-or-later


from __future__ import annotations

import bpy
from bpy.types import Collection, Object

from .. import var
from ..lib import asset
from . import generator_nodes


def create_object(
    context,
    coll: Collection,
    source_coll: Collection,
    label: str,
    material_name: str,
    source_prop: str,
) -> Object:
    if generator_nodes.is_scene_collection(source_coll):
        raise ValueError("Scene Collection cannot be used as generator source")

    name = f"{source_coll.name} {label}"
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    ob.display_type = "TEXTURED"
    asset.ob_link(ob, coll)

    prefs = context.preferences.addons[var.ADDON_ID].preferences
    asset.add_material(ob, name=material_name, color=prefs.color_cutter)
    ob[source_prop] = source_coll.name

    return ob


def select_object(context, ob: Object) -> Object:
    context.view_layer.objects.active = ob
    ob.select_set(True)
    return ob


def handler_add(handler) -> None:
    handlers = bpy.app.handlers.depsgraph_update_post

    if handler not in handlers:
        handlers.append(handler)


def handler_del(handler) -> None:
    handlers = bpy.app.handlers.depsgraph_update_post

    if handler in handlers:
        handlers.remove(handler)


def auto_update(scene, depsgraph, source_prop: str, update_object, handler_del_func, state: dict) -> None:
    if state.get("is_updating"):
        return

    generators = [ob for ob in scene.objects if source_prop in ob]

    if not generators:
        handler_del_func()
        return

    state["is_updating"] = True
    try:
        for ob in generators:
            update_object(ob, depsgraph=depsgraph)
    finally:
        state["is_updating"] = False


def clear_mesh(ob: Object, signature_prop: str) -> None:
    ob.data.clear_geometry()
    ob.data.update()
    ob[signature_prop] = ""


def source_collection(ob: Object, source_prop: str) -> Collection | None:
    coll = bpy.data.collections.get(ob.get(source_prop, ""))

    return None if coll is not None and generator_nodes.is_scene_collection(coll) else coll


def modifier(ob: Object, nodes_module):
    for md in ob.modifiers:
        is_generator_modifier = (
            md.type == "NODES"
            and md.node_group
            and md.node_group.name.startswith(nodes_module.NODE_GROUP_NAME)
        )

        if is_generator_modifier:
            if not generator_nodes.is_node_group_current(
                md.node_group,
                nodes_module.SCHEMA_KEY,
                nodes_module.SOCKETS,
            ):
                md.node_group = nodes_module.ensure_node_group()
            return md

    return None


def apply_modifier_socket_values(
    values: dict,
    md,
    nodes_module,
    legacy_names: dict[str, tuple[str, ...]] | None = None,
) -> None:
    if md is None or md.node_group is None:
        return

    identifiers = nodes_module.socket_identifiers(md.node_group)
    legacy_names = legacy_names or {}

    for name in values:
        for socket_name in (name, *legacy_names.get(name, ())):
            if identifier := identifiers.get(socket_name):
                values[name] = modifier_socket_value(md, identifier, values[name])
                break


def modifier_socket_value(md, identifier: str, fallback):
    value = md.get(identifier, fallback)

    if isinstance(fallback, bool):
        return bool(value)
    if isinstance(fallback, int):
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback
    if isinstance(fallback, float):
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    return value


def signature_parts(generator: Object, modifier_values: dict, source_prop: str) -> list[str]:
    return [
        str(
            modifier_values["source_coll"].name
            if modifier_values["source_coll"]
            else generator.get(source_prop, "")
        ),
        repr(
            sorted(
                (name, value)
                for name, value in modifier_values.items()
                if name != "source_coll"
            )
        ),
    ]
