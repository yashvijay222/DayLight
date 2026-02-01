# Presage SmartSpectra SDK Docker Container
# Ubuntu 22.04 with C++ SDK for vital sign detection
# Receives video frames via TCP, outputs metrics via TCP
# Note: SmartSpectra SDK is only available for amd64

# syntax=docker/dockerfile:1.7
FROM --platform=linux/amd64 ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

RUN --mount=type=cache,target=/var/lib/apt \
    --mount=type=cache,target=/var/cache/apt \
    rm -f /etc/apt/apt.conf.d/docker-clean \
 && apt-get update \
 && apt-get install -y \
    build-essential git gpg curl pkg-config \
    lsb-release \
    libcurl4-openssl-dev libssl-dev \
    libv4l-dev libgles2-mesa-dev libegl1-mesa-dev libgl1-mesa-dev libunwind-dev \
    nlohmann-json3-dev netcat-openbsd \
 && rm -rf /var/lib/apt/lists/*

# Install CMake 3.27+ (required for GLES3 in FindOpenGL)
RUN curl -L -o /tmp/cmake-3.27.0-linux-x86_64.sh \
    https://github.com/Kitware/CMake/releases/download/v3.27.0/cmake-3.27.0-linux-x86_64.sh \
 && chmod +x /tmp/cmake-3.27.0-linux-x86_64.sh \
 && /tmp/cmake-3.27.0-linux-x86_64.sh --skip-license --prefix=/usr/local \
 && rm /tmp/cmake-3.27.0-linux-x86_64.sh
    
# Add Presage repository
RUN curl -s "https://presage-security.github.io/PPA/KEY.gpg" | gpg --dearmor > /etc/apt/trusted.gpg.d/presage-technologies.gpg \
    && curl -s --compressed -o /etc/apt/sources.list.d/presage-technologies.list \
       "https://presage-security.github.io/PPA/presage-technologies.list"

# Install SmartSpectra SDK (will pull in Presage's custom OpenCV)
RUN --mount=type=cache,target=/var/lib/apt \
--mount=type=cache,target=/var/cache/apt \
rm -f /etc/apt/apt.conf.d/docker-clean \
&& apt-get update \
&& apt-get install -y libsmartspectra-dev=2.0.4 \
&& rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy source files
COPY presage_daemon.cpp CMakeLists.txt ./

# Build the daemon
RUN mkdir build && cd build \
    && cmake -DCMAKE_BUILD_TYPE=Release .. \
    && make -j$(nproc)

# Create recordings directory
RUN mkdir -p /app/recordings

# Environment variables
ENV SMARTSPECTRA_API_KEY=""
ENV VIDEO_INPUT_PORT=9001
ENV METRICS_OUTPUT_PORT=9002
ENV HEADLESS=true
ENV VERBOSITY=1
ENV PRESAGE_RECORDINGS_DIR=/app/recordings
ENV PRESAGE_VIDEO_FPS=30

# Run the daemon
CMD ["./build/presage_daemon"]
