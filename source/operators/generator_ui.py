# SPDX-License-Identifier: GPL-3.0-or-later


import bpy
from bpy.types import Collection

from . import generator_nodes


def active_collection(context) -> Collection | None:
    if context.collection is not None and not generator_nodes.is_scene_collection(context.collection):
        return context.collection

    layer_coll = context.view_layer.active_layer_collection
    if layer_coll is not None and not generator_nodes.is_scene_collection(layer_coll.collection):
        return layer_coll.collection

    ob = context.object
    if ob is not None and ob.users_collection:
        for coll in ob.users_collection:
            if not generator_nodes.is_scene_collection(coll):
                return coll

    return None


def collection_by_name(name: str) -> Collection | None:
    coll = bpy.data.collections.get(name) if name else None
    return None if coll is not None and generator_nodes.is_scene_collection(coll) else coll


def modifier(ob, nodes_module):
    for md in ob.modifiers:
        if md.type == "NODES" and md.node_group and md.node_group.name.startswith(nodes_module.NODE_GROUP_NAME):
            if not generator_nodes.is_node_group_current(
                md.node_group,
                nodes_module.SCHEMA_KEY,
                nodes_module.SOCKETS,
            ):
                md.node_group = nodes_module.ensure_node_group()
            return md

    return None


def socket_identifiers(md, nodes_module) -> dict[str, str]:
    if md is None or md.node_group is None:
        return {}

    return nodes_module.socket_identifiers(md.node_group)


def draw_socket(layout, md, identifiers: dict[str, str], name: str, text: str | None = None) -> None:
    identifier = identifiers.get(name)

    if identifier and identifier in md:
        layout.prop(md, f'["{identifier}"]', text=text or name)


def setup_property_layout(layout) -> None:
    layout.use_property_split = True
    layout.use_property_decorate = False


def draw_source_collection_search(layout, owner) -> None:
    setup_property_layout(layout)
    layout.prop_search(owner, "source_collection_name", bpy.data, "collections")


def execute_add_operator(operator, context, create_object, purge_handlers, success_message: str):
    purge_handlers()

    source_coll = collection_by_name(getattr(operator, "source_collection_name", ""))
    source_coll = source_coll or active_collection(context)

    if source_coll is None:
        operator.report({"ERROR"}, "Gem collection must be specified")
        return {"CANCELLED"}

    try:
        create_object(context, context.scene.collection, source_coll)
    except ValueError as e:
        operator.report({"ERROR"}, str(e))
        return {"CANCELLED"}

    operator.report({"INFO"}, success_message)
    return {"FINISHED"}


def invoke_add_operator(operator, context, purge_handlers):
    purge_handlers()

    if active_coll := active_collection(context):
        operator.source_collection_name = active_coll.name

    context.window_manager.invoke_props_dialog(operator)
    return {"RUNNING_MODAL"}


def draw_collection(layout, ob, prop_name: str, text: str = "Gem Collection") -> None:
    if prop_name not in ob:
        ob[prop_name] = ""
    elif ob[prop_name] and collection_by_name(ob[prop_name]) is None:
        ob[prop_name] = ""

    layout.prop_search(ob, f'["{prop_name}"]', bpy.data, "collections", text=text)


def socket_value(md, identifiers: dict[str, str], name: str, fallback):
    if identifier := identifiers.get(name):
        return md.get(identifier, fallback)

    return fallback


def purge_stale_handlers(handler_name: str, module_suffix: str) -> None:
    handlers = bpy.app.handlers.depsgraph_update_post

    for handler in tuple(handlers):
        module = getattr(handler, "__module__", "")
        name = getattr(handler, "__name__", "")

        if name == handler_name or module.endswith(module_suffix):
            handlers.remove(handler)
