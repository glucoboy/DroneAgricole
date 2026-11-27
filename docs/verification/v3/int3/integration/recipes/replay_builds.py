import concurrent.futures
import datetime
import json
import os
from pathlib import Path
import subprocess

root = Path.cwd()
out = root / ".runtime/b"
logs = out / "logs"
logs.mkdir(exist_ok=True)
ucrt = Path("C:/msys64/ucrt64")
bin_dir = ucrt / "bin"
freecad = Path("C:/Program Files/FreeCAD 1.1/bin/python.exe")
python = bin_dir / "python.exe"
cmake = bin_dir / "cmake.exe"
ctest = bin_dir / "ctest.exe"
env = os.environ.copy()
env.update(PATH=str(bin_dir) + ";" + env["PATH"], QT_QPA_PLATFORM="offscreen",
           PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def run(name, args):
    started = utc()
    argv = [str(part) for part in args]
    print(f"{started} {name}", flush=True)
    with (logs / f"{name}.log").open("wb") as log:
        result = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, env=env, check=False)
    record = dict(argv=argv, cwd=str(root), started_utc=started, finished_utc=utc(),
                  exit_code=result.returncode)
    (logs / f"{name}.command.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"{record['finished_utc']} {name} -> {result.returncode}", flush=True)
    return result.returncode

common = [
    "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_CXX_STANDARD=17",
    "-DCMAKE_CXX_STANDARD_REQUIRED=ON", "-DCMAKE_CXX_EXTENSIONS=OFF",
    f"-DCMAKE_CXX_COMPILER={bin_dir / 'g++.exe'}", f"-DCMAKE_MAKE_PROGRAM={bin_dir / 'ninja.exe'}",
    f"-DCMAKE_PREFIX_PATH={ucrt}", f"-DPython3_EXECUTABLE={python}",
    "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
]
authority = [
    f"-DL5_FREECAD_PYTHON={freecad}", f"-DL5_T0_VALIDATOR={out / 't0/cartographe-evidence.exe'}",
    "-DL5_A5_PHYSICAL_TRUST_SHA256=",
]
deps = [
    f"-DL5_L1_EXECUTABLE={out / 'l3/research/technical_research_core.exe'}",
    f"-DL5_L3_EXECUTABLE={out / 'l3/architecture_decision_core.exe'}",
    f"-DL5_L4_EXECUTABLE={out / 'l4/validation_core.exe'}",
    f"-DL5_A5_OPENSSL_EXECUTABLE={bin_dir / 'openssl.exe'}",
    f"-DOPENSSL_ROOT_DIR={ucrt}",
]

def build(name, source, jobs=4, options=(), targets=()):
    path = out / name
    if run(f"configure-{name}", [cmake, "-S", source, "-B", path, *common, *options]):
        return False
    target_args = ["--target", *targets] if targets else []
    return not run(f"build-{name}", [cmake, "--build", path, "--parallel", jobs, *target_args])

def test(name, log=None, filters=()):
    log = log or f"ctest-{name}"
    result = run(log, [ctest, "--test-dir", out / name, "--no-tests=error", "--output-on-failure",
                       "--output-junit", logs / f"{log}.xml", "-V", *filters])
    return result == 0

def main():
    if run("checkout", ["git", "status", "--porcelain=v1", "--branch"]):
        return 1
    if run("revision", ["git", "show", "-s", "--format=%H %P", "HEAD"]):
        return 1
    t0 = build("t0", "simulation", jobs=4)
    t0_tests = t0 and test("t0", filters=["-R", "^cartographe_(sitl_)?t0_contracts$"])
    if t0 and not t0_tests:
        t0_tests = test("t0", "ctest-t0-isolated-retry", ["-R", "^cartographe_(sitl_)?t0_contracts$"])
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        pending = {
            "l3": pool.submit(build, "l3", "architecture_decision_engine", 3),
            "l4": pool.submit(build, "l4", "validation_engine", 3),
            "l5": pool.submit(build, "l5", "convergence_manager", 4,
                              authority + deps + ["-DL5_A6_FAULT_INJECTION=OFF"]),
            "l5-faults": pool.submit(build, "l5-faults", "convergence_manager", 3,
                                     authority + deps + ["-DL5_A6_FAULT_INJECTION=ON", "-DBUILD_TESTING=ON"],
                                     ["convergence_core"]),
            "l5-no-crypto": pool.submit(build, "l5-no-crypto", "convergence_manager", 3,
                                         authority + deps + ["-DL5_A6_FAULT_INJECTION=OFF",
                                                              "-DCMAKE_DISABLE_FIND_PACKAGE_OpenSSL=TRUE"],
                                         ["convergence_core"]),
        }
        built = {name: future.result() for name, future in pending.items()}
        tests = {name: pool.submit(test, name) for name in ("l3", "l4", "l5") if built[name]}
        passed = {name: future.result() for name, future in tests.items()}
    if t0:
        test("t0", "ctest-historical-model", ["-R", "^cartographe_model_generation$"])
    return 0 if t0_tests and all(built.values()) and all(passed.values()) else 1

if __name__ == "__main__":
    raise SystemExit(main())
