from balancer import strategy_km
from balancer.model import types
from scipy import stats
import numpy as np
import sys
import clparams

######################
# CONFIGURATION     ##
######################

ALPHA = 0.05
K_VALUE = 170
THRESHOLD_OVERLOAD = 90
THRESHOLD_UNDERLOAD = 25
INTERVAL = 400

# Load parameters from command ilne
clparams.load_parameters(sys.modules[__name__]) 
print '##############################'

class TTestStrategy(strategy_km.Strategy):
    
    def __init__(self, scoreboard, pump, model):
        super(TTestStrategy, self).__init__(scoreboard, pump, model)
        
    ############################################
    ## HOTSPOT DETECTOR ########################
    ############################################
    
    
    
    def _detect_hotspots(self):
        '''
        Sets a flag if a node is overloaded or underloaded. Forecasts are used
        to detect hotspots.
        '''
        # Here we find out whether detect hotspot is being called from its subclass or not
        # if not, we will just use the default hosts list. Otherwise, we will use the hosts list
        # without the reserve node
        node_list = []
        if hasattr(self, 'node_list'):
            node_list = self.node_list
        else:
            node_list = self.model.get_hosts(types.NODE)
            
        for node in node_list:
            cpu_loads = node.get_readings()
            cpu_loads = cpu_loads[-K_VALUE:]
            node.underloaded = False
            node.overloaded = False
            
            _, p_value = stats.ttest_1samp(cpu_loads, THRESHOLD_OVERLOAD)
            current_mean = np.mean(cpu_loads, dtype=int)
            if p_value < ALPHA and current_mean >= THRESHOLD_OVERLOAD:
                node.overloaded = True
            else:
                _, p_value = stats.ttest_1samp(cpu_loads, THRESHOLD_UNDERLOAD)
                if p_value < ALPHA and current_mean <= THRESHOLD_UNDERLOAD:
                    node.underloaded = True
