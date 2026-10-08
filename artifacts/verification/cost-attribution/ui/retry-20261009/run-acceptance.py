import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('acceptance','tools/tcp/verify_workload_dashboard.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.OUT=Path.cwd()/'artifacts/verification/cost-attribution/ui/retry-20261009'/m.MODE
m.SHOTS=Path.cwd()/'artifacts/screenshots/cost-attribution-regression'
m.SESSION='b-retry-'+m.MODE
r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(m))
raise SystemExit(not r.wasSuccessful())
