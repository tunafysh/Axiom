cmake_minimum_required(VERSION 3.15)
project(axiom-emulator CXX)




add_library(axiom-emulator src/axiom-emulator.cpp)
target_include_directories(axiom-emulator PUBLIC include)



set_target_properties(axiom-emulator PROPERTIES PUBLIC_HEADER "include/axiom-emulator.h")
install(TARGETS axiom-emulator)
