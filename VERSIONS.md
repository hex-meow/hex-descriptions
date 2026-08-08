# 产品版本索引

| 产品 | 包名 | kind | 当前版本 | tag | 备注 |
|---|---|---|---|---|---|
| firefly_y6 | xpkg_urdf_firefly_y6 | arm | 1.1.0 | `firefly_y6/v1.1.0` | 1.0.0=原始导出;1.1.0=visual/collision 分离+ament 迁移。待零点重导出 MAJOR+更名 |
| gp80 | hex_gp80_description | ee | 0.2.0 | 尚未发布 | 双平行爪铰接化：`finger_joint1` driver、另一指和齿轮 mimic；tcp 待确认 |
| lifta70 | hex_lifta70_description | lift | 0.0.1 | 尚未发布 | trial：现有 CAD mesh 手改；总高 `lift_joint` + 中间段 0.5× mimic；待正式重导出 |

规则:cut release = 打前缀 tag,tag 版本必须等于该产品 model.yaml 的 version(`tools/validate.py` 校验)。
