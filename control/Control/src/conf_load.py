import clparams
import sys
from workload import wtimes_meta
from workload import timeutil

LOAD_SOURCE = 'times' # options: sonar, times, times_MKI
SCRAMBLER = 0 # 0 = default 1:1 scrambling
TIMES_SELECTED_MIX = wtimes_meta.mixmkII # selecht workload in times
RAMP_UP_DOWN = timeutil.minu(10)
SETUP = timeutil.minu(10)

# Override settings by command line
clparams.load_parameters(sys.modules[__name__])