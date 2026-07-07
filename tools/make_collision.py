#!/usr/bin/env python3
"""Generate per-link convex-hull collision meshes for a product.

Reads  products/<name>/meshes/visual/*.STL
Writes products/<name>/meshes/collision/<link>.stl  (binary STL, convex hull)

This is a MANUAL tool: run it, eyeball the result, commit the output.
It is deliberately NOT a CI/release gate (see robot-overall-design/06-urdf-distribution.md).
Convex hulls are a coarse first cut — replace individual links with hand-tuned
primitives or decimated meshes where a hull is too fat (e.g. between gripper fingers).

Dependencies: numpy + scipy only.

Usage:
    python3 tools/make_collision.py products/firefly_y6 [products/gp80 ...]
"""
import struct
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull

BINARY_TRI = np.dtype([("normal", "<f4", 3), ("verts", "<f4", (3, 3)), ("attr", "<u2")])


def read_stl_vertices(path: Path) -> np.ndarray:
    data = path.read_bytes()
    if len(data) >= 84:
        (n,) = struct.unpack_from("<I", data, 80)
        if len(data) == 84 + 50 * n:
            tris = np.frombuffer(data, dtype=BINARY_TRI, count=n, offset=84)
            return tris["verts"].reshape(-1, 3).astype(np.float64)
    # ASCII fallback
    verts = []
    for line in data.decode("ascii", errors="ignore").splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[0] == "vertex":
            verts.append([float(x) for x in parts[1:]])
    if not verts:
        raise ValueError(f"cannot parse STL: {path}")
    return np.array(verts, dtype=np.float64)


def write_hull_stl(path: Path, points: np.ndarray, hull: ConvexHull) -> None:
    buf = bytearray(struct.pack("<80sI", b"hex-descriptions convex-hull collision mesh", len(hull.simplices)))
    for simplex, eq in zip(hull.simplices, hull.equations):
        normal = eq[:3]  # outward unit normal from the hull facet equation
        p0, p1, p2 = points[simplex]
        if np.dot(np.cross(p1 - p0, p2 - p0), normal) < 0:
            p1, p2 = p2, p1  # wind triangle to match the outward normal
        buf += struct.pack("<3f", *normal)
        for p in (p0, p1, p2):
            buf += struct.pack("<3f", *p)
        buf += struct.pack("<H", 0)
    path.write_bytes(bytes(buf))


def process_product(product_dir: Path) -> bool:
    visual_dir = product_dir / "meshes" / "visual"
    collision_dir = product_dir / "meshes" / "collision"
    if not visual_dir.is_dir():
        print(f"error: {visual_dir} does not exist", file=sys.stderr)
        return False
    collision_dir.mkdir(parents=True, exist_ok=True)
    ok = True
    for src in sorted(visual_dir.iterdir()):
        if src.suffix.lower() != ".stl":
            continue
        dst = collision_dir / (src.stem + ".stl")
        try:
            verts = read_stl_vertices(src)
            points = np.unique(verts.round(9), axis=0)
            hull = ConvexHull(points)
            write_hull_stl(dst, points, hull)
            print(
                f"  {src.name}: {len(verts) // 3} tris / {len(points)} unique verts"
                f" -> hull {len(hull.simplices)} tris ({dst.relative_to(product_dir)})"
            )
        except Exception as exc:  # noqa: BLE001 — report and continue with the other links
            print(f"error: {src}: {exc}", file=sys.stderr)
            ok = False
    return ok


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    ok = True
    for arg in sys.argv[1:]:
        product = Path(arg)
        print(f"{product}:")
        ok &= process_product(product)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
