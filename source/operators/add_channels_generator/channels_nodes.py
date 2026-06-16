# SPDX-License-Identifier: GPL-3.0-or-later


from bpy.types import GeometryNodeTree, NodesModifier

from .. import generator_nodes


NODE_GROUP_NAME = "JewelCraft Channels Between Gemstones"
SCHEMA_KEY = "jewelcraft_channels_schema"

SOCKET_COLLECTION = "Gem Collection"
SOCKET_RATIO = "Radius Scale"
SOCKET_MAX_GAP = "Max Gap"
SOCKET_OFFSET_RATIO = "Offset Ratio"
SOCKET_CURVE_RESOLUTION = "Curve Resolution"

DEFAULT_RATIO = 0.4
DEFAULT_MAX_GAP = 0.5
DEFAULT_OFFSET_RATIO = 0.0
DEFAULT_CURVE_RESOLUTION = 32

SOCKETS = (
    (SOCKET_COLLECTION, "NodeSocketCollection", None, None, None),
    (SOCKET_RATIO, "NodeSocketFloat", DEFAULT_RATIO, 0.01, 10.0),
    (SOCKET_MAX_GAP, "NodeSocketFloat", DEFAULT_MAX_GAP, 0.0, 1000.0),
    (SOCKET_OFFSET_RATIO, "NodeSocketFloat", DEFAULT_OFFSET_RATIO, -1.0, 1.0),
    (SOCKET_CURVE_RESOLUTION, "NodeSocketInt", DEFAULT_CURVE_RESOLUTION, 3, 128),
)

SETTINGS_SOCKET_ATTRS = (
    (SOCKET_RATIO, "radius_scale"),
    (SOCKET_MAX_GAP, "max_gap"),
    (SOCKET_OFFSET_RATIO, "offset_ratio"),
    (SOCKET_CURVE_RESOLUTION, "curve_resolution"),
)


def ensure_node_group() -> GeometryNodeTree:
    return generator_nodes.ensure_node_group(
        NODE_GROUP_NAME,
        SCHEMA_KEY,
        SOCKETS,
    )


def build_node_group(ng: GeometryNodeTree) -> GeometryNodeTree:
    return generator_nodes.build_node_group(ng, SCHEMA_KEY, SOCKETS)


def new_modifier(context, ob, name: str, settings) -> NodesModifier:
    values = settings_to_values(settings)
    return generator_nodes.new_modifier(context, ob, name, ensure_node_group, values)


def settings_to_values(settings) -> dict:
    return generator_nodes.settings_to_values(settings, SETTINGS_SOCKET_ATTRS)


socket_identifiers = generator_nodes.socket_identifiers
