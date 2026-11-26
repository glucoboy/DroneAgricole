from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path.cwd() / "convergence_manager/tests"))
from test_v3_a5_authority import ROOT, AdmissionFixture, SigningFixtures, check, save

normal, no_crypto, openssl, out = (Path(arg).resolve() for arg in sys.argv[1:])
with TemporaryDirectory(prefix="int2-a5-compare-", dir=ROOT / ".runtime") as private:
    base = Path(private)
    fixture = AdmissionFixture(no_crypto, base / "fixture", SigningFixtures(openssl, base))
    missing = check(fixture.run("crypto-unavailable"), "REVIEW_NOT_CONFIGURED")
    fixture.core = normal
    control = check(fixture.run("crypto-control"))
    assert missing["request_sha256"] == control["request_sha256"]
    save(out, {"without_crypto": missing, "with_crypto": control})
print("Même demande signée : refus sans OpenSSL, préadmission TEST_ONLY avec OpenSSL.")

