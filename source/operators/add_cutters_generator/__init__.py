# SPDX-License-Identifier: GPL-3.0-or-later


import bpy
from bpy.props import StringProperty
from bpy.types import Operator, Panel

from ...lib import gemlib
from .. import generator_ui


class OBJECT_OT_cutters_generator_add(Operator):
    bl_label = "Cutters Generator"
    bl_description = "Create auto-updating cutters for gems in a collection"
    bl_idname = "object.jewelcraft_cutters_generator_add"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    source_collection_name: StringProperty(
        name="Gem Collection",
        description="Collection containing gem objects",
    )

    def draw(self, context):
        generator_ui.draw_source_collection_search(self.layout, self)

    def execute(self, context):
        from . import cutters_mesh

        return generator_ui.execute_add_operator(
            self,
            context,
            cutters_mesh.create_object,
            purge_stale_handlers,
            "Created cutters generator",
        )

    def invoke(self, context, event):
        return generator_ui.invoke_add_operator(self, context, purge_stale_handlers)


class OBJECT_PT_cutters_generator_modifier(Panel):
    bl_label = "Cutters Generator"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "modifier"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob is not None and _cutters_modifier(ob) is not None

    def draw(self, context):
        md = _cutters_modifier(context.object)
        identifiers = _socket_identifiers(md)
        cut, shape = _source_cut_shape(context.object)

        layout = self.layout
        generator_ui.setup_property_layout(layout)

        from . import cutters_mesh

        generator_ui.draw_collection(layout, context.object, cutters_mesh.PROP_SOURCE_COLLECTION)

        layout.separator()

        row = layout.row()
        row.use_property_split = False
        _draw_socket(row, md, identifiers, "Handle")

        col = layout.column()
        col.enabled = bool(_socket_value(md, identifiers, "Handle", True))
        _draw_socket(col, md, identifiers, "Handle Top", text="Top")

        if _is_round_or_square(shape):
            _draw_socket(col, md, identifiers, "Handle Length", text="Size")
        else:
            _draw_socket(col, md, identifiers, "Handle Length", text="Length")
            _draw_socket(col, md, identifiers, "Handle Width", text="Width")

        _draw_socket(col, md, identifiers, "Handle Bottom", text="Bottom")

        if shape == gemlib.SHAPE_FANTASY and cut in {"PEAR", "HEART"}:
            _draw_socket(col, md, identifiers, "Handle Position Offset")

        layout.separator()
        layout.label(text="Girdle")

        col = layout.column()
        _draw_socket(
            col,
            md,
            identifiers,
            "Girdle Top",
            text="Top" if _socket_value(md, identifiers, "Handle", True) else "Table",
        )

        if shape == gemlib.SHAPE_TRIANGLE or cut == "HEART":
            _draw_socket(col, md, identifiers, "Girdle Length Offset", text="Length Offset")
            _draw_socket(col, md, identifiers, "Girdle Width Offset", text="Width Offset")
        else:
            _draw_socket(col, md, identifiers, "Girdle Length Offset", text="Size Offset")

        _draw_socket(col, md, identifiers, "Girdle Bottom", text="Bottom")

        layout.separator()

        row = layout.row()
        row.use_property_split = False
        _draw_socket(row, md, identifiers, "Hole")

        use_hole = bool(_socket_value(md, identifiers, "Hole", True))
        show_culet_size = not use_hole and shape == gemlib.SHAPE_RECTANGLE

        col = layout.column()
        _draw_socket(col, md, identifiers, "Hole Top", text="Top" if use_hole else "Culet")

        if show_culet_size:
            _draw_socket(col, md, identifiers, "Hole Length", text="Length")

        sub = col.column()
        sub.enabled = use_hole

        if _is_round_or_square(shape):
            _draw_socket(sub, md, identifiers, "Hole Length", text="Size")
        else:
            if not show_culet_size:
                _draw_socket(sub, md, identifiers, "Hole Length", text="Length")
            _draw_socket(sub, md, identifiers, "Hole Width", text="Width")

        _draw_socket(sub, md, identifiers, "Hole Bottom", text="Bottom")

        if cut in {"PEAR", "HEART"}:
            col = layout.column()
            col.enabled = cut == "PEAR"
            _draw_socket(col, md, identifiers, "Hole Position Offset")

        layout.separator()

        _draw_socket(layout, md, identifiers, "Seat Depth")

        layout.separator()

        row = layout.row()
        row.use_property_split = False
        _draw_socket(row, md, identifiers, "Curve Seat")

        col = layout.column()
        col.enabled = bool(_socket_value(md, identifiers, "Curve Seat", False))
        _draw_socket(col, md, identifiers, "Curve Seat Profile", text="Profile")
        _draw_socket(col, md, identifiers, "Curve Seat Segments", text="Segments")

        if shape != gemlib.SHAPE_ROUND:
            if shape == gemlib.SHAPE_TRIANGLE:
                layout.separator()
                layout.label(text="Curve Profile")

                col = layout.column()
                _draw_socket(col, md, identifiers, "Curve Profile Factor", text="Factor")
                sub = col.column()
                sub.enabled = _socket_value(md, identifiers, "Curve Profile Factor", 0.0) != 0.0
                _draw_socket(sub, md, identifiers, "Curve Profile Segments", text="Segments")

            elif cut in {"MARQUISE", "PEAR", "HEART"}:
                layout.separator()
                layout.label(text="Profile")

                col = layout.column()
                _draw_socket(col, md, identifiers, "Profile Factor 1", text="Factor 1")
                _draw_socket(col, md, identifiers, "Profile Factor 2", text="Factor 2")
                if cut == "HEART":
                    _draw_socket(col, md, identifiers, "Profile Factor 3", text="Factor 3")

            if shape != gemlib.SHAPE_FANTASY:
                layout.separator()
                layout.label(text="Bevel Corners")

                col = layout.column()
                bevel_socket = "Bevel Corners Width" if shape == gemlib.SHAPE_RECTANGLE else "Bevel Corners Percent"
                _draw_socket(col, md, identifiers, bevel_socket, text="Width")
                sub = col.column()
                sub.enabled = _socket_value(md, identifiers, bevel_socket, 0.0) != 0.0
                _draw_socket(sub, md, identifiers, "Bevel Corners Segments", text="Segments")
                _draw_socket(sub, md, identifiers, "Bevel Corners Profile", text="Profile")

        if shape == gemlib.SHAPE_ROUND or shape == gemlib.SHAPE_FANTASY:
            layout.separator()
            _draw_socket(layout, md, identifiers, "Detalization")


def _source_cut_shape(ob) -> tuple[str, int | None]:
    from . import cutters_mesh

    source_coll = bpy.data.collections.get(ob.get(cutters_mesh.PROP_SOURCE_COLLECTION, ""))

    if source_coll is not None:
        for gem_ob in source_coll.all_objects:
            if gem_ob.type == "MESH" and "gem" in gem_ob:
                cut = gem_ob["gem"].get("cut", "ROUND")

                try:
                    return cut, gemlib.CUTS[cut].shape
                except KeyError:
                    break

    return "ROUND", gemlib.SHAPE_ROUND


def _is_round_or_square(shape: int | None) -> bool:
    return shape in {gemlib.SHAPE_ROUND, gemlib.SHAPE_SQUARE}


def _cutters_modifier(ob):
    from . import cutters_nodes

    return generator_ui.modifier(ob, cutters_nodes)


def _socket_identifiers(md) -> dict[str, str]:
    from . import cutters_nodes

    return generator_ui.socket_identifiers(md, cutters_nodes)


_draw_socket = generator_ui.draw_socket
_socket_value = generator_ui.socket_value


def purge_stale_handlers() -> None:
    generator_ui.purge_stale_handlers("cutters_auto_update", ".add_cutters_generator.cutters_mesh")
