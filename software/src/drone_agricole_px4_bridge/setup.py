from setuptools import find_packages, setup


package_name = "drone_agricole_px4_bridge"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Projet Drone Agricole",
    maintainer_email="devnull@example.invalid",
    description="Pont d'état et essais offboard sécurisés entre PX4 SITL et ROS 2.",
    license="Proprietary",
    entry_points={
        "console_scripts": [
            "state_bridge = drone_agricole_px4_bridge.state_bridge:main",
            "offboard_test = drone_agricole_px4_bridge.offboard_test:main",
        ],
    },
)
