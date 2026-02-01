cmake_minimum_required(VERSION 3.27.0)
project(presage_daemon CXX)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find required packages
find_package(SmartSpectra REQUIRED)
find_package(OpenCV REQUIRED)

# Create executable
add_executable(presage_daemon presage_daemon.cpp)

# Link libraries
target_link_libraries(presage_daemon
    SmartSpectra::Container
    ${OpenCV_LIBS}
)

target_compile_options(presage_daemon PRIVATE -Wall -Wextra -O2)
