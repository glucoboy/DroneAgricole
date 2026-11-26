import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

root = Path.cwd()
checkout = (root / ".runtime/i21a").resolve()
run = checkout / ".runtime/run"
binary = run / "l3/research/technical_research_core.exe"
sys.path.insert(0, str(checkout / "tools"))
from replay_sealed_test import l1_command

relative_route = "hardware/mecanique/cartographe/verification/routes_prototype.json"
catalog_relative = "docs/electromechanical_v2/L1_CARTOGRAPHE.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


results = {}
with TemporaryDirectory(prefix="int21-f16-") as temporary:
    private = Path(temporary)
    fixture = private / "fixture"
    l1_command(checkout, fixture)
    route = fixture / relative_route
    historical = route.read_bytes()
    raw = (checkout / relative_route).read_bytes()
    assert raw == historical.replace(b"\r\n", b"\n") and raw != historical
    catalog = fixture / catalog_relative
    cache_count = 0
    for label, content in (("checkout_lf", raw), ("sealed_crlf", historical)):
        route.write_bytes(content)
        result = {"route_sha256": sha(content), "route_bytes": len(content), "passes": []}
        for cwd in (checkout, private):
            observations = {}
            for issue in ("F16-AXIS-ACTIVE", "F16-MOUNTED-BEND-RADIUS"):
                cache_count += 1
                command = [str(binary), "submit", "--root", str(fixture), "--store",
                           str(private / f"store-{cache_count}"), "--catalog", str(catalog), "--issue", issue]
                process = subprocess.run(command, cwd=cwd, capture_output=True, check=True, timeout=30)
                report = json.loads(process.stdout)
                observations[issue] = {"outcome": report["outcome"], "value": report.get("value"),
                                       "source_hash_mismatch": "SOURCE_HASH_MISMATCH" in process.stdout.decode("utf-8"),
                                       "network": report.get("network"), "exit_code": process.returncode}
                if issue == "F16-AXIS-ACTIVE":
                    assert observations[issue]["source_hash_mismatch"] == (label == "checkout_lf")
                    assert report["outcome"] == ("UNKNOWN" if label == "checkout_lf" else "RESOLVED")
                    if label == "sealed_crlf":
                        assert abs(report["value"]["value"] - 425.17384217864503) < 1e-12
                else:
                    assert report["outcome"] == "UNKNOWN"
            result["passes"].append({"cwd": "checkout" if cwd == checkout else "secondaire",
                                     "issues": observations})
        assert result["passes"][0]["issues"] == result["passes"][1]["issues"]
        results[label] = result
    payload = {"schema": "v3.int21.l1-control/1", "status": "PASS",
               "binary_sha256": sha(binary.read_bytes()), "catalog_sha256": sha(catalog.read_bytes()),
               "argv_model": [str(binary), "submit", "--root", "<copie-privée>", "--store", "<cache-neuf>",
                              "--catalog", f"<copie-privée>/{catalog_relative}", "--issue", "<issue-id>"],
               "fixture_network": "OFFLINE_DEFAULT", "results": results}
(run / "l1-experiment.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                                       encoding="utf-8", newline="\n")
print("L1 PASS : le diagnostic suit les octets de F16 ; deux CWD ; rayon monté UNKNOWN.")
