# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Artem Viveritsa
# SPDX-FileContributor: Modified by Mikhail Rachinskiy

from itertools import combinations
from typing import NamedTuple

from mathutils import Matrix, Vector

from . import asset


_EPS = 1e-6
_MAX_CONNECTIONS = 2048
_CHAIN_MAX_CONNECTIONS = 2
_CHAIN_CURVATURE_SHIFT_FACTOR = 0.25
_CHAIN_CURVATURE_SIZE_FACTOR = 0.25


class GemInfo(NamedTuple):
    location: Vector
    radius: float
    matrix: Matrix
    normal: Vector


class ConnectionInfo(NamedTuple):
    first: GemInfo
    second: GemInfo
    first_point: Vector
    second_point: Vector


class ConnectionPoint(NamedTuple):
    position: Vector
    size_factor: float


def to_gem_info(ob) -> GemInfo:
    return matrix_to_gem_info(ob.matrix_world, ob.dimensions.xy)


def matrix_to_gem_info(matrix_world: Matrix, dimensions_xy) -> GemInfo:
    loc, rot, _ = matrix_world.decompose()
    mat = Matrix.LocRotScale(loc, rot, (1.0, 1.0, 1.0))
    nor = matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))

    if nor.length_squared <= _EPS:
        nor = Vector((0.0, 0.0, 1.0))
    else:
        nor.normalize()

    rad = max(dimensions_xy) / 2.0

    loc.freeze()
    mat.freeze()
    nor.freeze()

    return GemInfo(loc, rad, mat, nor)


def find_connections(gems: list[GemInfo], max_gap: float) -> list[ConnectionInfo]:
    connections = []
    app = connections.append

    for first, second in combinations(gems, 2):
        dist_locs = (first.location - second.location).length
        first_point, second_point = asset.nearest_coords(first.radius, second.radius, first.matrix, second.matrix)
        gap = asset.calc_gap(first_point, second_point, first.location, dist_locs, first.radius)

        if gap <= max_gap:
            app(ConnectionInfo(first, second, first_point, second_point))
            if len(connections) > _MAX_CONNECTIONS:
                raise ValueError("Too many gem connections found. Reduce Max Gap or selection size")

    return connections


def neighbor_map(connections: list[ConnectionInfo]) -> dict[GemInfo, list[GemInfo]]:
    neighbors = {}

    for connection in connections:
        neighbors.setdefault(connection.first, []).append(connection.second)
        neighbors.setdefault(connection.second, []).append(connection.first)

    return neighbors


def connection_points(
    connection: ConnectionInfo,
    neighbors: dict[GemInfo, list[GemInfo]],
    gap: float,
) -> tuple[Vector, tuple[ConnectionPoint, ConnectionPoint]] | None:
    axis = connection.second_point - connection.first_point
    if axis.length_squared <= _EPS:
        axis = connection.second.location - connection.first.location
        if axis.length_squared <= _EPS:
            return None

    axis.normalize()

    normal = connection.first.normal + connection.second.normal
    if normal.length_squared <= _EPS:
        normal = connection.first.normal.copy()
        if normal.length_squared <= _EPS:
            normal = Vector((0.0, 0.0, 1.0))
    normal.normalize()

    perpendicular = axis.cross(normal)
    if perpendicular.length_squared <= _EPS:
        perpendicular = normal.cross(Vector((1.0, 0.0, 0.0)))
        if perpendicular.length_squared <= _EPS:
            perpendicular = normal.cross(Vector((0.0, 1.0, 0.0)))
            if perpendicular.length_squared <= _EPS:
                return None
    perpendicular.normalize()

    midpoint = connection.first_point.lerp(connection.second_point, 0.5)
    avg_diameter = connection.first.radius + connection.second.radius
    if avg_diameter <= _EPS:
        return None

    half_width = avg_diameter * gap * 0.5
    curvature_ratio = _chain_curvature_ratio(connection, neighbors, perpendicular, avg_diameter)
    outward_sign = -1.0 if curvature_ratio > 0.0 else 1.0
    shift_magnitude = abs(curvature_ratio) * _CHAIN_CURVATURE_SHIFT_FACTOR * half_width
    size_delta = abs(curvature_ratio) * _CHAIN_CURVATURE_SIZE_FACTOR
    points = []

    for spread_direction in (-1.0, 1.0):
        position = midpoint + (perpendicular * (half_width * spread_direction))
        size_factor = 1.0

        if curvature_ratio:
            position += perpendicular * (outward_sign * shift_magnitude)
            is_inner = (spread_direction * curvature_ratio) > 0.0
            size_factor = 1.0 - size_delta if is_inner else 1.0 + size_delta

        points.append(ConnectionPoint(position, size_factor))

    return normal, (points[0], points[1])


def _chain_curvature_ratio(
    connection: ConnectionInfo, neighbors: dict[GemInfo, list[GemInfo]], width_direction: Vector, avg_diameter: float
) -> float:
    first_neighbors = neighbors.get(connection.first, ())
    second_neighbors = neighbors.get(connection.second, ())

    if len(first_neighbors) > _CHAIN_MAX_CONNECTIONS or len(second_neighbors) > _CHAIN_MAX_CONNECTIONS:
        return 0.0

    extra_locations = []

    prev_neighbors = [info for info in first_neighbors if info is not connection.second]
    next_neighbors = [info for info in second_neighbors if info is not connection.first]

    if len(prev_neighbors) == 1:
        extra_locations.append(prev_neighbors[0].location)
    if len(next_neighbors) == 1:
        extra_locations.append(next_neighbors[0].location)

    if not extra_locations:
        return 0.0

    neighbors_center = Vector()
    for location in extra_locations:
        neighbors_center += location
    neighbors_center /= len(extra_locations)

    chord_midpoint = (connection.first.location + connection.second.location) * 0.5
    ratio = (neighbors_center - chord_midpoint).dot(width_direction) / avg_diameter

    return max(-1.0, min(ratio, 1.0))
