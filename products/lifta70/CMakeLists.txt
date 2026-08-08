cmake_minimum_required(VERSION 3.8)
project(hex_lifta70_description)

find_package(ament_cmake REQUIRED)

install(DIRECTORY urdf meshes DESTINATION share/${PROJECT_NAME})
install(FILES model.yaml DESTINATION share/${PROJECT_NAME})

ament_package()
