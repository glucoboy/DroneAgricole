# syntax=docker/dockerfile:1.7

FROM ros:humble-ros-base-jammy AS ros-humble-dependencies

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       cmake \
       libeigen3-dev \
       libgl1-mesa-dev \
       libqt6opengl6-dev \
       libtiff-dev \
       libyaml-cpp-dev \
       ninja-build \
       python3-colcon-common-extensions \
       qt6-base-dev \
       qt6-base-dev-tools \
       ros-humble-demo-nodes-cpp \
       ros-humble-geometry-msgs \
       ros-humble-nav-msgs \
       ros-humble-rosbag2 \
       ros-humble-rosbag2-cpp \
       ros-humble-rosbag2-storage-mcap \
       ros-humble-rosidl-default-generators \
       ros-humble-sensor-msgs \
       ros-humble-std-msgs \
    && rm -rf /var/lib/apt/lists/*

COPY software/src/livox_ros_driver2_msgs_compat /opt/drone_tools_ws/src/livox_ros_driver2
RUN source /opt/ros/humble/setup.bash \
    && cd /opt/drone_tools_ws \
    && colcon build --merge-install --cmake-args -DCMAKE_BUILD_TYPE=Release \
    && rm -rf build log

ENV AMENT_PREFIX_PATH=/opt/drone_tools_ws/install
ENV LD_LIBRARY_PATH=/opt/drone_tools_ws/install/lib:/usr/local/lib

WORKDIR /workspace


FROM ros-humble-dependencies AS ros-humble-core

ARG CMAKE_BUILD_PARALLEL_LEVEL=2

COPY CMakeLists.txt /opt/drone_agricole_src/CMakeLists.txt
COPY software/cpp /opt/drone_agricole_src/software/cpp
RUN source /opt/ros/humble/setup.bash \
    && source /opt/drone_tools_ws/install/setup.bash \
    && cmake -S /opt/drone_agricole_src -B /opt/drone_agricole_build -G Ninja \
       -DCMAKE_BUILD_TYPE=Release \
       -DCMAKE_INSTALL_PREFIX=/usr/local \
       -DDRONE_AGRICOLE_BUILD_DASHBOARD=OFF \
       -DDRONE_AGRICOLE_BUILD_TESTS=OFF \
       -DDRONE_AGRICOLE_WITH_ROS2=ON \
    && cmake --build /opt/drone_agricole_build --parallel "${CMAKE_BUILD_PARALLEL_LEVEL}" \
    && cmake --install /opt/drone_agricole_build \
    && rm -rf /opt/drone_agricole_build /opt/drone_agricole_src

ENV AMENT_PREFIX_PATH=/opt/drone_tools_ws/install
ENV LD_LIBRARY_PATH=/opt/drone_tools_ws/install/lib:/usr/local/lib

WORKDIR /workspace


FROM ros-humble-core AS ros-humble

LABEL org.opencontainers.image.title="Drone Agricole - ROS 2 Humble LIO base" \
      org.opencontainers.image.version="1.0.0"

WORKDIR /workspace
CMD ["bash"]


FROM ros-humble-dependencies AS ros-humble-fastlio2

ARG CMAKE_BUILD_PARALLEL_LEVEL=4
ARG FAST_LIO_REPOSITORY=https://github.com/hku-mars/FAST_LIO.git
ARG FAST_LIO_COMMIT=a4743b095409588842a5b30ddfa27e29d2f99164

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       git \
       libeigen3-dev \
       libomp-dev \
       libpcl-dev \
       python3-colcon-common-extensions \
       python3-dev \
       ros-humble-pcl-conversions \
       ros-humble-pcl-ros \
       ros-humble-rclcpp-components \
       ros-humble-rosidl-default-generators \
       ros-humble-std-srvs \
       ros-humble-tf2-ros \
       ros-humble-visualization-msgs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/fast_lio_ws/src
RUN git -c http.version=HTTP/1.1 clone --branch ROS2 --single-branch "${FAST_LIO_REPOSITORY}" FAST_LIO \
    && cd FAST_LIO \
    && git checkout --detach "${FAST_LIO_COMMIT}" \
    && git -c http.version=HTTP/1.1 submodule update --init --recursive \
    && test "$(git rev-parse HEAD)" = "${FAST_LIO_COMMIT}" \
    && test "$(git -C include/ikd-Tree rev-parse HEAD)" = "e2e3f4e9d3b95a9e66b1ba83dc98d4a05ed8a3c4"

# Instrumentation locale, versionnée séparément du dépôt amont figé : elle
# expose les compteurs du pipeline sans modifier les paramètres algorithmiques.
COPY software/third_party/patches/fast_lio2/0001-pipeline-diagnostics.patch /tmp/fast_lio2_pipeline.patch
RUN cd /opt/fast_lio_ws/src/FAST_LIO \
    && git apply --check /tmp/fast_lio2_pipeline.patch \
    && git apply /tmp/fast_lio2_pipeline.patch \
    && rm /tmp/fast_lio2_pipeline.patch

# Le profil QoS reste best-effort par défaut pour le matériel, mais devient
# configurable afin que les benchmarks rosbag puissent exiger une livraison fiable.
COPY software/third_party/patches/fast_lio2/0002-configurable-lidar-qos.patch /tmp/fast_lio2_qos.patch
RUN cd /opt/fast_lio_ws/src/FAST_LIO \
    && git apply --check /tmp/fast_lio2_qos.patch \
    && git apply /tmp/fast_lio2_qos.patch \
    && rm /tmp/fast_lio2_qos.patch

WORKDIR /opt/fast_lio_ws
RUN source /opt/ros/humble/setup.bash \
    && source /opt/drone_tools_ws/install/setup.bash \
    && CMAKE_BUILD_PARALLEL_LEVEL="${CMAKE_BUILD_PARALLEL_LEVEL}" colcon build \
       --merge-install \
       --cmake-args -DCMAKE_BUILD_TYPE=Release \
    && rm -rf build log

ENV AMENT_PREFIX_PATH=/opt/fast_lio_ws/install:/opt/drone_tools_ws/install
ENV LD_LIBRARY_PATH=/opt/fast_lio_ws/install/lib:/opt/drone_tools_ws/install/lib:/usr/local/lib

# Le binaire propriétaire est injecté après les dépendances lourdes afin qu'une
# modification C++ ne reconstruise pas FAST-LIO2, PCL et leurs dépendances.
COPY --from=ros-humble-core /usr/local/bin/drone-agricole-tools /usr/local/bin/drone-agricole-tools

LABEL org.opencontainers.image.title="Drone Agricole - FAST-LIO2 ROS 2 Humble" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.source="https://github.com/hku-mars/FAST_LIO" \
      org.opencontainers.image.revision="a4743b095409588842a5b30ddfa27e29d2f99164"

WORKDIR /workspace
CMD ["bash"]


FROM ros-humble-dependencies AS ros-humble-pointlio

ARG CMAKE_BUILD_PARALLEL_LEVEL=4
ARG POINT_LIO_REPOSITORY=https://github.com/dfloreaa/point_lio_ros2.git
ARG POINT_LIO_COMMIT=a8e2d0d5090af97ead8dd4fac3d37cf3dbb33ff7

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       git \
       libeigen3-dev \
       libomp-dev \
       libpcl-dev \
       python3-colcon-common-extensions \
       python3-dev \
       ros-humble-pcl-conversions \
       ros-humble-pcl-ros \
       ros-humble-std-msgs \
       ros-humble-tf2-ros \
       ros-humble-visualization-msgs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/point_lio_ws/src
RUN git -c http.version=HTTP/1.1 clone "${POINT_LIO_REPOSITORY}" point_lio \
    && cd point_lio \
    && git checkout --detach "${POINT_LIO_COMMIT}" \
    && test "$(git rev-parse HEAD)" = "${POINT_LIO_COMMIT}"

COPY software/third_party/patches/point_lio/0001-pipeline-diagnostics-and-qos.patch /tmp/point_lio.patch
RUN cd /opt/point_lio_ws/src/point_lio \
    && git apply --check /tmp/point_lio.patch \
    && git apply /tmp/point_lio.patch \
    && rm /tmp/point_lio.patch

WORKDIR /opt/point_lio_ws
RUN source /opt/ros/humble/setup.bash \
    && source /opt/drone_tools_ws/install/setup.bash \
    && CMAKE_BUILD_PARALLEL_LEVEL="${CMAKE_BUILD_PARALLEL_LEVEL}" colcon build \
       --merge-install \
       --cmake-args -DCMAKE_BUILD_TYPE=Release \
    && rm -rf build log

ENV AMENT_PREFIX_PATH=/opt/point_lio_ws/install:/opt/drone_tools_ws/install
ENV LD_LIBRARY_PATH=/opt/point_lio_ws/install/lib:/opt/drone_tools_ws/install/lib:/usr/local/lib

COPY --from=ros-humble-core /usr/local/bin/drone-agricole-tools /usr/local/bin/drone-agricole-tools

LABEL org.opencontainers.image.title="Drone Agricole - Point-LIO ROS 2 Humble" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.source="https://github.com/dfloreaa/point_lio_ros2" \
      org.opencontainers.image.revision="a8e2d0d5090af97ead8dd4fac3d37cf3dbb33ff7"

WORKDIR /workspace
CMD ["bash"]


FROM ros-humble-dependencies AS ros-humble-liosam-dependencies

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       git \
       libeigen3-dev \
       libopencv-dev \
       libpcl-dev \
       python3-colcon-common-extensions \
       software-properties-common \
       ros-humble-cv-bridge \
       ros-humble-pcl-conversions \
       ros-humble-pcl-msgs \
       ros-humble-tf2-eigen \
       ros-humble-tf2-geometry-msgs \
       ros-humble-tf2-sensor-msgs \
       ros-humble-tf2-ros \
       ros-humble-visualization-msgs \
       ros-humble-xacro \
    && add-apt-repository -y ppa:borglab/gtsam-release-4.1 \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       libgtsam-dev \
       libgtsam-unstable-dev \
    && rm -rf /var/lib/apt/lists/*


FROM ros-humble-liosam-dependencies AS ros-humble-liosam

ARG CMAKE_BUILD_PARALLEL_LEVEL=4
ARG LIO_SAM_REPOSITORY=https://github.com/TixiaoShan/LIO-SAM.git
ARG LIO_SAM_COMMIT=08af3f32f01725372d4269838dc44c19c6d9e76b

WORKDIR /opt/lio_sam_ws/src
RUN git -c http.version=HTTP/1.1 clone --branch ros2 --single-branch "${LIO_SAM_REPOSITORY}" lio_sam \
    && cd lio_sam \
    && git checkout --detach "${LIO_SAM_COMMIT}" \
    && test "$(git rev-parse HEAD)" = "${LIO_SAM_COMMIT}"

COPY software/third_party/patches/lio_sam/0001-reliable-qos-and-pipeline-counters.patch /tmp/lio_sam.patch
RUN cd /opt/lio_sam_ws/src/lio_sam \
    && git apply --check /tmp/lio_sam.patch \
    && git apply /tmp/lio_sam.patch \
    && rm /tmp/lio_sam.patch

WORKDIR /opt/lio_sam_ws
RUN source /opt/ros/humble/setup.bash \
    && source /opt/drone_tools_ws/install/setup.bash \
    && CMAKE_BUILD_PARALLEL_LEVEL="${CMAKE_BUILD_PARALLEL_LEVEL}" colcon build \
       --merge-install \
       --cmake-args -DCMAKE_BUILD_TYPE=Release \
    && rm -rf build log

ENV AMENT_PREFIX_PATH=/opt/lio_sam_ws/install:/opt/drone_tools_ws/install
ENV LD_LIBRARY_PATH=/opt/lio_sam_ws/install/lib:/opt/drone_tools_ws/install/lib:/usr/local/lib

COPY --from=ros-humble-core /usr/local/bin/drone-agricole-tools /usr/local/bin/drone-agricole-tools

LABEL org.opencontainers.image.title="Drone Agricole - LIO-SAM ROS 2 Humble" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.source="https://github.com/TixiaoShan/LIO-SAM" \
      org.opencontainers.image.revision="08af3f32f01725372d4269838dc44c19c6d9e76b"

WORKDIR /workspace
CMD ["bash"]


FROM ros-humble-liosam AS ros-humble-qt-dashboard

ARG CMAKE_BUILD_PARALLEL_LEVEL=2

COPY --from=ros-humble-fastlio2 /opt/fast_lio_ws/install /opt/fast_lio_ws/install
COPY --from=ros-humble-pointlio /opt/point_lio_ws/install /opt/point_lio_ws/install

COPY CMakeLists.txt /opt/drone_agricole_src/CMakeLists.txt
COPY software/cpp /opt/drone_agricole_src/software/cpp
RUN source /opt/ros/humble/setup.bash \
    && source /opt/drone_tools_ws/install/setup.bash \
    && source /opt/fast_lio_ws/install/setup.bash \
    && source /opt/point_lio_ws/install/setup.bash \
    && source /opt/lio_sam_ws/install/setup.bash \
    && cmake -S /opt/drone_agricole_src -B /opt/drone_agricole_build -G Ninja \
       -DCMAKE_BUILD_TYPE=Release \
       -DCMAKE_INSTALL_PREFIX=/usr/local \
       -DDRONE_AGRICOLE_BUILD_TESTS=OFF \
       -DDRONE_AGRICOLE_WITH_ROS2=ON \
    && cmake --build /opt/drone_agricole_build --parallel "${CMAKE_BUILD_PARALLEL_LEVEL}" \
    && cmake --install /opt/drone_agricole_build \
    && rm -rf /opt/drone_agricole_build /opt/drone_agricole_src

ENV AMENT_PREFIX_PATH=/opt/lio_sam_ws/install:/opt/point_lio_ws/install:/opt/fast_lio_ws/install:/opt/drone_tools_ws/install
ENV LD_LIBRARY_PATH=/opt/lio_sam_ws/install/lib:/opt/point_lio_ws/install/lib:/opt/fast_lio_ws/install/lib:/opt/drone_tools_ws/install/lib:/usr/local/lib

LABEL org.opencontainers.image.title="Drone Agricole - Qt 6 desktop dashboard and LIO runtime" \
      org.opencontainers.image.version="1.0.0"

WORKDIR /workspace
CMD ["bash"]


FROM ros:jazzy-ros-base-noble AS ros-jazzy-sim

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       python3-colcon-common-extensions \
       ros-jazzy-demo-nodes-cpp \
       ros-jazzy-ros-gz-bridge \
       ros-jazzy-rosbag2 \
       ros-jazzy-rosbag2-storage-mcap \
    && rm -rf /var/lib/apt/lists/*

LABEL org.opencontainers.image.title="Drone Agricole - ROS 2 Jazzy simulation base" \
      org.opencontainers.image.version="0.1.0"

WORKDIR /workspace
CMD ["bash"]


FROM ros-jazzy-sim AS ros-jazzy-px4

ARG MICRO_XRCE_DDS_AGENT_REPOSITORY=https://github.com/eProsima/Micro-XRCE-DDS-Agent.git
ARG MICRO_XRCE_DDS_AGENT_COMMIT=73622810d984349b80bbac0ef55fc0b694d62222
ARG PX4_MSGS_REPOSITORY=https://github.com/PX4/px4_msgs.git
ARG PX4_MSGS_COMMIT=598c7aad7b2386f9406ebd2a2f841619fddc3c78

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       cmake \
       git \
       qt6-base-dev \
       qt6-base-dev-tools \
       ros-jazzy-ament-cmake-gtest \
       ros-jazzy-diagnostic-msgs \
       ros-jazzy-geometry-msgs \
       ros-jazzy-nav-msgs \
       ros-jazzy-rosidl-default-generators \
       ros-jazzy-tf2-ros \
    && rm -rf /var/lib/apt/lists/*

# PX4 1.18 utilise le protocole uXRCE-DDS v2 et requiert l'Agent 2.4.3.
# Le dépôt et ses sous-modules sont tous figés par commit.
WORKDIR /opt
RUN git -c http.version=HTTP/1.1 clone --recursive "${MICRO_XRCE_DDS_AGENT_REPOSITORY}" Micro-XRCE-DDS-Agent \
    && cd Micro-XRCE-DDS-Agent \
    && git checkout --detach "${MICRO_XRCE_DDS_AGENT_COMMIT}" \
    && git submodule update --init --recursive \
    && test "$(git rev-parse HEAD)" = "${MICRO_XRCE_DDS_AGENT_COMMIT}" \
    && cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build --parallel "$(nproc)" \
    && cmake --install build \
    && ldconfig \
    && rm -rf build .git

WORKDIR /opt/px4_ros_ws/src
RUN git -c http.version=HTTP/1.1 clone --branch release/1.18 --single-branch "${PX4_MSGS_REPOSITORY}" px4_msgs \
    && cd px4_msgs \
    && git checkout --detach "${PX4_MSGS_COMMIT}" \
    && test "$(git rev-parse HEAD)" = "${PX4_MSGS_COMMIT}" \
    && rm -rf .git

WORKDIR /opt/px4_ros_ws
RUN source /opt/ros/jazzy/setup.bash \
    && colcon build \
       --merge-install \
       --packages-select px4_msgs \
       --cmake-args -DCMAKE_BUILD_TYPE=Release \
    && rm -rf build log

# Le paquet projet est construit dans une couche séparée : une modification
# du pont ne régénère donc pas les 64 interfaces PX4.
COPY software/src/drone_agricole_px4_bridge /opt/px4_ros_ws/src/drone_agricole_px4_bridge
RUN source /opt/ros/jazzy/setup.bash \
    && source /opt/px4_ros_ws/install/setup.bash \
    && colcon build \
       --merge-install \
       --packages-select drone_agricole_px4_bridge \
       --cmake-args -DCMAKE_BUILD_TYPE=Release \
    && colcon test --merge-install --packages-select drone_agricole_px4_bridge \
       --event-handlers console_direct+ \
    && colcon test-result --all --verbose \
    && rm -rf build log

ENV AMENT_PREFIX_PATH=/opt/px4_ros_ws/install
ENV LD_LIBRARY_PATH=/opt/px4_ros_ws/install/lib:/usr/local/lib

LABEL org.opencontainers.image.title="Drone Agricole - PX4 ROS 2 bridge" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.revision.px4_msgs="598c7aad7b2386f9406ebd2a2f841619fddc3c78" \
      org.opencontainers.image.revision.micro_xrce_agent="73622810d984349b80bbac0ef55fc0b694d62222"

WORKDIR /workspace
CMD ["bash"]
