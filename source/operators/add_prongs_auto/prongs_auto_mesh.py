# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Artem Viveritsa
# SPDX-FileContributor: Modified by Mikhail Rachinskiy

from statistics import median
from typing import NamedTuple

import bl_math
from mathutils import Matrix, Vector

from ...lib import gem_neighbors, unit


_EPS = 1e-6
_MAX_PRONGS = 4096


class ProngInfo(NamedTuple):
    position: Vector
    normal: Vector
    size: float
    height: float
    matrix: Matrix


def create_prongs_auto(
    gems,
    size_ratio: float,
    height_ratio: float,
    gap: float,
    uniformity: float,
    max_gap: float,
    merge_distance: float,
    size_step: float,
) -> list[ProngInfo]:
    gem_infos = [gem_neighbors.to_gem_info(ob) for ob in gems]
    connections = gem_neighbors.find_connections(gem_infos, max_gap)

    if not connections:
        return []

    prong_infos = _create_prong_infos(connections, size_ratio, height_ratio, gap, size_step)

    if merge_distance and len(prong_infos) > 1:
        prong_infos = _merge_nearby_prongs(prong_infos, merge_distance, size_step)

    if uniformity and len(prong_infos) > 1:
        prong_infos = _apply_uniformity(prong_infos, uniformity, size_step)

    if len(prong_infos) > _MAX_PRONGS:
        raise ValueError("Too many prongs generated. Reduce Max Gap or selection size")

    return prong_infos


def _create_prong_infos(
    connections: list[gem_neighbors.ConnectionInfo],
    size_ratio: float,
    height_ratio: float,
    gap: float,
    size_step: float,
) -> list[ProngInfo]:

    Scale = unit.Scale()
    prong_infos = []
    app = prong_infos.append
    neighbors = gem_neighbors.neighbor_map(connections)

    for connection in connections:
        result = gem_neighbors.connection_points(connection, neighbors, gap)
        if result is None:
            continue

        normal, points = result
        avg_diameter = connection.first.radius + connection.second.radius
        size = avg_diameter * size_ratio
        height = avg_diameter * height_ratio
        if size <= _EPS or height <= _EPS:
            continue

        rotation = normal.to_track_quat("Z", "Y").to_matrix().to_4x4()

        for point in points:
            prong_size = _round_size(Scale, size * point.size_factor, size_step)
            matrix = Matrix.Translation(point.position) @ rotation
            app(ProngInfo(point.position.copy(), normal.copy(), prong_size, height, matrix))

    return prong_infos


def _merge_nearby_prongs(prongs: list[ProngInfo], merge_distance: float, size_step: float) -> list[ProngInfo]:
    unit_scale = unit.Scale()
    parent = list(range(len(prongs)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(first: int, second: int) -> None:
        root_first = find(first)
        root_second = find(second)
        if root_first != root_second:
            parent[root_second] = root_first

    for i, base in enumerate(prongs):
        for j in range(i + 1, len(prongs)):
            if (base.position - prongs[j].position).length < merge_distance:
                union(i, j)

    groups = {}

    for index in range(len(prongs)):
        root = find(index)
        groups.setdefault(root, []).append(prongs[index])

    merged = []
    app = merged.append

    for group in groups.values():
        if len(group) == 1:
            app(group[0])
            continue

        position = Vector()
        normal = Vector()

        size = 0.0
        height = 0.0

        for info in group:
            position += info.position
            normal += info.normal
            size += info.size
            height += info.height

        count = len(group)
        position /= count
        size /= count
        height /= count
        size = _round_size(unit_scale, size, size_step)

        if normal.length_squared <= _EPS:
            normal = group[0].normal.copy()
        else:
            normal.normalize()

        matrix = Matrix.Translation(position) @ normal.to_track_quat("Z", "Y").to_matrix().to_4x4()
        app(ProngInfo(position, normal, size, height, matrix))

    return merged


def _round_size(Scale: unit.Scale, size: float, size_step: float) -> float:
    if size <= _EPS:
        size_mm = size_step
    else:
        size_mm = Scale.from_scene(size)
        size_mm = round(size_mm / size_step) * size_step
        size_mm = max(size_mm, size_step)

    return Scale.to_scene(size_mm)


def _apply_uniformity(prongs: list[ProngInfo], uniformity: float, size_step: float) -> list[ProngInfo]:
    unit_scale = unit.Scale()
    median_size = median(info.size for info in prongs)
    median_height = median(info.height for info in prongs)
    normalized = []
    app = normalized.append

    for info in prongs:
        size = bl_math.lerp(info.size, median_size, uniformity)
        height = bl_math.lerp(info.height, median_height, uniformity)
        size = _round_size(unit_scale, size, size_step)
        height = max(height, _EPS)
        app(ProngInfo(info.position, info.normal, size, height, info.matrix.copy()))

    return normalized
