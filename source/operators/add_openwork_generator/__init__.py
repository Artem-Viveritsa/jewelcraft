# SPDX-License-Identifier: GPL-3.0-or-later


from bpy.props import StringProperty
from bpy.types import Operator, Panel

from .. import generator_ui


class OBJECT_OT_openwork_generator_add(Operator):
    bl_label = "Openwork Generator"
    bl_description = (
        "Create auto-updating openwork pyramids around gems in a collection: "
        "the base is a polygon through the prong positions around a gem, the tip is at the gem center"
    )
    bl_idname = "object.jewelcraft_openwork_generator_add"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    source_collection_name: StringProperty(
        name="Gem Collection",
        description="Collection containing gem objects",
    )

    def draw(self, context):
        generator_ui.draw_source_collection_search(self.layout, self)

    def execute(self, context):
        from . import openwork_mesh

        return generator_ui.execute_add_operator(
            self,
            context,
            openwork_mesh.create_object,
            purge_stale_handlers,
            "Created openwork generator",
        )

    def invoke(self, context, event):
        return generator_ui.invoke_add_operator(self, context, purge_stale_handlers)


class OBJECT_PT_openwork_generator_modifier(Panel):
    bl_label = "Openwork Generator"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "modifier"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob is not None and _openwork_modifier(ob) is not None

    def draw_header(self, context):
        from . import openwork_nodes

        generator_ui.draw_interactive_header(self.layout, _openwork_modifier(context.object), openwork_nodes)

    def draw(self, context):
        from . import openwork_nodes

        md = _openwork_modifier(context.object)
        identifiers = generator_ui.socket_identifiers(md, openwork_nodes)

        layout = self.layout
        generator_ui.setup_property_layout(layout)
        generator_ui.draw_refresh(layout, md, identifiers)

        from . import openwork_mesh

        generator_ui.draw_collection(
            layout,
            context.object,
            openwork_mesh.PROP_SOURCE_COLLECTION,
            description=openwork_nodes.DESCRIPTION_COLLECTION,
        )
        layout.separator()
        generator_ui.draw_socket(layout, md, identifiers, "Gap")
        generator_ui.draw_socket(layout, md, identifiers, "Max Gap")
        generator_ui.draw_socket(layout, md, identifiers, "Merge Distance")
        layout.separator()
        generator_ui.draw_socket(layout, md, identifiers, "Base Offset")
        generator_ui.draw_socket(layout, md, identifiers, "Corner Offset")
        layout.separator()
        generator_ui.draw_socket(layout, md, identifiers, "Common Offset")

        if not generator_ui.socket_value(md, identifiers, "Common Offset", True):
            generator_ui.draw_socket(layout, md, identifiers, "Scale")

        layout.separator()
        generator_ui.draw_socket(layout, md, identifiers, "Snap")

        if generator_ui.socket_value(md, identifiers, "Snap", False):
            generator_ui.draw_socket(layout, md, identifiers, "Snap Collection")
            generator_ui.draw_socket(layout, md, identifiers, "Snap Offset")


def _openwork_modifier(ob):
    from . import openwork_nodes

    return generator_ui.modifier(ob, openwork_nodes)


def purge_stale_handlers() -> None:
    generator_ui.purge_stale_handlers("openwork_auto_update", ".add_openwork_generator.openwork_mesh")
