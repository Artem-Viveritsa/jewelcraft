# SPDX-License-Identifier: GPL-3.0-or-later


from bpy.types import GeometryNodeTree, NodesModifier

from .. import generator_nodes


NODE_GROUP_NAME = "JewelCraft Cutters Generator"
SCHEMA_KEY = "jewelcraft_cutters_schema"

SOCKET_COLLECTION = "Gem Collection"
SOCKET_INCLUDE_HANDLE = "Handle"
SOCKET_INCLUDE_HOLE = "Hole"
SOCKET_USE_CURVE_SEAT = "Curve Seat"

DESCRIPTION_COLLECTION = "Collection containing gem objects"

SOCKETS = (
    (SOCKET_COLLECTION, "NodeSocketCollection", None, None, None, DESCRIPTION_COLLECTION),
    generator_nodes.INTERACTIVE_SOCKET,
    (SOCKET_INCLUDE_HANDLE, "NodeSocketBool", True, None, None, "Add a handle above the girdle"),
    ("Handle Top", "NodeSocketFloat", 0.0, None, None, "Top of the handle"),
    ("Handle Length", "NodeSocketFloat", 0.0, None, None, "Length of the handle"),
    ("Handle Width", "NodeSocketFloat", 0.0, None, None, "Width of the handle"),
    ("Handle Bottom", "NodeSocketFloat", 0.0, None, None, "Bottom of the handle"),
    ("Handle Position Offset", "NodeSocketFloat", 0.0, None, None, "Move the handle along the gem length"),
    (
        "Girdle Top",
        "NodeSocketFloat",
        0.0,
        None,
        None,
        "Top of the girdle section, table level when there is no handle",
    ),
    ("Girdle Length Offset", "NodeSocketFloat", 0.0, None, None, "Girdle length offset relative to the gem size"),
    ("Girdle Width Offset", "NodeSocketFloat", 0.0, None, None, "Girdle width offset relative to the gem size"),
    ("Girdle Bottom", "NodeSocketFloat", 0.0, None, None, "Bottom of the girdle section"),
    (SOCKET_INCLUDE_HOLE, "NodeSocketBool", True, None, None, "Add a hole under the girdle"),
    ("Hole Top", "NodeSocketFloat", 0.0, None, None, "Top of the hole, culet level when there is no hole"),
    ("Hole Length", "NodeSocketFloat", 0.0, None, None, "Length of the hole"),
    ("Hole Width", "NodeSocketFloat", 0.0, None, None, "Width of the hole"),
    ("Hole Bottom", "NodeSocketFloat", 0.0, None, None, "Bottom of the hole"),
    ("Hole Position Offset", "NodeSocketFloat", 0.0, None, None, "Move the hole along the gem length"),
    ("Seat Depth", "NodeSocketFloat", 0.0, 0.0, 1.0, "Lower the girdle and the hole, relative to the gem height"),
    (
        SOCKET_USE_CURVE_SEAT,
        "NodeSocketBool",
        False,
        None,
        None,
        "Round the transition between the girdle and the hole",
    ),
    ("Curve Seat Profile", "NodeSocketFloat", 0.5, 0.15, 1.0, "Profile of the curved seat"),
    ("Curve Seat Segments", "NodeSocketInt", 15, 2, 30, "Number of segments of the curved seat"),
    ("Curve Profile Factor", "NodeSocketFloat", 0.0, 0.0, 1.0, "Amount of curvature of the cutter sides"),
    ("Curve Profile Segments", "NodeSocketInt", 10, 1, 30, "Number of segments of the curved sides"),
    ("Bevel Corners Width", "NodeSocketFloat", 0.0, 0.0, None, "Width of the corner bevel"),
    ("Bevel Corners Percent", "NodeSocketFloat", 0.0, 0.0, 50.0, "Width of the corner bevel, relative to the side"),
    ("Bevel Corners Segments", "NodeSocketInt", 1, 1, 30, "Number of segments of the corner bevel"),
    ("Bevel Corners Profile", "NodeSocketFloat", 0.5, 0.15, 1.0, "Profile of the corner bevel"),
    ("Profile Factor 1", "NodeSocketFloat", 1.0, 0.0, 2.0, "Shape factor of the cutter profile"),
    ("Profile Factor 2", "NodeSocketFloat", 1.0, 0.0, 2.0, "Shape factor of the cutter profile"),
    ("Profile Factor 3", "NodeSocketFloat", 1.0, 0.0, 2.0, "Shape factor of the cutter profile"),
    ("Detalization", "NodeSocketInt", 32, 12, 64, "Number of segments of the rounded parts"),
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
