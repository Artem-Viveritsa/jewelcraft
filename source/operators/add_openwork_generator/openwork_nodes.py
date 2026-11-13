# SPDX-License-Identifier: GPL-3.0-or-later


from bpy.types import GeometryNodeTree, NodesModifier

from .. import generator_nodes


NODE_GROUP_NAME = "JewelCraft Openwork Between Gemstones"
SCHEMA_KEY = "jewelcraft_openwork_schema"

SOCKET_COLLECTION = "Gem Collection"
SOCKET_MAX_GAP = "Max Gap"
SOCKET_GAP = "Gap"
SOCKET_MERGE_DISTANCE = "Merge Distance"
SOCKET_BASE_OFFSET = "Base Offset"
SOCKET_CORNER_OFFSET = "Corner Offset"
SOCKET_SCALE = "Scale"
SOCKET_COMMON_OFFSET = "Common Offset"
SOCKET_SNAP = "Snap"
SOCKET_SNAP_COLLECTION = "Snap Collection"
SOCKET_SNAP_OFFSET = "Snap Offset"

DEFAULT_MAX_GAP = 0.5
DEFAULT_GAP = 0.6
DEFAULT_MERGE_DISTANCE = 0.3
DEFAULT_BASE_OFFSET = -1.5
DEFAULT_CORNER_OFFSET = 0.0
DEFAULT_SCALE = 1.0
DEFAULT_COMMON_OFFSET = True
DEFAULT_SNAP = False
DEFAULT_SNAP_OFFSET = 0.0

DESCRIPTION_COLLECTION = "Collection containing gem objects, including gems made with Mirror Instance"

SOCKETS = (
    (SOCKET_COLLECTION, "NodeSocketCollection", None, None, None, DESCRIPTION_COLLECTION),
    (
        SOCKET_MAX_GAP,
        "NodeSocketFloat",
        DEFAULT_MAX_GAP,
        0.0,
        1000.0,
        "Largest distance between two gems for them to be treated as neighbours",
    ),
    (
        SOCKET_GAP,
        "NodeSocketFloat",
        DEFAULT_GAP,
        0.1,
        1.0,
        "Distance between the two points placed between neighbouring gems, relative to gem size",
    ),
    (
        SOCKET_MERGE_DISTANCE,
        "NodeSocketFloat",
        DEFAULT_MERGE_DISTANCE,
        0.0,
        1000.0,
        "Join points located at specified distance into one corner shared by several gems",
    ),
    (
        SOCKET_BASE_OFFSET,
        "NodeSocketFloat",
        DEFAULT_BASE_OFFSET,
        -1000.0,
        1000.0,
        (
            "Move the base polygon along the gem normal, negative values move it under the gem. "
            "With snap enabled, the search for the nearest surface starts from this position"
        ),
    ),
    (
        SOCKET_CORNER_OFFSET,
        "NodeSocketFloat",
        DEFAULT_CORNER_OFFSET,
        -1000.0,
        1000.0,
        "Move the pyramid tip from the gem center along the gem normal, negative values move it under the gem",
    ),
    (
        SOCKET_SCALE,
        "NodeSocketFloat",
        DEFAULT_SCALE,
        0.1,
        2.0,
        "Scale the base polygon of every pyramid around its center, works with individual offsets only",
    ),
    (
        SOCKET_COMMON_OFFSET,
        "NodeSocketBool",
        DEFAULT_COMMON_OFFSET,
        None,
        None,
        (
            "Offset all base polygons together, so neighbouring pyramids share corners. "
            "Turn off to offset every pyramid separately along its gem normal, pyramids can then intersect"
        ),
    ),
    (
        SOCKET_SNAP,
        "NodeSocketBool",
        DEFAULT_SNAP,
        None,
        None,
        "Snap every base polygon point to the nearest surface of the snap collection",
    ),
    (
        SOCKET_SNAP_COLLECTION,
        "NodeSocketCollection",
        None,
        None,
        None,
        "Collection of mesh objects, every base point snaps to the nearest surface among them",
    ),
    (
        SOCKET_SNAP_OFFSET,
        "NodeSocketFloat",
        DEFAULT_SNAP_OFFSET,
        -1000.0,
        1000.0,
        "Additional offset from the snapped surface along its normal",
    ),
)

SETTINGS_SOCKET_ATTRS = (
    (SOCKET_MAX_GAP, "max_gap"),
    (SOCKET_GAP, "gap"),
    (SOCKET_MERGE_DISTANCE, "merge_distance"),
    (SOCKET_BASE_OFFSET, "base_offset"),
    (SOCKET_CORNER_OFFSET, "corner_offset"),
    (SOCKET_SCALE, "scale"),
    (SOCKET_COMMON_OFFSET, "common_offset"),
    (SOCKET_SNAP, "snap"),
    (SOCKET_SNAP_OFFSET, "snap_offset"),
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
