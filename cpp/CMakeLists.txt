cmake_minimum_required(VERSION 3.10)
project(adaptivecad_cpp)

add_library(adaptivecad_cpp
    src/Vec3.cpp
    src/Quaternion.cpp
    src/Matrix4.cpp
)

target_include_directories(adaptivecad_cpp PUBLIC include)
