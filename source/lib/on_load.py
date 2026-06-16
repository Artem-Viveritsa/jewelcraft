# SPDX-FileCopyrightText: 2015-2026 Mikhail Rachinskiy
# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
from bpy.app.handlers import persistent

from .. import var


_is_executed = False


def handler_add():
    bpy.app.handlers.load_post.append(_execute)
    bpy.app.timers.register(_timer)  # Execute once after registration


def handler_del():
    bpy.app.handlers.load_post.remove(_execute)


def _timer():
    global _is_executed

    if _is_executed:
        return

    _execute(None)


@persistent
def _execute(dummy):
    global _is_executed

    _is_executed = True

    _scene_props_versioning()
    var.config_naming_versioning()

    scene_props = bpy.context.scene.jewelcraft
    scene_props.measurements.deserialize(is_on_load=True)
    _scene_materials_deserialize()
    _generator_handlers_add()

    wm_props = bpy.context.window_manager.jewelcraft
    wm_props.gem_colors.deserialize()
    wm_props.gem_map_palette.deserialize()
    wm_props.asset_libs.deserialize()


def _scene_materials_deserialize():
    materials = bpy.context.scene.jewelcraft.weighting_materials

    if materials.coll:
        return

    prefs = bpy.context.preferences.addons[var.ADDON_ID].preferences

    try:
        materials.deserialize(prefs.weighting_default_list)
    except FileNotFoundError:
        prefs.property_unset("weighting_default_list")
        bpy.context.preferences.is_dirty = True
        materials.deserialize(prefs.weighting_default_list)


def _generator_handlers_add():
    from ..operators.add_channels_generator import channels_mesh
    from ..operators.add_cutters_generator import cutters_mesh

    scene = bpy.context.scene

    if any(cutters_mesh.PROP_SOURCE_COLLECTION in ob for ob in scene.objects):
        cutters_mesh.handler_add()

    if any(channels_mesh.PROP_SOURCE_COLLECTION in ob for ob in scene.objects):
        channels_mesh.handler_add()


def _scene_props_versioning():
    if bpy.app.version < (5, 0, 0):
        return
    if bpy.context.scene.get("jewelcraft"):
        del bpy.context.scene["jewelcraft"]
