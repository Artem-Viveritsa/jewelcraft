# SPDX-License-Identifier: GPL-3.0-or-later


from __future__ import annotations

import hashlib
from array import array
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from math import atan2, cos, pi, radians, sin, tau

import bpy
from bpy.types import Collection, Depsgraph, Object
from mathutils import Matrix, Vector, kdtree
from mathutils.bvhtree import BVHTree

from ...lib import gem_neighbors
from .. import generator_mesh
from . import openwork_nodes


PROP_SOURCE_COLLECTION = "jewelcraft_openwork_source_collection"
PROP_SIGNATURE = "jewelcraft_openwork_signature"
PROP_GEM_NAMES = "jewelcraft_openwork_gems"

ATTR_GEM_INDEX = "gem_index"
ATTR_IS_BASE = "is_base"

_EPS = 1e-6
_OPEN_SIDE_ANGLE = radians(100)
_CHAMFER_RATIO = 0.8
_CHAMFER_MAX_TURN = radians(100)
_COLLINEAR_DISTANCE = 0.02

_UPDATE_STATE = {}

_Cell = list[tuple[tuple, Vector]]


@dataclass(slots=True)
class _OpenworkSettings:
    max_gap: float = openwork_nodes.DEFAULT_MAX_GAP
    gap: float = openwork_nodes.DEFAULT_GAP
    merge_distance: float = openwork_nodes.DEFAULT_MERGE_DISTANCE
    base_offset: float = openwork_nodes.DEFAULT_BASE_OFFSET
    corner_offset: float = openwork_nodes.DEFAULT_CORNER_OFFSET
    scale: float = openwork_nodes.DEFAULT_SCALE
    common_offset: bool = openwork_nodes.DEFAULT_COMMON_OFFSET
    snap: bool = openwork_nodes.DEFAULT_SNAP
    snap_offset: float = openwork_nodes.DEFAULT_SNAP_OFFSET


def create_object(
    context,
    coll: Collection,
    source_coll: Collection,
    max_gap: float = openwork_nodes.DEFAULT_MAX_GAP,
    gap: float = openwork_nodes.DEFAULT_GAP,
    merge_distance: float = openwork_nodes.DEFAULT_MERGE_DISTANCE,
    base_offset: float = openwork_nodes.DEFAULT_BASE_OFFSET,
    corner_offset: float = openwork_nodes.DEFAULT_CORNER_OFFSET,
    scale: float = openwork_nodes.DEFAULT_SCALE,
    common_offset: bool = openwork_nodes.DEFAULT_COMMON_OFFSET,
    snap: bool = openwork_nodes.DEFAULT_SNAP,
    snap_offset: float = openwork_nodes.DEFAULT_SNAP_OFFSET,
) -> Object:
    ob = generator_mesh.create_object(
        context,
        coll,
        source_coll,
        "Openwork Generator",
        "Openwork",
        PROP_SOURCE_COLLECTION,
    )
    settings = _OpenworkSettings(
        max_gap, gap, merge_distance, base_offset, corner_offset, scale, common_offset, snap, snap_offset
    )
    openwork_nodes.new_modifier(context, ob, "Openwork Generator", settings)

    handler_add()
    update_object(ob)

    return generator_mesh.select_object(context, ob)


def handler_add() -> None:
    generator_mesh.handler_add(openwork_auto_update)


def handler_del() -> None:
    generator_mesh.handler_del(openwork_auto_update)


def openwork_auto_update(scene, depsgraph: Depsgraph) -> None:
    generator_mesh.auto_update(
        scene,
        depsgraph,
        PROP_SOURCE_COLLECTION,
        update_object,
        handler_del,
        _UPDATE_STATE,
    )


def update_object(ob: Object, depsgraph: Depsgraph | None = None, force: bool = False) -> None:
    modifier_values = _modifier_values(ob)

    if not generator_mesh.is_update_allowed(modifier_values, force):
        return

    source_coll = modifier_values["source_coll"]

    if source_coll is None:
        generator_mesh.clear_mesh(ob, PROP_SIGNATURE)
        return

    ob[PROP_SOURCE_COLLECTION] = source_coll.name

    depsgraph = depsgraph or bpy.context.evaluated_depsgraph_get()
    gems = _source_gems(source_coll, depsgraph)
    targets = _snap_targets(modifier_values["Snap Collection"], ob) if modifier_values["Snap"] else []
    signature = _signature(ob, gems, modifier_values, targets, depsgraph)

    if ob.get(PROP_SIGNATURE) == signature:
        return

    verts, faces, gem_indices, is_base = build_openwork_mesh(
        [gem_neighbors.matrix_to_gem_info(matrix, dimensions) for _, matrix, dimensions in gems],
        modifier_values["Max Gap"],
        modifier_values["Gap"],
        modifier_values["Merge Distance"],
        modifier_values["Base Offset"],
        modifier_values["Corner Offset"],
        modifier_values["Scale"],
        modifier_values["Common Offset"],
        _snap_func(targets, modifier_values["Snap Offset"], depsgraph),
    )

    me = ob.data
    me.clear_geometry()
    me.from_pydata(verts, [], faces)
    _set_face_attribute(me, ATTR_GEM_INDEX, "INT", gem_indices)
    _set_face_attribute(me, ATTR_IS_BASE, "BOOLEAN", is_base)
    me.update()

    ob[PROP_GEM_NAMES] = [name for name, _, _ in gems]
    ob[PROP_SIGNATURE] = signature


def _set_face_attribute(me, name: str, data_type: str, values: list) -> None:
    if name in me.attributes:
        me.attributes.remove(me.attributes[name])

    attribute = me.attributes.new(name, data_type, "FACE")
    attribute.data.foreach_set("value", values)


def _source_gems(coll: Collection, depsgraph: Depsgraph) -> list[tuple[str, Matrix, tuple[float, float]]]:
    originals = set(coll.all_objects)
    gems = [
        (ob.name, ob.matrix_world.copy(), tuple(ob.dimensions.xy))
        for ob in originals
        if ob.type == "MESH" and "gem" in ob
    ]

    for instance in depsgraph.object_instances:
        if not instance.is_instance:
            continue

        ob = instance.object

        if ob.type != "MESH" or "gem" not in ob or ob.original not in originals:
            continue

        matrix = instance.matrix_world.copy()
        scale = matrix.to_scale()
        xs = [corner[0] for corner in ob.bound_box]
        ys = [corner[1] for corner in ob.bound_box]
        dimensions = ((max(xs) - min(xs)) * abs(scale.x), (max(ys) - min(ys)) * abs(scale.y))
        gems.append((ob.name, matrix, dimensions))

    gems.sort(key=lambda gem: gem[0])

    return gems


def build_openwork_mesh(
    gems: list[gem_neighbors.GemInfo],
    max_gap: float,
    gap: float,
    merge_distance: float,
    base_offset: float,
    corner_offset: float,
    scale: float,
    common_offset: bool,
    snap: Callable[[Vector], Vector] | None,
):
    corner_positions, corner_owners = _find_corners(gems, max_gap, gap, merge_distance)
    corners_of_gem: list[list[int]] = [[] for _ in gems]

    for corner, owners in enumerate(corner_owners):
        for i in owners:
            corners_of_gem[i].append(corner)

    verts: list[Vector] = []
    faces: list[tuple[int, ...]] = []
    gem_indices: list[int] = []
    is_base: list[bool] = []
    shared: dict[tuple, int] = {}
    snapped: set[int] = set()

    cells = _build_cells(gems, corners_of_gem, corner_positions, corner_owners, max_gap, gap, merge_distance)
    squared_owners: dict[tuple, set[int]] = {}

    for i, cell in enumerate(cells):
        for key, _ in cell:
            if key[0] == "X":
                squared_owners.setdefault(key, set()).add(i)

    for i, gem in enumerate(gems):
        cell = cells[i]

        if len(cell) < 3:
            continue

        local: dict[tuple, int] = {}
        indices = []

        for key, position in cell:
            if common_offset and key[0] in {"C", "X"}:
                cache = shared
                normal = _mean_normal(gems, corner_owners[key[1]] if key[0] == "C" else squared_owners[key], gem)
            else:
                cache = local
                normal = gem.normal

            if key not in cache:
                cache[key] = len(verts)
                verts.append(position + normal * base_offset)

            indices.append(cache[key])

        if not common_offset and scale != 1.0:
            center = sum((verts[v] for v in indices), Vector()) / len(indices)

            for v in indices:
                verts[v] = center + (verts[v] - center) * scale

        if snap is not None:
            for v in indices:
                if v not in snapped:
                    verts[v] = snap(verts[v])
                    snapped.add(v)

        _add_pyramid(verts, faces, gem_indices, is_base, i, gem, indices, corner_offset)

    return verts, faces, gem_indices, is_base


def _find_corners(
    gems: list[gem_neighbors.GemInfo],
    max_gap: float,
    gap: float,
    merge_distance: float,
) -> tuple[list[Vector], list[set[int]]]:
    connections = gem_neighbors.find_connections(gems, max_gap)
    neighbors = gem_neighbors.neighbor_map(connections)
    index_of = {id(gem): i for i, gem in enumerate(gems)}
    positions: list[Vector] = []
    owners: list[set[int]] = []

    for connection in connections:
        result = gem_neighbors.connection_points(connection, neighbors, gap)

        if result is None:
            continue

        for point in result[1]:
            positions.append(point.position)
            owners.append({index_of[id(connection.first)], index_of[id(connection.second)]})

    return _merge_points(positions, owners, merge_distance)


def _build_cells(
    gems: list[gem_neighbors.GemInfo],
    corners_of_gem: list[list[int]],
    corner_positions: list[Vector],
    corner_owners: list[set[int]],
    max_gap: float,
    gap: float,
    merge_distance: float,
) -> list[_Cell]:
    axes = [_axes(gem) for gem in gems]
    cells = [_gem_cell(gem, axes[i], corners_of_gem[i], corner_positions, max_gap, gap) for i, gem in enumerate(gems)]
    cells = _align_open_sides(gems, axes, cells, corner_owners, merge_distance)

    return [
        _drop_collinear(_square_corners(gem, _close_open_sides(gem, i, cells[i], axes[i], merge_distance), axes[i]))
        for i, gem in enumerate(gems)
    ]


def _gem_cell(
    gem: gem_neighbors.GemInfo,
    axes: tuple[Vector, Vector],
    corners: list[int],
    corner_positions: list[Vector],
    max_gap: float,
    gap: float,
) -> _Cell:
    cell = [(("C", corner), corner_positions[corner]) for corner in corners]

    if not cell:
        cell = _local_corners(gem, axes, max_gap, gap)

    return _sorted_cell(gem, axes, cell)


def _sorted_cell(
    gem: gem_neighbors.GemInfo,
    axes: tuple[Vector, Vector],
    cell: _Cell,
) -> _Cell:
    return sorted(cell, key=lambda item: _angle(gem, axes, item[1]))


def _gaps(angles: list[float]) -> Iterator[tuple[int, float, float]]:
    count = len(angles)

    for i, start in enumerate(angles):
        end = angles[(i + 1) % count] + (tau if i == count - 1 else 0.0)
        yield i, start, end - start


def _mirrored_points(
    gem: gem_neighbors.GemInfo,
    cell: _Cell,
    tolerance: float,
) -> _Cell:
    mirrored = []

    for key, position in cell:
        point = gem.location * 2.0 - position

        if not any((point - other).length <= tolerance for _, other in cell):
            mirrored.append((key, point))

    return mirrored


def _align_open_sides(
    gems: list[gem_neighbors.GemInfo],
    axes: list[tuple[Vector, Vector]],
    cells: list[_Cell],
    corner_owners: list[set[int]],
    tolerance: float,
) -> list[_Cell]:
    proposals: dict[tuple, list[Vector]] = {}
    bounding: list[set[tuple]] = []

    for gem, gem_axes, cell in zip(gems, axes, cells):
        angles = [_angle(gem, gem_axes, position) for _, position in cell]
        keys = set()

        for i, start, span in _gaps(angles):
            if span <= _OPEN_SIDE_ANGLE:
                continue

            first, second = cell[i], cell[(i + 1) % len(cell)]
            keys.update((first[0], second[0]))

            if span >= pi:
                continue

            candidates = [
                position
                for _, position in _mirrored_points(gem, cell, tolerance)
                if (_angle(gem, gem_axes, position) - start) % tau < span
            ]

            if not candidates:
                continue

            middle = start + span * 0.5
            direction = gem_axes[0] * cos(middle) + gem_axes[1] * sin(middle)
            depth = max((position - gem.location).dot(direction) for position in candidates)

            for key, position in (first, second):
                shift = depth - (position - gem.location).dot(direction)

                if key[0] == "C" and shift > _EPS:
                    proposals.setdefault(key, []).append(position + direction * shift)

        bounding.append(keys)

    moves = {
        key: sum(positions, Vector()) / len(positions)
        for key, positions in proposals.items()
        if all(key in bounding[i] for i in corner_owners[key[1]])
    }

    return [
        _sorted_cell(gem, gem_axes, [(key, moves.get(key, position)) for key, position in cell])
        for gem, gem_axes, cell in zip(gems, axes, cells)
    ]


def _close_open_sides(
    gem: gem_neighbors.GemInfo,
    index: int,
    cell: _Cell,
    axes: tuple[Vector, Vector],
    tolerance: float,
) -> _Cell:
    angles = [_angle(gem, axes, position) for _, position in cell]
    added = [
        (("M", index, key), position)
        for key, position in _mirrored_points(gem, cell, tolerance)
        if _in_open_side(angles, _angle(gem, axes, position))
    ]

    return _sorted_cell(gem, axes, cell + added)


def _in_open_side(angles: list[float], angle: float) -> bool:
    for _, start, span in _gaps(angles):
        if (angle - start) % tau < span:
            return span > _OPEN_SIDE_ANGLE

    return False


def _drop_collinear(cell: _Cell) -> _Cell:
    cell = list(cell)
    i = 0

    while i < len(cell) and len(cell) > 3:
        key, position = cell[i]
        before, after = cell[i - 1][1], cell[(i + 1) % len(cell)][1]
        line = after - before

        if (
            key[0] == "M"
            and line.length > _EPS
            and (position - before).cross(line).length / line.length < _COLLINEAR_DISTANCE
        ):
            del cell[i]
        else:
            i += 1

    return cell


def _square_corners(
    gem: gem_neighbors.GemInfo,
    cell: _Cell,
    axes: tuple[Vector, Vector],
) -> _Cell:
    count = len(cell)

    if count < 4:
        return cell

    added = []

    for i in range(count):
        z, a, b, c = (cell[(i + n) % count][1] for n in (-1, 0, 1, 2))
        before = a - z
        edge = b - a
        after = c - b

        if min(before.length, edge.length, after.length) <= _EPS:
            continue

        if edge.length >= _CHAMFER_RATIO * min(before.length, after.length):
            continue

        d_before = before.normalized()
        d_edge = edge.normalized()
        d_after = after.normalized()
        turn_a = atan2(d_before.cross(d_edge).dot(gem.normal), d_before.dot(d_edge))
        turn_b = atan2(d_edge.cross(d_after).dot(gem.normal), d_edge.dot(d_after))

        if turn_a <= 0.0 or turn_b <= 0.0 or turn_a + turn_b > _CHAMFER_MAX_TURN:
            continue

        denominator = d_before.cross(d_after).dot(gem.normal)

        if abs(denominator) <= _EPS:
            continue

        distance = edge.cross(d_after).dot(gem.normal) / denominator

        if distance <= 0.0:
            continue

        point = a + d_before * distance
        added.append((("X", tuple(round(value, 3) for value in point)), point))

    return _sorted_cell(gem, axes, cell + added)


def _add_pyramid(
    verts: list[Vector],
    faces: list[tuple[int, ...]],
    gem_indices: list[int],
    is_base: list[bool],
    gem_index: int,
    gem: gem_neighbors.GemInfo,
    indices: list[int],
    tip_offset: float,
) -> None:
    center = sum((verts[v] for v in indices), Vector()) / len(indices)

    normal = Vector()
    for a, b in zip(indices, indices[1:] + indices[:1]):
        normal += (verts[a] - center).cross(verts[b] - center)

    if normal.length_squared <= _EPS * _EPS:
        return

    if normal.dot(gem.normal) < 0.0:
        indices.reverse()
        normal.negate()

    normal.normalize()
    tip = gem.location + gem.normal * tip_offset
    height = (tip - center).dot(normal)

    if abs(height) <= _EPS:
        faces.append(tuple(indices))
        gem_indices.append(gem_index)
        is_base.append(True)
        return

    tip_index = len(verts)
    verts.append(tip)

    for a, b in zip(indices, indices[1:] + indices[:1]):
        faces.append((a, b, tip_index) if height > 0.0 else (b, a, tip_index))
        gem_indices.append(gem_index)
        is_base.append(False)

    faces.append(tuple(reversed(indices)) if height > 0.0 else tuple(indices))
    gem_indices.append(gem_index)
    is_base.append(True)


def _merge_points(
    positions: list[Vector],
    owners: list[set[int]],
    merge_distance: float,
) -> tuple[list[Vector], list[set[int]]]:
    count = len(positions)
    parent = list(range(count))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    if merge_distance > 0.0 and count > 1:
        tree = kdtree.KDTree(count)

        for i, position in enumerate(positions):
            tree.insert(position, i)

        tree.balance()

        for i, position in enumerate(positions):
            for _, j, distance in tree.find_range(position, merge_distance):
                if j > i and distance < merge_distance:
                    parent[find(j)] = find(i)

    groups: dict[int, list[int]] = {}

    for i in range(count):
        groups.setdefault(find(i), []).append(i)

    merged_positions = []
    merged_owners = []

    for members in groups.values():
        merged_positions.append(sum((positions[i] for i in members), Vector()) / len(members))
        merged_owners.append(set().union(*(owners[i] for i in members)))

    return merged_positions, merged_owners


def _axes(gem: gem_neighbors.GemInfo) -> tuple[Vector, Vector]:
    rotation = gem.matrix.to_3x3()
    return rotation @ Vector((1.0, 0.0, 0.0)), rotation @ Vector((0.0, 1.0, 0.0))


def _angle(gem: gem_neighbors.GemInfo, axes: tuple[Vector, Vector], position: Vector) -> float:
    direction = position - gem.location
    return atan2(direction.dot(axes[1]), direction.dot(axes[0])) % tau


def _local_corners(
    gem: gem_neighbors.GemInfo,
    axes: tuple[Vector, Vector],
    max_gap: float,
    gap: float,
) -> _Cell:
    half_length = gem.radius + max_gap * 0.5
    half_width = gem.radius * gap
    corners = []

    for n, (sign_x, sign_y) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
        corners.append(
            (
                ("L", n),
                gem.location + axes[0] * (sign_x * half_length) + axes[1] * (sign_y * half_width),
            )
        )

    return corners


def _mean_normal(
    gems: list[gem_neighbors.GemInfo],
    owner_indices: set[int],
    fallback: gem_neighbors.GemInfo,
) -> Vector:
    normal = sum((gems[i].normal for i in owner_indices), Vector())

    return normal.normalized() if normal.length_squared > _EPS * _EPS else fallback.normal


def _snap_targets(coll: Collection | None, generator: Object) -> list[Object]:
    if coll is None:
        return []

    targets = [ob for ob in coll.all_objects if ob.type == "MESH" and "gem" not in ob and ob is not generator]
    targets.sort(key=lambda ob: ob.name)

    return targets


def _snap_func(targets: list[Object], snap_offset: float, depsgraph: Depsgraph) -> Callable[[Vector], Vector] | None:
    if not targets:
        return None

    surfaces = []

    for target in targets:
        target_eval = target.evaluated_get(depsgraph)
        matrix = target_eval.matrix_world.copy()
        matrix_inv = matrix.inverted_safe()
        tree = BVHTree.FromObject(target_eval, depsgraph)
        surfaces.append((tree, matrix, matrix_inv, matrix_inv.to_3x3().transposed()))

    def snap(position: Vector) -> Vector:
        nearest = None
        nearest_distance = 0.0

        for tree, matrix, matrix_inv, normal_matrix in surfaces:
            location, normal, _, _ = tree.find_nearest(matrix_inv @ position)

            if location is None:
                continue

            location = matrix @ location
            distance = (location - position).length_squared

            if nearest is None or distance < nearest_distance:
                nearest = location + (normal_matrix @ normal).normalized() * snap_offset
                nearest_distance = distance

        return position if nearest is None else nearest

    return snap


def _modifier_values(ob: Object) -> dict:
    source_coll = generator_mesh.source_collection(ob, PROP_SOURCE_COLLECTION)
    values = _default_modifier_values()
    generator_mesh.apply_modifier_socket_values(
        values,
        generator_mesh.modifier(ob, openwork_nodes),
        openwork_nodes,
    )
    values["source_coll"] = source_coll
    return values


def _default_modifier_values() -> dict:
    return openwork_nodes.settings_to_values(_OpenworkSettings()) | {"Snap Collection": None}


def _signature(
    generator: Object,
    gems: list[tuple[str, Matrix, tuple[float, float]]],
    modifier_values: dict,
    targets: list[Object],
    depsgraph: Depsgraph,
) -> str:
    parts = generator_mesh.signature_parts(generator, modifier_values, PROP_SOURCE_COLLECTION)

    for name, matrix, dimensions in gems:
        matrix_values = tuple(round(value, 6) for row in matrix for value in row)
        dim_values = tuple(round(value, 6) for value in dimensions)
        parts.append(f"{name}:{matrix_values}:{dim_values}")

    parts.extend(_target_signature(target, depsgraph) for target in targets)

    return "|".join(parts)


def _target_signature(target: Object, depsgraph: Depsgraph) -> str:
    target_eval = target.evaluated_get(depsgraph)
    me = target_eval.to_mesh()
    coords = array("f", bytes(12 * len(me.vertices)))
    me.vertices.foreach_get("co", coords)
    target_eval.to_mesh_clear()

    matrix_values = tuple(round(value, 6) for row in target_eval.matrix_world for value in row)
    digest = hashlib.md5(coords.tobytes()).hexdigest()

    return f"{target.name}:{matrix_values}:{digest}"
