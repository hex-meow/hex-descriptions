#!/usr/bin/env python3
"""Validate a product directory: URDF <-> model.yaml <-> package.xml consistency.

Checks (per products/<name>):
  1. model.yaml has the required keys; version is semver-ish.
  2. package.xml <name> == model.yaml.package and <version> == model.yaml.version.
  3. URDF parses; <robot name> == model.yaml.model.
  4. Movable-joint count == dof; joint names (document order) == joint_names.
  5. Every link has <inertial> with finite mass > 0 and finite inertia terms (no NaN).
  6. root_link / tip_link (if set) exist; root_link is the tree root (never a child).
  7. Every package:// mesh URI uses model.yaml.package as root and the file exists.
  8. Every <visual> with a mesh has a <collision> in the same link, and collision
     geometry is either a primitive or a mesh under meshes/collision/.

Usage:
    python3 tools/validate.py products/*            # or individual product dirs
Exit code 0 = all pass.
"""
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

MOVABLE = {"revolute", "continuous", "prismatic"}
REQUIRED_KEYS = {"model", "kind", "version", "dof", "joint_names", "root_link", "package", "urdf"}


def fail(errors: list, msg: str) -> None:
    errors.append(msg)


def finite(value: str) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def validate_product(product_dir: Path) -> list:
    errors: list = []
    manifest_path = product_dir / "model.yaml"
    if not manifest_path.is_file():
        return [f"missing {manifest_path}"]
    manifest = yaml.safe_load(manifest_path.read_text())

    missing = REQUIRED_KEYS - set(manifest)
    if missing:
        fail(errors, f"model.yaml missing keys: {sorted(missing)}")
        return errors
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(manifest["version"])):
        fail(errors, f"model.yaml version {manifest['version']!r} is not MAJOR.MINOR.PATCH")

    # package.xml consistency
    pkg_xml = product_dir / "package.xml"
    if pkg_xml.is_file():
        pkg = ET.parse(pkg_xml).getroot()
        pkg_name = pkg.findtext("name")
        pkg_version = pkg.findtext("version")
        if pkg_name != manifest["package"]:
            fail(errors, f"package.xml name {pkg_name!r} != model.yaml package {manifest['package']!r}")
        if pkg_version != str(manifest["version"]):
            fail(errors, f"package.xml version {pkg_version!r} != model.yaml version {manifest['version']!r}")
    else:
        fail(errors, "missing package.xml")

    # URDF checks
    urdf_path = product_dir / manifest["urdf"]
    if not urdf_path.is_file():
        fail(errors, f"missing URDF {urdf_path}")
        return errors
    robot = ET.parse(urdf_path).getroot()
    if robot.get("name") != manifest["model"]:
        fail(errors, f"URDF robot name {robot.get('name')!r} != model.yaml model {manifest['model']!r}")

    links = robot.findall("link")
    link_names = [l.get("name") for l in links]
    joints = robot.findall("joint")
    movable = [j for j in joints if j.get("type") in MOVABLE]
    # mimic 从动关节不算 DOF(11-ee-api §9:一个电机一根轴;joint_names 只列 driver)。
    drivers = [j for j in movable if j.find("mimic") is None]
    driver_names = [j.get("name") for j in drivers]
    all_joint_names = {j.get("name") for j in joints}
    for j in movable:
        m = j.find("mimic")
        if m is not None and m.get("joint") not in all_joint_names:
            fail(errors, f"joint {j.get('name')}: mimic 引用不存在的关节 {m.get('joint')!r}")

    if len(drivers) != int(manifest["dof"]):
        fail(errors, f"URDF driver(non-mimic) joints {len(drivers)} != model.yaml dof {manifest['dof']}")
    if driver_names != list(manifest["joint_names"] or []):
        fail(errors, f"URDF driver joint order {driver_names} != model.yaml joint_names {manifest['joint_names']}")

    children = {j.findtext("child/[@link]") or j.find("child").get("link") for j in joints if j.find("child") is not None}
    roots = [n for n in link_names if n not in children]
    if manifest["root_link"] not in link_names:
        fail(errors, f"root_link {manifest['root_link']!r} not a URDF link")
    elif roots != [manifest["root_link"]]:
        fail(errors, f"URDF tree root(s) {roots} != model.yaml root_link {manifest['root_link']!r}")
    tip = manifest.get("tip_link")
    if tip and tip not in link_names:
        fail(errors, f"tip_link {tip!r} not a URDF link")

    for link in links:
        name = link.get("name")
        inertial = link.find("inertial")
        if inertial is None:
            # 纯坐标系 link(无 visual/collision,如 tcp)允许无惯量(URDF 缺省=零质量 frame)。
            if link.find("visual") is None and link.find("collision") is None:
                continue
            fail(errors, f"link {name}: missing <inertial> (gravity comp requires it)")
            continue
        mass = inertial.find("mass")
        if mass is None or not finite(mass.get("value")) or float(mass.get("value")) <= 0:
            fail(errors, f"link {name}: mass missing/non-finite/<=0")
        inertia = inertial.find("inertia")
        if inertia is None or not all(finite(inertia.get(k)) for k in ("ixx", "ixy", "ixz", "iyy", "iyz", "izz")):
            fail(errors, f"link {name}: inertia tensor missing or non-finite (NaN guard)")

        has_visual_mesh = link.find("visual/geometry/mesh") is not None
        collision = link.find("collision")
        if has_visual_mesh and collision is None:
            fail(errors, f"link {name}: has visual mesh but no <collision>")
        cmesh = link.find("collision/geometry/mesh")
        if cmesh is not None and "/meshes/collision/" not in cmesh.get("filename", ""):
            fail(errors, f"link {name}: collision mesh {cmesh.get('filename')!r} is not under meshes/collision/ "
                         "(full-res visual mesh reused for collision?)")

    for mesh in robot.iter("mesh"):
        uri = mesh.get("filename", "")
        m = re.fullmatch(r"package://([^/]+)/(.+)", uri)
        if not m:
            fail(errors, f"mesh URI {uri!r} is not package://")
            continue
        if m.group(1) != manifest["package"]:
            fail(errors, f"mesh URI {uri!r} package root != model.yaml package {manifest['package']!r}")
        if not (product_dir / m.group(2)).is_file():
            fail(errors, f"mesh file missing on disk: {uri}")

    for joint in movable:
        if joint.get("type") != "continuous" and joint.find("limit") is None:
            fail(errors, f"joint {joint.get('name')}: movable but has no <limit>")

    return errors


def main() -> int:
    args = [Path(a) for a in sys.argv[1:]]
    if not args:
        print(__doc__, file=sys.stderr)
        return 2
    failed = False
    for product in args:
        if not (product / "model.yaml").exists() and not product.is_dir():
            continue
        errors = validate_product(product)
        status = "OK" if not errors else "FAIL"
        print(f"[{status}] {product}")
        for e in errors:
            print(f"    - {e}")
        failed |= bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
