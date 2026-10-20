"""Deploy only on the private test app; never use as the student entry point."""
import os
from pathlib import Path
import runpy

previous = os.environ.get('MAY_BLOOM_DEPLOYMENT')
os.environ['MAY_BLOOM_DEPLOYMENT'] = 'staging'
try:
    runpy.run_path(str(Path(__file__).with_name('advancedplus.app.py')), run_name='__main__')
finally:
    if previous is None:
        os.environ.pop('MAY_BLOOM_DEPLOYMENT', None)
    else:
        os.environ['MAY_BLOOM_DEPLOYMENT'] = previous
