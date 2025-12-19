cmake_minimum_required(VERSION 3.15)
project(axiom-emulator C)

# Option to decide if we build an executable or a library
option(BUILD_AS_EXECUTABLE "Build axiom-emulator as an executable" ON)


find_package(raylib REQUIRED)


# List of sources
set(SOURCES src/main.c)

# Build depending on the option
if(BUILD_AS_EXECUTABLE)
    add_executable(axiom-emulator ${SOURCES})
    target_link_libraries(axiom-emulator PRIVATE raylib)
else()
    add_library(axiom-emulator SHARED ${SOURCES})
endif()

target_include_directories(axiom-emulator PUBLIC external)
install(TARGETS axiom-emulator)
