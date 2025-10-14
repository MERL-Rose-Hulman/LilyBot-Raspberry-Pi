cmake_minimum_required(VERSION 3.16)

project(lilybot_cpp VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

add_library(lilybot
    src/i2c_bus.cpp
    src/gpio_line.cpp
    src/drv8830.cpp
    src/tb6612.cpp
    src/lcd.cpp
    src/ultrasonic.cpp
    src/robot.cpp
    src/kit.cpp
)

target_include_directories(lilybot
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_compile_options(lilybot
    PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion>
)

add_executable(lilybot_demo src/main.cpp)
target_link_libraries(lilybot_demo PRIVATE lilybot)

install(TARGETS lilybot lilybot_demo
    RUNTIME DESTINATION bin
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
)
