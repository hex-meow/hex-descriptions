# hex-descriptions

Single source of truth for hexmeow robot product descriptions: URDF + full-resolution
visual meshes + simplified collision meshes, one subdirectory per product.

At runtime a live robot **self-describes** over Zenoh (`arm/urdf` → `UrdfResource`,
assembled whole-robot URDF at `<idx>/urdf` — see `robot-overall-design/02-arm-api.md`).
This repo is the *upstream source* that feeds everything the runtime path cannot cover:
the controller image (buildroot installs to `/usr/share/hexmeow/urdf/`), ROS 2
workspaces, GUI mesh bundles, and hardware-free simulation/CI.
Design rationale: `robot-overall-design/06-urdf-distribution.md`.

## Layout

```
products/<model>/          # each subdir is a valid ament_cmake package (colcon-buildable as-is)
  package.xml              # package name == the package:// root used inside the URDF
  model.yaml               # machine-checkable manifest: model, kind, version, dof, joints, links
  urdf/<...>.urdf          # plain URDF (no xacro at current scale)
  meshes/visual/*.STL      # full-res, for rendering only (GUI / RViz)
  meshes/collision/*.stl   # simplified (convex hull) — what <collision> references
tools/validate.py          # consistency gate: URDF <-> model.yaml <-> package.xml
tools/make_collision.py    # manual convex-hull generator (numpy+scipy); run + commit output
VERSIONS.md                # human index: product -> current version/tag
```

## Products

| product | package | kind | dof | version |
|---|---|---|---|---|
| firefly_y6 | `xpkg_urdf_firefly_y6` (legacy name kept, see model.yaml) | arm | 6 | 1.1.0 |
| gp80 | `hex_gp80_description` | hand (gripper) | 0 (rigid body) | 0.1.0 |

New products use the `hex_<model>_description` package-name convention.

## Versioning

Per-product **prefixed git tags**: `<model>/vMAJOR.MINOR.PATCH` (e.g. `firefly_y6/v1.1.0`).
Each product has its own independent version line inside this one repo; the same version
string lives in its `model.yaml` (`tools/validate.py` is the consistency check).
Product PCBs store `model` + this description version so a controller can pick
`/usr/share/hexmeow/urdf/<model>.urdf` and assert the match.

- **MAJOR** — kinematics/frame/joint-name/DOF changes that break IK, planning, or
  recorded datasets. Consumers must re-pin.
- **MINOR** — compatible additions: better meshes, new variant, added metadata.
- **PATCH** — inertial refinements, materials, docs.

This version axis is orthogonal to the Zenoh API's `ApiVersion` (proto).

## Consuming

- **ROS 2**: clone as a sibling and `colcon build --base-paths` it (each product dir is
  an ament package), or pin a tag in a `.repos` file. `package://` URIs resolve normally.
- **hex-controller / buildroot**: the BR2_EXTERNAL recipe copies a pinned tag's
  `urdf/` + `meshes/collision/` into `/usr/share/hexmeow/urdf/` (offline build; no
  network fetch at build time).
- **GUI / web**: take `urdf/` + `meshes/visual/` from a pinned tag at build time; the
  long-term path is fetching from the robot itself (`arm/urdf` + content-addressed
  `asset://<sha256>` mesh queryables).

## Validation

```sh
python3 tools/validate.py products/*
```

Checks DOF/joint-name/root-tip consistency against `model.yaml`, finite inertials
(NaN guard), `package://` roots and on-disk mesh existence, and that no full-res visual
mesh is reused as collision geometry.

## What is deliberately NOT here

- CAD sources (SLDASM/STEP) — stay in the CAD vault; only exported artifacts land here.
- SW2URDF export junk (`export.log`, `.csv` sidecars, ROS 1 launch boilerplate).
- xacro, git-LFS, CI artifact pipelines, MJCF/glTF exports — deferred until a consumer
  actually needs them (see design doc §不做清单).
- Whole-robot composed URDFs — composition (base+lift+arm+gripper) is owned by the
  robot at runtime, not by static files here.
