# SPDX-License-Identifier: GPL-3.0-or-later


from __future__ import annotations

from dataclasses import dataclass, field

import bmesh
from bpy.types import Collection, Depsgraph, Object
from mathutils import Matrix, Vector

from ...lib import gemlib
from .. import generator_mesh
from ..add_cutter import cutter_mesh
from ..add_cutter.cutter_presets import init_presets
from . import cutters_nodes

PROP_SOURCE_COLLECTION = "jewelcraft_cutters_source_collection"
PROP_INCLUDE_HANDLE = "jewelcraft_cutters_include_handle"
PROP_INCLUDE_HOLE = "jewelcraft_cutters_include_hole"
PROP_CURVE_SEAT_MODE = "jewelcraft_cutters_curve_seat_mode"
PROP_SIGNATURE = "jewelcraft_cutters_signature"

CURVE_SEAT_PRESET = "PRESET"
CURVE_SEAT_OFF = "OFF"
CURVE_SEAT_ON = "ON"
DEFAULT_GEM_DIMENSIONS = Vector((1.0, 1.0, 0.6))

_UPDATE_STATE = {}


@dataclass(slots=True)
class _Dimensions:
    x: float = 0.0
    y: float = 0.0
    z1: float = 0.0
    z2: float = 0.0


@dataclass(slots=True)
class _CutterSettings:
    cut: str
    shape: int
    detalization: int = 32
    use_handle: bool = True
    handle_dim: _Dimensions = field(default_factory=_Dimensions)
    handle_shift: float = 0.0
    girdle_dim: _Dimensions = field(default_factory=_Dimensions)
    table_z: float = 0.0
    use_hole: bool = True
    hole_dim: _Dimensions = field(default_factory=_Dimensions)
    hole_shift: float = 0.0
    culet_z: float = 0.0
    culet_size: float = 0.0
    seat_depth: float = 0.0
    use_curve_seat: bool = False
    curve_seat_profile: float = 0.5
    curve_seat_segments: int = 15
    curve_profile_factor: float = 0.0
    curve_profile_segments: int = 10
    bevel_corners_width: float = 0.0
    bevel_corners_percent: float = 0.0
    bevel_corners_segments: int = 1
    bevel_corners_profile: float = 0.5
    mul_1: float = 1.0
    mul_2: float = 1.0
    mul_3: float = 1.0


def create_object(
    context,
    coll: Collection,
    source_coll: Collection,
) -> Object:
    gems = _source_gems(source_coll)
    ob = generator_mesh.create_object(
        context,
        coll,
        source_coll,
        "Cutters Generator",
        "Cutter",
        PROP_SOURCE_COLLECTION,
    )

    include_handle = True
    include_hole = True
    use_curve_seat = False

    ob[PROP_INCLUDE_HANDLE] = include_handle
    ob[PROP_INCLUDE_HOLE] = include_hole
    ob[PROP_CURVE_SEAT_MODE] = CURVE_SEAT_ON if use_curve_seat else CURVE_SEAT_OFF

    settings = (
        _preset_settings_for_gem(gems[0], include_handle, include_hole, use_curve_seat)
        if gems
        else _default_preset_settings(include_handle, include_hole, use_curve_seat)
    )
    cutters_nodes.new_modifier(context, ob, "Cutters Generator", settings)

    handler_add()
    update_object(ob)

    return generator_mesh.select_object(context, ob)


def handler_add() -> None:
    generator_mesh.handler_add(cutters_auto_update)


def handler_del() -> None:
    generator_mesh.handler_del(cutters_auto_update)


def cutters_auto_update(scene, depsgraph: Depsgraph) -> None:
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

    _sync_properties(ob, modifier_values, source_coll)

    gems = _source_gems(source_coll)
    signature = _signature(ob, gems, modifier_values)

    if ob.get(PROP_SIGNATURE) == signature:
        return

    bm = bmesh.new()
    reference_dim = gems[0].dimensions if gems else None

    try:
        for gem_ob in gems:
            settings = _settings_for_gem(gem_ob, modifier_values, reference_dim)
            gem_bm = cutter_mesh.get(settings, gem_ob.dimensions, reference_dim)

            try:
                _append_bmesh(bm, gem_bm, _gem_matrix(gem_ob))
            finally:
                gem_bm.free()

        ob.data.clear_geometry()
        bm.to_mesh(ob.data)
        ob.data.update()
        ob[PROP_SIGNATURE] = signature
    finally:
        bm.free()


def _source_gems(coll: Collection) -> list[Object]:
    return [ob for ob in coll.all_objects if ob.type == "MESH" and "gem" in ob]


def _preset_settings_for_gem(
    gem_ob: Object,
    include_handle: bool,
    include_hole: bool,
    use_curve_seat: bool,
) -> _CutterSettings:
    cut, shape = _gem_cut_shape(gem_ob)
    settings = _CutterSettings(cut, shape)
    init_presets(settings, gem_ob.dimensions)

    settings.use_handle = include_handle
    settings.use_hole = include_hole
    settings.use_curve_seat = use_curve_seat

    return settings


def _settings_for_gem(gem_ob: Object, modifier_values: dict, reference_dim) -> _CutterSettings:
    cut, shape = _gem_cut_shape(gem_ob)
    settings = _CutterSettings(cut, shape)
    init_presets(settings, reference_dim)
    _apply_settings_values(settings, modifier_values)
    return settings


def _gem_cut_shape(gem_ob: Object) -> tuple[str, int]:
    cut = gem_ob["gem"].get("cut", "ROUND")

    try:
        return cut, gemlib.CUTS[cut].shape
    except KeyError:
        return "ROUND", gemlib.SHAPE_ROUND


def _apply_settings_values(settings: _CutterSettings, modifier_values: dict) -> None:
    for socket, attr in cutters_nodes.SETTINGS_SOCKET_ATTRS:
        target = settings
        path = attr.split(".")

        for name in path[:-1]:
            target = getattr(target, name)

        setattr(target, path[-1], modifier_values[socket])


def _modifier_values(ob: Object) -> dict:
    source_coll = generator_mesh.source_collection(ob, PROP_SOURCE_COLLECTION)
    values = _default_modifier_values()
    values["Handle"] = bool(ob.get(PROP_INCLUDE_HANDLE, values["Handle"]))
    values["Hole"] = bool(ob.get(PROP_INCLUDE_HOLE, values["Hole"]))
    values["Curve Seat"] = ob.get(PROP_CURVE_SEAT_MODE, CURVE_SEAT_OFF) == CURVE_SEAT_ON

    if source_coll is not None:
        gems = _source_gems(source_coll)

        if gems:
            values = _default_modifier_values(
                _preset_settings_for_gem(
                    gems[0],
                    values["Handle"],
                    values["Hole"],
                    values["Curve Seat"],
                )
            )

    legacy_names = {
        "Handle Length": ("Handle Size",),
        "Handle Width": ("Handle Size",),
        "Girdle Length Offset": ("Girdle Size Offset",),
        "Girdle Width Offset": ("Girdle Size Offset",),
        "Hole Length": ("Hole Size",),
        "Hole Width": ("Hole Size",),
    }

    generator_mesh.apply_modifier_socket_values(
        values,
        generator_mesh.modifier(ob, cutters_nodes),
        cutters_nodes,
        legacy_names,
    )
    values["source_coll"] = source_coll
    return values


def _default_modifier_values(settings: _CutterSettings | None = None) -> dict:
    if settings is None:
        settings = _default_preset_settings(True, True, False)

    return cutters_nodes.settings_to_values(settings)


def _default_preset_settings(
    include_handle: bool,
    include_hole: bool,
    use_curve_seat: bool,
) -> _CutterSettings:
    settings = _CutterSettings("ROUND", gemlib.SHAPE_ROUND)
    init_presets(settings, DEFAULT_GEM_DIMENSIONS)

    settings.use_handle = include_handle
    settings.use_hole = include_hole
    settings.use_curve_seat = use_curve_seat

    return settings


def _sync_properties(ob: Object, modifier_values: dict, source_coll: Collection) -> None:
    ob[PROP_SOURCE_COLLECTION] = source_coll.name
    ob[PROP_INCLUDE_HANDLE] = modifier_values["Handle"]
    ob[PROP_INCLUDE_HOLE] = modifier_values["Hole"]
    ob[PROP_CURVE_SEAT_MODE] = CURVE_SEAT_ON if modifier_values["Curve Seat"] else CURVE_SEAT_OFF


def _append_bmesh(dst, src, matrix: Matrix) -> None:
    src.verts.ensure_lookup_table()
    src.faces.ensure_lookup_table()

    verts = {v: dst.verts.new(matrix @ v.co) for v in src.verts}

    for face in src.faces:
        try:
            dst.faces.new(tuple(verts[v] for v in face.verts))
        except ValueError:
            pass


def _gem_matrix(ob: Object) -> Matrix:
    loc, rot, _scale = ob.matrix_world.decompose()
    return Matrix.LocRotScale(loc, rot, (1.0, 1.0, 1.0))


def _signature(generator: Object, gems: list[Object], modifier_values: dict) -> str:
    parts = generator_mesh.signature_parts(generator, modifier_values, PROP_SOURCE_COLLECTION)

    for ob in gems:
        matrix_values = tuple(round(value, 6) for row in ob.matrix_world for value in row)
        dim_values = tuple(round(value, 6) for value in ob.dimensions)
        cut = ob.get("gem", {}).get("cut", "ROUND")
        parts.append(f"{ob.name}:{cut}:{matrix_values}:{dim_values}")

    return "|".join(parts)
