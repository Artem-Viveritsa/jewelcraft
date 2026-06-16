# SPDX-License-Identifier: GPL-3.0-or-later


from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import cos, sin, tau

from bpy.types import Collection, Depsgraph, Object
from mathutils import Vector

from .. import generator_mesh
from . import channels_nodes

PROP_SOURCE_COLLECTION = "jewelcraft_channels_source_collection"
PROP_SIGNATURE = "jewelcraft_channels_signature"

_EPS = 1e-9
_MAX_CONNECTIONS = 8192
_GENERATOR_SOURCE_PROPERTIES = {
    PROP_SOURCE_COLLECTION,
    "jewelcraft_cutters_source_collection",
}

_UPDATE_STATE = {}


@dataclass(slots=True)
class _ChannelSettings:
    radius_scale: float = channels_nodes.DEFAULT_RATIO
    max_gap: float = channels_nodes.DEFAULT_MAX_GAP
    offset_ratio: float = channels_nodes.DEFAULT_OFFSET_RATIO
    curve_resolution: int = channels_nodes.DEFAULT_CURVE_RESOLUTION


@dataclass(slots=True)
class _ObjectInfo:
    location: Vector
    normal: Vector
    radius: float

    @classmethod
    def from_object(cls, ob: Object) -> "_ObjectInfo":
        return cls(ob.matrix_world.translation.copy(), _object_normal(ob), _object_radius(ob))


def create_object(
    context,
    coll: Collection,
    source_coll: Collection,
    ratio: float = channels_nodes.DEFAULT_RATIO,
    max_gap: float = channels_nodes.DEFAULT_MAX_GAP,
    offset_ratio: float = channels_nodes.DEFAULT_OFFSET_RATIO,
    curve_resolution: int = channels_nodes.DEFAULT_CURVE_RESOLUTION,
) -> Object:
    ob = generator_mesh.create_object(
        context,
        coll,
        source_coll,
        "Channels Generator",
        "Channels",
        PROP_SOURCE_COLLECTION,
    )
    settings = _ChannelSettings(ratio, max_gap, offset_ratio, curve_resolution)
    channels_nodes.new_modifier(context, ob, "Channels Generator", settings)

    handler_add()
    update_object(ob)

    return generator_mesh.select_object(context, ob)


def handler_add() -> None:
    generator_mesh.handler_add(channels_auto_update)


def handler_del() -> None:
    generator_mesh.handler_del(channels_auto_update)


def channels_auto_update(scene, depsgraph: Depsgraph) -> None:
    generator_mesh.auto_update(
        scene,
        depsgraph,
        PROP_SOURCE_COLLECTION,
        update_object,
        handler_del,
        _UPDATE_STATE,
    )


def update_object(ob: Object, depsgraph: Depsgraph | None = None) -> None:
    modifier_values = _modifier_values(ob)
    source_coll = modifier_values["source_coll"]

    if source_coll is None:
        generator_mesh.clear_mesh(ob, PROP_SIGNATURE)
        return

    ob[PROP_SOURCE_COLLECTION] = source_coll.name

    source_objects = _source_objects(source_coll)
    signature = _signature(ob, source_objects, modifier_values)

    if ob.get(PROP_SIGNATURE) == signature:
        return

    mesh_data = _build_channels_mesh(
        source_objects,
        modifier_values["Radius Scale"],
        modifier_values["Max Gap"],
        modifier_values["Offset Ratio"],
        modifier_values["Curve Resolution"],
    )

    ob.data.clear_geometry()
    ob.data.from_pydata(*mesh_data)
    ob.data.update()
    ob[PROP_SIGNATURE] = signature


def _source_objects(coll: Collection) -> list[Object]:
    source_types = {"MESH", "CURVE", "SURFACE", "META", "FONT"}
    return [
        ob
        for ob in coll.all_objects
        if ob.type in source_types and not any(prop in ob for prop in _GENERATOR_SOURCE_PROPERTIES)
    ]


def _build_channels_mesh(
    objects: list[Object],
    radius_scale: float,
    max_gap: float,
    offset_ratio: float,
    curve_resolution: int,
):
    verts = []
    faces = []
    infos = [_ObjectInfo.from_object(ob) for ob in objects]
    resolution = max(3, int(curve_resolution))
    connection_count = 0

    for first, second in combinations(infos, 2):
        if first.radius <= _EPS or second.radius <= _EPS:
            continue

        distance = (first.location - second.location).length

        if distance > first.radius + second.radius + max_gap:
            continue

        first_point = first.location + first.normal * (first.radius * offset_ratio)
        second_point = second.location + second.normal * (second.radius * offset_ratio)
        first_channel_radius = first.radius * radius_scale
        second_channel_radius = second.radius * radius_scale

        if first_channel_radius <= _EPS or second_channel_radius <= _EPS:
            continue

        _append_channel(
            verts,
            faces,
            first_point,
            second_point,
            first_channel_radius,
            second_channel_radius,
            resolution,
        )

        connection_count += 1

        if connection_count > _MAX_CONNECTIONS:
            raise ValueError(
                "Too many channel connections found. Reduce Max Gap or collection size"
            )

    return verts, [], faces


def _append_channel(
    verts: list[Vector],
    faces: list[tuple[int, ...]],
    first_point: Vector,
    second_point: Vector,
    first_radius: float,
    second_radius: float,
    resolution: int,
) -> None:
    axis = second_point - first_point

    if axis.length_squared <= _EPS:
        return

    axis.normalize()
    normal, bitangent = _circle_basis(axis)
    first_start = len(verts)
    second_start = first_start + resolution

    ring_dirs = []

    for i in range(resolution):
        angle = tau * i / resolution
        ring_dirs.append(normal * cos(angle) + bitangent * sin(angle))

    verts.extend(first_point + direction * first_radius for direction in ring_dirs)
    verts.extend(second_point + direction * second_radius for direction in ring_dirs)

    for i in range(resolution):
        j = (i + 1) % resolution
        faces.append((first_start + i, first_start + j, second_start + j, second_start + i))

    faces.append(tuple(reversed(range(first_start, first_start + resolution))))
    faces.append(tuple(range(second_start, second_start + resolution)))


def _circle_basis(axis: Vector) -> tuple[Vector, Vector]:
    reference = Vector((0.0, 0.0, 1.0))

    if abs(axis.dot(reference)) > 0.999:
        reference = Vector((1.0, 0.0, 0.0))

    normal = axis.cross(reference)
    normal.normalize()
    bitangent = axis.cross(normal)
    bitangent.normalize()

    return normal, bitangent


def _object_normal(ob: Object) -> Vector:
    normal = ob.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))

    if normal.length_squared <= _EPS:
        return Vector((0.0, 0.0, 1.0))

    normal.normalize()
    return normal


def _object_radius(ob: Object) -> float:
    try:
        xs = [co[0] for co in ob.bound_box]
    except AttributeError:
        return max(ob.dimensions.xy) * 0.5

    local_diameter = max(xs) - min(xs)
    scale_x = abs(ob.matrix_world.to_scale().x)
    radius = local_diameter * scale_x * 0.5

    if radius <= _EPS:
        radius = max(ob.dimensions.xy) * 0.5

    return radius


def _modifier_values(ob: Object) -> dict:
    source_coll = generator_mesh.source_collection(ob, PROP_SOURCE_COLLECTION)
    values = _default_modifier_values()
    generator_mesh.apply_modifier_socket_values(
        values,
        generator_mesh.modifier(ob, channels_nodes),
        channels_nodes,
    )
    values["source_coll"] = source_coll
    return values


def _default_modifier_values() -> dict:
    return channels_nodes.settings_to_values(_ChannelSettings())


def _signature(generator: Object, source_objects: list[Object], modifier_values: dict) -> str:
    parts = generator_mesh.signature_parts(generator, modifier_values, PROP_SOURCE_COLLECTION)

    for ob in source_objects:
        matrix_values = tuple(round(value, 6) for row in ob.matrix_world for value in row)
        dim_values = tuple(round(value, 6) for value in ob.dimensions)
        bbox_values = tuple(round(value, 6) for corner in ob.bound_box for value in corner)
        parts.append(f"{ob.name}:{matrix_values}:{dim_values}:{bbox_values}")

    return "|".join(parts)
