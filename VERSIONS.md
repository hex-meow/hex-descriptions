# 产品版本索引

| 产品 | 包名 | kind | 当前版本 | tag | 备注 |
|---|---|---|---|---|---|
| firefly_y6 | xpkg_urdf_firefly_y6 | arm | 1.1.0 | `firefly_y6/v1.1.0` | 1.0.0=原始导出;1.1.0=visual/collision 分离+ament 迁移。待零点重导出 MAJOR+更名 |
| gp80 | hex_gp80_description | hand | 0.1.0 | `gp80/v0.1.0` | 单刚体(手指未铰接);安装面待确认 |

规则:cut release = 打前缀 tag,tag 版本必须等于该产品 model.yaml 的 version(`tools/validate.py` 校验)。
