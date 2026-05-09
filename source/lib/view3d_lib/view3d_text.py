# SPDX-FileCopyrightText: 2015-2025 Mikhail Rachinskiy
# SPDX-License-Identifier: GPL-3.0-or-later

from collections.abc import Iterator
from typing import NamedTuple

import blf
import bpy

from .. import colorlib

_TYPE_BOOL = 1
_TYPE_INT = 2
_TYPE_PROC = 3
_TYPE_ENUM = 4
_TYPE_HOTKEY = 5
_FONT_SIZE = 22


class _Prop(NamedTuple):
    type: int
    name: str
    key: str
    attr: str
    items: tuple[str]


class Layout:
    __slots__ = "children", "enabled_by", "col_max"
    children: "list[Layout | _Prop]"
    enabled_by: str
    col_max: list[str]

    def __init__(self) -> None:
        self.children = []
        self.enabled_by = ""
        self.col_max = ["", ""]

    def get_col_max(self) -> list[int]:
        for child in self.children:
            if child.__class__ is Layout:
                self.col_max[0] = max(self.col_max[0], child.col_max[0], key=len)
                self.col_max[1] = max(self.col_max[1], child.col_max[1], key=len)

        return self.col_max

    def layout(self) -> "Layout":
        lay = Layout()
        self.children.append(lay)
        return lay

    def _prop(self, type: int, name: str, key: str, attr: str, items: tuple[str] = None) -> None:
        self.children.append(_Prop(type, name, key, attr, items))
        self.col_max[0] = max(self.col_max[0], name, key=len)
        self.col_max[1] = max(self.col_max[1], key, key=len)

    def separator(self) -> None:
        self.children.append(_Prop(None, None, None, None, None))

    def bool(self, name: str, key: str, attr: str) -> None:
        self._prop(_TYPE_BOOL, name, key, attr)

    def int(self, name: str, key: str, attr: str) -> None:
        self._prop(_TYPE_INT, name, key, attr)

    def proc(self, name: str, key: str, attr: str) -> None:
        self._prop(_TYPE_PROC, name, key, attr)

    def enum(self, name: str, key: str, attr: str, items: tuple[str]) -> None:
        self._prop(_TYPE_ENUM, name, key, attr, items)

    def hotkey(self, name: str, key: str) -> None:
        self._prop(_TYPE_HOTKEY, name, key, "", None)


def _draw_text(
    fontid: int,
    text: str,
    x: int,
    y: int,
    color: tuple[float, float, float, float],
    shadow_color: tuple[float, float, float, float],
    outline: int = 1,
) -> None:
    for offset_x, offset_y in (
        (-outline, -outline),
        (-outline, 0),
        (-outline, outline),
        (0, -outline),
        (0, outline),
        (outline, -outline),
        (outline, 0),
        (outline, outline),
    ):
        blf.position(fontid, x + offset_x, y + offset_y, 0.0)
        blf.color(fontid, *shadow_color)
        blf.draw(fontid, text)

    blf.position(fontid, x, y, 0.0)
    blf.color(fontid, *color)
    blf.draw(fontid, text)


def _get_background_color() -> tuple[float, float, float]:
    shading = bpy.context.space_data.shading

    if shading.background_type == "WORLD":
        world = bpy.context.scene.world
        if world is not None:
            return tuple(world.color)

    elif shading.background_type == "VIEWPORT":
        return tuple(shading.background_color)

    gradients = bpy.context.preferences.themes[0].view_3d.space.gradients

    if gradients.background_type == "RADIAL":
        return tuple(gradients.gradient)

    return tuple(gradients.high_gradient)


def _get_text_colors() -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
    color = list(bpy.context.preferences.themes[0].view_3d.space.text_hi)
    bg_color = _get_background_color()

    if sum((text_channel - bg_channel) ** 2 for text_channel, bg_channel in zip(color, bg_color, strict=True)) ** 0.5 < 0.5:
        factor = 0.33 if colorlib.luma(color) > 0.5 else 3.0
        color = [min(max(channel * factor, 0.0), 1.0) for channel in color]

    shadow_value = 0.0 if colorlib.luma(color) > 0.4 else 1.0
    return (*color, 1.0), (shadow_value, shadow_value, shadow_value, 0.8)


def _dim_shadow(shadow_color: tuple[float, float, float, float], factor: float = 0.25) -> tuple[float, float, float, float]:
    return (*shadow_color[:3], shadow_color[3] * factor)


def _get_font_scale(prefs: bpy.types.Preferences) -> float:
    # VER
    if bpy.app.version >= (4, 3, 0):
        font_size = prefs.ui_styles[0].widget.points
    else:
        font_size = prefs.ui_styles[0].widget_label.points

    return font_size * prefs.view.ui_scale / 11  # 11 is the default font size


def _get_lineheight(prefs: bpy.types.Preferences, fontid: int = 1) -> int:
    fontscale = _get_font_scale(prefs)
    fontsize = round(fontscale * _FONT_SIZE)

    blf.size(fontid, fontsize)

    _, h_font = blf.dimensions(fontid, "M")
    return round(h_font * 1.8)


def get_xy() -> tuple[int, int]:
    overlay = bpy.context.space_data.overlay
    prefs = bpy.context.preferences
    view = prefs.view
    ui_scale = prefs.view.ui_scale
    fontscale = _get_font_scale(prefs)

    x = round(20 * ui_scale)
    y = round(10 * ui_scale)

    for region in bpy.context.area.regions:
        if region.type in {"HEADER", "TOOL_HEADER"}:
            y += region.height
        elif region.type == "TOOLS":
            x += region.width

    _y = 0

    if overlay.show_text and (view.show_view_name or view.show_object_info):
        _y += 60
    if overlay.show_stats:
        _y += 140

    y += round(_y * fontscale)
    y += _get_lineheight(prefs) * 2
    y = bpy.context.region.height - y

    return x, y


def _get_props(layout: Layout, data) -> Iterator[_Prop]:
    for child in layout.children:
        if child.__class__ is _Prop:
            yield child
            continue

        if child.enabled_by and not getattr(data, child.enabled_by):
            continue

        yield from _get_props(child, data)


def draw_options(data, layout: Layout, x: int, y: int) -> None:
    prefs = bpy.context.preferences

    color_text, color_shadow = _get_text_colors()
    color_shadow_soft = _dim_shadow(color_shadow, 0)
    color_grey = color_text
    color_green = (0.2, 1.0, 0.4, 1.0)
    color_red = (1.0, 0.3, 0.3, 1.0)
    color_yellow = (0.9, 0.9, 0.0, 1.0)
    color_blue = (0.3, 0.5, 1.0, 1.0)

    fontid = 1
    fontscale = _get_font_scale(prefs)
    fontsize = round(fontscale * _FONT_SIZE)

    blf.size(fontid, fontsize)

    col_max = layout.get_col_max()
    w_col1, _ = blf.dimensions(fontid, col_max[0])
    w_col2, _ = blf.dimensions(fontid, col_max[1])
    lineheight = _get_lineheight(prefs, fontid)
    outline = max(1, round(fontscale))

    for prop in _get_props(layout, data):
        y -= lineheight
        _x = x

        if prop.type is None:
            continue

        _draw_text(fontid, prop.name, x, y, color_text, color_shadow, outline)

        if prop.key:
            _x += w_col1 + 20
            _draw_text(fontid, prop.key, _x, y, color_grey, color_shadow, outline)

        if prop.type is _TYPE_BOOL:
            _x += w_col2 + 10
            _draw_text(fontid, ":", _x, y, color_text, color_shadow, outline)

            _x += 20
            if getattr(data, prop.attr):
                _draw_text(fontid, "ON", _x, y, color_green, color_shadow_soft, outline)
            else:
                _draw_text(fontid, "OFF", _x, y, color_red, color_shadow_soft, outline)

        elif prop.type is _TYPE_INT:
            _x += w_col2 + 10
            _draw_text(fontid, ":", _x, y, color_text, color_shadow, outline)

            _x += 20
            _draw_text(fontid, str(round(getattr(data, prop.attr), 3)), _x, y, color_blue, color_shadow_soft, outline)

        elif prop.type is _TYPE_ENUM:
            _x += w_col2 + 10
            _draw_text(fontid, ":", _x, y, color_text, color_shadow, outline)

            _x += 20
            _draw_text(fontid, prop.items[getattr(data, prop.attr)], _x, y, color_text, color_shadow, outline)

        elif prop.type is _TYPE_PROC:
            if getattr(data, prop.attr):
                _x += w_col2 + 10
                _draw_text(fontid, ":", _x, y, color_text, color_shadow, outline)

                _x += 20
                _draw_text(fontid, "PROCESSING...", _x, y, color_yellow, color_shadow_soft, outline)
