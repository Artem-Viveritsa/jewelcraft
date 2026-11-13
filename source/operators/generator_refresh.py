# SPDX-License-Identifier: GPL-3.0-or-later


from bpy.types import Operator


class OBJECT_OT_generator_refresh(Operator):
    bl_label = "Refresh"
    bl_description = "Update the generated geometry"
    bl_idname = "object.jewelcraft_generator_refresh"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob is not None and _generator_module(ob) is not None

    def execute(self, context):
        try:
            _generator_module(context.object).update_object(context.object, force=True)
        except ValueError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}

        return {"FINISHED"}


def _generator_module(ob):
    from .add_channels_generator import channels_mesh
    from .add_cutters_generator import cutters_mesh
    from .add_openwork_generator import openwork_mesh

    for module in (cutters_mesh, channels_mesh, openwork_mesh):
        if module.PROP_SOURCE_COLLECTION in ob:
            return module

    return None
