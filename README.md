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
| gp80 | `hex_gp80_description` | ee (parallel gripper) | 1 | 0.2.0 |
| lifta70 | `hex_lifta70_description` | lift | 1 (2 coupled prismatic joints) | 0.0.1 (trial) |

New products use the `hex_<model>_description` package-name convention.

## 机械导出约定：单自由度多级伸缩机构

以 LiftA70 这类“三个刚体、两个移动副、一个驱动自由度”的望远镜升降机为例，
**不要为了让 DOF 看起来等于 1 而把中间筒合并、固定或删掉**。三个机械构件必须分别导出，
这样渲染、自碰撞、质量、质心和惯量才仍然对应真实刚体。独立自由度数量由 driver/mimic
关系表达，不等于 URDF 中 movable joint 的数量。

LiftA70 的正典坐标约定如下：

- `lift_joint` 是唯一 driver，`q` 直接表示顶端平台相对最低位的总升高，单位 m，
  `lower=0`、`upper=0.70`、轴为 `0 0 1`。
- `intermediate_stage_joint` 是从动关节，中间段绝对升高恒为平台的一半：
  `<mimic joint="lift_joint" multiplier="0.5" offset="0"/>`，自身有限行程为
  `[0, 0.35]`。
- `model.yaml` 写 `dof: 1` 和 `joint_names: [lift_joint]`；mimic 关节不出现在
  命令、状态向量或 `joint_names` 中。
- `q=0` 必须是完全缩回/最低位，正方向必须向上。导出前应在 CAD 里建立并保留
  `base_link` 底部安装基准和 `arm_mount` 顶端安装基准，后者随 `platform_link`
  运动。

为了让公开关节坐标与平台高度一致，正典 URDF 使用运动学等效的并联树，而不是 CAD
装配界面里直观的串联树：

```text
base_link
├── lift_joint ───────────────> platform_link       q
│   └── arm_mount_joint ──────> arm_mount           fixed
└── intermediate_stage_joint ─> intermediate_link   0.5 q (mimic)
```

对应的关键 URDF 结构是：

```xml
<joint name="lift_joint" type="prismatic">
  <parent link="base_link"/>
  <child link="platform_link"/>
  <axis xyz="0 0 1"/>
  <limit lower="0" upper="0.70" effort="..." velocity="..."/>
</joint>

<joint name="intermediate_stage_joint" type="prismatic">
  <parent link="base_link"/>
  <child link="intermediate_link"/>
  <axis xyz="0 0 1"/>
  <limit lower="0" upper="0.35" effort="..." velocity="..."/>
  <mimic joint="lift_joint" multiplier="0.5" offset="0"/>
</joint>
```

机械侧正式交付还必须满足：

1. 三个 link 分别给出准确质量、质心和惯量，不能把移动件质量并入底座。
2. 给出全精度 visual mesh；collision mesh 另行简化，不能直接复用全精度网格。
3. 所有 mesh、inertial origin、joint origin 和安装 frame 必须使用明确且一致的
   `q=0` 坐标基准；不得靠查看 STL 包围盒猜安装面。
4. `arm_mount` 必须落在真实机械安装坐标系上，并明确 xyz/rpy、孔位原点和 +Z 朝向。
5. `effort` 填平台坐标下经过验证的名义推力，`velocity` 填平台总高度坐标下的名义速度；
   mimic 关节也必须给有限 limit。
6. 交付前检查 `q={0, 0.35, 0.70}`：平台附加位移应为 `{0, 0.35, 0.70}` m，
   中间段应为 `{0, 0.175, 0.35}` m。

如果 CAD 导出插件不能生成上述并联树或 `<mimic>`，机械同事可以交付保留三 link 和两个
prismatic joint 的原始串联 URDF；仓库维护者再做确定性的后处理。不能交付只有一个 link/joint
且已丢失中间构件信息的扁平版本。

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
