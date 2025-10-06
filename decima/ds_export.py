"""Utilities for exporting Death Stranding mesh streams.

At the moment the toolkit can parse the shared ``VertexStreamSet`` blocks that
Death Stranding uses, but the exporter still operates on the older Horizon
layout.  The helpers in this module centralise the logic that groups
primitives by their shared stream set so the main exporter can short-circuit
before attempting to treat them like Horizon meshes.

The actual stream repacking work remains unimplemented – the format requires
rebuilding the per-mesh chunk table before any bytes can be written back to
disk.  Raising a dedicated exception keeps the failure explicit and avoids the
generic ``AttributeError`` that Blender would otherwise surface when the
Horizon codepath touches ``vertexStream`` on a Death Stranding primitive.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


class DeathStrandingExportError(RuntimeError):
    """Raised when exporting a Death Stranding mesh is not yet supported."""


@dataclass(frozen=True)
class PrimitiveBinding:
    """Links a mesh resource primitive to its object name in Blender.

    The Horizon exporter addresses objects via the naming scheme
    ``"{primitive_index}_{mesh_name}"``.  Grouping the primitives that share a
    ``VertexStreamSet`` allows future work to repack the shared streams instead
    of rewriting them per primitive as Horizon does.
    """

    primitive_index: int
    mesh_name: str

    @property
    def object_name(self) -> str:
        return f"{self.primitive_index}_{self.mesh_name}"


def collect_primitives_sharing_vertex_set(
    mesh_resource,
    vertex_guid,
    mesh_name: str,
) -> List[PrimitiveBinding]:
    """Return the mesh primitives that reference ``vertex_guid``.

    Parameters
    ----------
    mesh_resource:
        Either ``RegularSkinnedMeshResource`` or ``StaticMeshResource`` as
        parsed by the add-on.  The object is assumed to expose a ``primitives``
        attribute containing ``RenderingPrimitiveResource`` instances, each of
        which provides a ``vertexRef`` reference with a ``guid`` attribute.
    vertex_guid:
        The UUID shared by the ``VertexStreamSet`` block.
    mesh_name:
        Used to reproduce Blender's export object naming pattern.
    """

    bindings: List[PrimitiveBinding] = []
    primitives = getattr(mesh_resource, "primitives", [])
    for index, primitive in enumerate(primitives):
        reference = getattr(primitive, "vertexRef", None)
        if reference is None:
            continue
        if getattr(reference, "guid", None) == vertex_guid:
            bindings.append(PrimitiveBinding(index, mesh_name))
    return bindings


def export_death_stranding_mesh(
    mesh_resource,
    primitive,
    primitive_index: int,
    mesh_name: str,
) -> None:
    """Entry point used by :func:`ExportMesh` when a DS primitive is detected.

    The routine currently raises :class:`DeathStrandingExportError` to make it
    explicit to callers – and therefore to Blender users – that exporting a
    Death Stranding mesh still requires implementing the chunked stream
    repacker.  Returning ``None`` here would silently fall back to the Horizon
    codepath, which would in turn corrupt the file by writing a per-primitive
    stream layout.
    """

    vertex_guid = getattr(getattr(primitive, "vertexRef", None), "guid", None)
    if vertex_guid is None:
        raise DeathStrandingExportError(
            "Primitive does not expose a vertex stream reference; cannot export"
        )

    bindings = collect_primitives_sharing_vertex_set(mesh_resource, vertex_guid, mesh_name)
    referenced_objects = [binding.object_name for binding in bindings]

    raise DeathStrandingExportError(
        "Death Stranding export requires repacking shared vertex/index streams "
        "(referenced Blender objects: %s)" % ", ".join(referenced_objects)
    )

