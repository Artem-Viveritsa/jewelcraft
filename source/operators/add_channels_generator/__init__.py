# SPDX-License-Identifier: GPL-3.0-or-later


from bpy.props import StringProperty
from bpy.types import Operator, Panel

from .. import generator_ui


class OBJECT_OT_channels_generator_add(Operator):
    bl_label = "Channels Generator"
    bl_description = "Create Geometry Nodes channels between nearby gems in a collection"
    bl_idname = "object.jewelcraft_channels_generator_add"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    source_collection_name: StringProperty(
        name="Gem Collection",
        description="Collection containing gem objects",
    )

    def draw(self, context):
        generator_ui.draw_source_collection_search(self.layout, self)

    def execute(self, context):
        from . import channels_mesh

        return generator_ui.execute_add_operator(
            self,
            context,
            channels_mesh.create_object,
            purge_stale_handlers,
            "Created channels generator",
        )

    def invoke(self, context, event):
        return generator_ui.invoke_add_operator(self, context, purge_stale_handlers)


class OBJECT_PT_channels_generator_modifier(Panel):
    bl_label = "Channels Generator"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "modifier"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob is not None and _channels_modifier(ob) is not None

    def draw(self, context):
        md = _channels_modifier(context.object)
        from . import channels_nodes

        identifiers = generator_ui.socket_identifiers(md, channels_nodes)

        layout = self.layout
        generator_ui.setup_property_layout(layout)

        from . import channels_mesh

        generator_ui.draw_collection(layout, context.object, channels_mesh.PROP_SOURCE_COLLECTION)
        layout.separator()
        generator_ui.draw_socket(layout, md, identifiers, "Radius Scale")
        generator_ui.draw_socket(layout, md, identifiers, "Max Gap")
        generator_ui.draw_socket(layout, md, identifiers, "Offset Ratio")
        layout.separator()
        generator_ui.draw_socket(layout, md, identifiers, "Curve Resolution")


def _channels_modifier(ob):
    from . import channels_nodes

    return generator_ui.modifier(ob, channels_nodes)


def purge_stale_handlers() -> None:
    generator_ui.purge_stale_handlers("channels_auto_update", ".add_channels_generator.channels_mesh")
