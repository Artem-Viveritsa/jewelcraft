# SPDX-License-Identifier: GPL-3.0-or-later


import hashlib

import bpy
from bpy.types import GeometryNodeTree, ID, NodesModifier


_SCHEMA_FINGERPRINT_VERSION = 1


def is_scene_collection(coll) -> bool:
    return any(scene.collection == coll for scene in bpy.data.scenes)


def node_group_fingerprint(sockets) -> str:
    data = repr((_SCHEMA_FINGERPRINT_VERSION, tuple(sockets))).encode()
    return hashlib.sha1(data).hexdigest()


def is_node_group_current(ng: GeometryNodeTree, schema_key: str, sockets) -> bool:
    return ng.get(schema_key) == node_group_fingerprint(sockets)


def ensure_node_group(name: str, schema_key: str, sockets) -> GeometryNodeTree:
    ng = bpy.data.node_groups.get(name)

    if ng is not None and is_node_group_current(ng, schema_key, sockets):
        ng.is_modifier = True
        return ng

    if ng is None:
        ng = bpy.data.node_groups.new(name, "GeometryNodeTree")

    return build_node_group(ng, schema_key, sockets)


def build_node_group(
    ng: GeometryNodeTree,
    schema_key: str,
    sockets,
) -> GeometryNodeTree:
    ng.nodes.clear()

    for item in tuple(ng.interface.items_tree):
        ng.interface.remove(item)

    ng.is_modifier = True
    ng[schema_key] = node_group_fingerprint(sockets)

    _new_socket(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    _new_socket(ng, "Geometry", "INPUT", "NodeSocketGeometry")

    for name, socket_type, default_value, min_value, max_value in sockets:
        _new_socket(ng, name, "INPUT", socket_type, default_value, min_value, max_value)

    group_in = ng.nodes.new("NodeGroupInput")
    group_in.location = (-220, 0)

    group_out = ng.nodes.new("NodeGroupOutput")
    group_out.location = (120, 0)

    ng.links.new(group_in.outputs["Geometry"], group_out.inputs["Geometry"])
    return ng


def new_modifier(context, ob, name: str, ensure_group, values: dict | None = None) -> NodesModifier:
    previous_active = context.view_layer.objects.active
    previous_selection = [item for item in context.selected_objects if item is not ob]

    for item in previous_selection:
        item.select_set(False)

    ob.select_set(True)
    context.view_layer.objects.active = ob

    try:
        bpy.ops.node.new_geometry_nodes_modifier()
        md = ob.modifiers[-1]
        md.name = name
        temp_group = md.node_group
        md.node_group = ensure_group()

        if temp_group is not None and temp_group.users == 0:
            bpy.data.node_groups.remove(temp_group)
    except Exception:
        has_node_modifier = (
            ob.modifiers
            and ob.modifiers[-1].type == "NODES"
            and ob.modifiers[-1].node_group is not None
        )

        if has_node_modifier:
            ob.modifiers.remove(ob.modifiers[-1])
        raise
    finally:
        for item in previous_selection:
            item.select_set(True)

        if previous_active is not None:
            try:
                context.view_layer.objects.active = previous_active
            except TypeError:
                pass

    md.show_group_selector = False

    if values:
        apply_modifier_values(md, values)

    return md


def settings_to_values(settings, socket_attrs) -> dict:
    return {socket: _attr_value(settings, attr) for socket, attr in socket_attrs}


def apply_modifier_values(md: NodesModifier, values: dict) -> None:
    identifiers = socket_identifiers(md.node_group)

    for name, value in values.items():
        if identifier := identifiers.get(name):
            _set_modifier_value(md, identifier, value)

    md.id_data.update_tag()
    md.node_group.update_tag()


def socket_identifiers(ng: GeometryNodeTree) -> dict[str, str]:
    return {
        item.name: item.identifier
        for item in ng.interface.items_tree
        if getattr(item, "item_type", None) == "SOCKET" and item.in_out == "INPUT"
    }


def _set_modifier_value(md: NodesModifier, identifier: str, value) -> None:
    try:
        md[identifier] = value
    except TypeError:
        if identifier in md:
            del md[identifier]

        try:
            md[identifier] = value
        except TypeError:
            if not isinstance(value, ID):
                raise


def _attr_value(settings, attr: str):
    value = settings

    for name in attr.split("."):
        value = getattr(value, name)

    return value


def _new_socket(
    ng: GeometryNodeTree,
    name: str,
    in_out: str,
    socket_type: str,
    default_value=None,
    min_value=None,
    max_value=None,
):
    socket = ng.interface.new_socket(name=name, in_out=in_out, socket_type=socket_type)

    if in_out == "INPUT" and hasattr(socket, "hide_in_modifier"):
        socket.hide_in_modifier = True

    for attr, value in (
        ("default_value", default_value),
        ("min_value", min_value),
        ("max_value", max_value),
    ):
        if value is not None and hasattr(socket, attr):
            setattr(socket, attr, value)

    return socket
