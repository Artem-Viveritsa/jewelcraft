# SPDX-License-Identifier: GPL-3.0-or-later


from bpy.types import GeometryNodeTree, NodesModifier

from .. import generator_nodes


NODE_GROUP_NAME = "JewelCraft Cutters Generator"
SCHEMA_KEY = "jewelcraft_cutters_schema"

SOCKET_COLLECTION = "Gem Collection"
SOCKET_INCLUDE_HANDLE = "Handle"
SOCKET_INCLUDE_HOLE = "Hole"
SOCKET_USE_CURVE_SEAT = "Curve Seat"

SOCKETS = (
    (SOCKET_COLLECTION, "NodeSocketCollection", None, None, None),
    (SOCKET_INCLUDE_HANDLE, "NodeSocketBool", True, None, None),
    ("Handle Top", "NodeSocketFloat", 0.0, None, None),
    ("Handle Length", "NodeSocketFloat", 0.0, None, None),
    ("Handle Width", "NodeSocketFloat", 0.0, None, None),
    ("Handle Bottom", "NodeSocketFloat", 0.0, None, None),
    ("Handle Position Offset", "NodeSocketFloat", 0.0, None, None),
    ("Girdle Top", "NodeSocketFloat", 0.0, None, None),
    ("Girdle Length Offset", "NodeSocketFloat", 0.0, None, None),
    ("Girdle Width Offset", "NodeSocketFloat", 0.0, None, None),
    ("Girdle Bottom", "NodeSocketFloat", 0.0, None, None),
    (SOCKET_INCLUDE_HOLE, "NodeSocketBool", True, None, None),
    ("Hole Top", "NodeSocketFloat", 0.0, None, None),
    ("Hole Length", "NodeSocketFloat", 0.0, None, None),
    ("Hole Width", "NodeSocketFloat", 0.0, None, None),
    ("Hole Bottom", "NodeSocketFloat", 0.0, None, None),
    ("Hole Position Offset", "NodeSocketFloat", 0.0, None, None),
    ("Seat Depth", "NodeSocketFloat", 0.0, 0.0, 1.0),
    (SOCKET_USE_CURVE_SEAT, "NodeSocketBool", False, None, None),
    ("Curve Seat Profile", "NodeSocketFloat", 0.5, 0.15, 1.0),
    ("Curve Seat Segments", "NodeSocketInt", 15, 2, 30),
    ("Curve Profile Factor", "NodeSocketFloat", 0.0, 0.0, 1.0),
    ("Curve Profile Segments", "NodeSocketInt", 10, 1, 30),
    ("Bevel Corners Width", "NodeSocketFloat", 0.0, 0.0, None),
    ("Bevel Corners Percent", "NodeSocketFloat", 0.0, 0.0, 50.0),
    ("Bevel Corners Segments", "NodeSocketInt", 1, 1, 30),
    ("Bevel Corners Profile", "NodeSocketFloat", 0.5, 0.15, 1.0),
    ("Profile Factor 1", "NodeSocketFloat", 1.0, 0.0, 2.0),
    ("Profile Factor 2", "NodeSocketFloat", 1.0, 0.0, 2.0),
    ("Profile Factor 3", "NodeSocketFloat", 1.0, 0.0, 2.0),
    ("Detalization", "NodeSocketInt", 32, 12, 64),
)

SETTINGS_SOCKET_ATTRS = (
    (SOCKET_INCLUDE_HANDLE, "use_handle"),
    ("Handle Top", "handle_dim.z1"),
    ("Handle Length", "handle_dim.y"),
    ("Handle Width", "handle_dim.x"),
    ("Handle Bottom", "handle_dim.z2"),
    ("Handle Position Offset", "handle_shift"),
    ("Girdle Top", "girdle_dim.z1"),
    ("Girdle Length Offset", "girdle_dim.y"),
    ("Girdle Width Offset", "girdle_dim.x"),
    ("Girdle Bottom", "girdle_dim.z2"),
    (SOCKET_INCLUDE_HOLE, "use_hole"),
    ("Hole Top", "hole_dim.z1"),
    ("Hole Length", "hole_dim.y"),
    ("Hole Width", "hole_dim.x"),
    ("Hole Bottom", "hole_dim.z2"),
    ("Hole Position Offset", "hole_shift"),
    ("Seat Depth", "seat_depth"),
    (SOCKET_USE_CURVE_SEAT, "use_curve_seat"),
    ("Curve Seat Profile", "curve_seat_profile"),
    ("Curve Seat Segments", "curve_seat_segments"),
    ("Curve Profile Factor", "curve_profile_factor"),
    ("Curve Profile Segments", "curve_profile_segments"),
    ("Bevel Corners Width", "bevel_corners_width"),
    ("Bevel Corners Percent", "bevel_corners_percent"),
    ("Bevel Corners Segments", "bevel_corners_segments"),
    ("Bevel Corners Profile", "bevel_corners_profile"),
    ("Profile Factor 1", "mul_1"),
    ("Profile Factor 2", "mul_2"),
    ("Profile Factor 3", "mul_3"),
    ("Detalization", "detalization"),
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
