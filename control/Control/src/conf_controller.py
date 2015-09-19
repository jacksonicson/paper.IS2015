import clparams
import sys

######################
# CONFIGURATION     ##
######################
EXIT_AFTER_INITIAL_PLACEMENT = False

STRATEGY_INITIAL_PLACEMENT = 'round'
STRATEGY_REALLOCATION = 'kmcontrol'
STRATEGY_PLACEMENT = 'worstFitDemand'
######################

# Load parameters from command line
clparams.load_parameters(sys.modules[__name__])

'''
Initial Placement Strategy
- round (Round robin allocation to all available servers)
- firstFit (First fit based on CPU and memory)
- firstFitVector (First fit vector based on time series for CPU load and single value for memory load)
- dotProduct (Dot product on time series for CPU load and single value for memory load) 
- cosine (Cosine on time series for CPU load and single value for memory load) 
- ssapv (SSAPv for time series on CPU load and single value for memory load)
- dsap (DSAP with re-allocations)
- file (CSV file containing the initial placement)
'''

'''
Reallocation Strategies:
- kmcontrol
- tcontrol
- dsap
- dsapp
- none
'''

'''
Placement Strategies: 
- firstNode (all domains on node with index 0)
- round (allocated domains in a round robin approach to the nodes) 
- random (allocate domains to nodes randomly)

- firstFit (allocate domain to node that has enough CPU and MEM capacity)
- firstFitDemand (allocate domain to a node based on its current CPU load and 100% estimated VM load)
 
- bestFit (allocate domain to node that has not only enough CPU and MEM, but also dominates the others)
- bestFitDemand (allocate domain to a node based on its current CPU load and 100% estimated VM load)

- worstFit (the opposite of bestFit)
- worstFitDemand (allocate domain to a node based on its current CPU load and 100% estimated VM load) 

- nextFit (allocate domains on a node until node is full, then move to the next free node)
- nextFitDemand (allocate domain to a node based on its current CPU load and 100% estimated VM load)

- dotProduct (allocate domain with dot product heuristic with CPU and MEM in vector)
- dotProductDemand (allocate domain to a node based on its current CPU load and 100% estimated VM load)

- l2 (allocate domain with L2 heuristic with CPU and MEM in vector)
- l2Demand (allocate domain to a node based on its current CPU load and 100% estimated VM load)
 
- harmonic (each node is assigned a harmonic interval range for CPU cores there VMs get assigned)
- ssap
- static
'''

def is_start_initial_placement():
    if STRATEGY_INITIAL_PLACEMENT is None:
        return False
    if STRATEGY_INITIAL_PLACEMENT == 'None':
        return False
    
    return True

def is_start_reallocation():
    if STRATEGY_REALLOCATION is None:
        return False
    if STRATEGY_REALLOCATION == 'None':
        return False
    
    return True

def is_start_placement():
    if STRATEGY_PLACEMENT is None:
        return False
    if STRATEGY_PLACEMENT == 'None':
        return False
    
    return True
    