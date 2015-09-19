'''
Launches multiple simulations (simulation.py) in parallel. Each simulation is configured
using command line arguments. Configurations are generated based on factor matrices. 
A factor matrix is specified by extending CommandBuilder and implementing all required methods.  

Parameters: 
[output file name] # Is written 

'''

import itertools
import numpy as np
import subprocess
import sys
import configuration

####################
# CONFIGURATION   ##
PARALLELITY = 5
RUNS = 1
####################

class CommandBuilder(object):
    def __build_level_matrix_alt(self, factor_levels_map, center_level):
        t = list(itertools.product(*[range(len(factor_levels_map[f][1])) for f in xrange(len(factor_levels_map))]))
        if center_level:
            c = np.array([2 for _ in xrange(len(factor_levels_map))])
            t.append(c)
        t = np.transpose(np.array(t))
        return t
    
    def build(self, filename, center_level):
        # Which factor map to use
        factor_levels_map = self.get_factors()
        level_matrix = self.__build_level_matrix_alt(factor_levels_map, center_level)
        print level_matrix 
        
        # List of commands to build
        commands = []
        
        # For all runs 
        for run in xrange(0, RUNS):
            for col in xrange(len(level_matrix[0])):
                # Treatment params (parameter) base             
                treatment_params = []
                treatment_params_map = {}
                
                # Build treatment params
                for row in xrange(len(factor_levels_map)):
                    factor_name = factor_levels_map[row][0]
                    level_index = level_matrix[row][col]
                    factor_value = factor_levels_map[row][1][level_index]
                
                    # Add treatment params
                    treatment_params.append('-' + factor_name)
                    treatment_params.append(str(factor_value))
                    treatment_params_map[factor_name] = factor_value
                        
                # Add static params (might depend already set treatment_params)
                treatment_params.extend(self.fill_static_params(run, treatment_params_map))    
                        
                # Build execution command
                execution_command = ["python", self.get_script_name(), '-f', filename, '-RUN', str(run)]
                execution_command.extend(treatment_params)
                print 'Command: %s' % execution_command
                
                # Add command to list
                commands.append(execution_command)
            
            
        print 'Total number of commands: %i' % len(commands)
        return commands

class KMandTControllerCB(CommandBuilder):
    '''
    Used for 2k full factorial design to find optimal settings
    for the T and KM controllers in a MKI environment. 
    '''
    
    # TController optimal setting used for benchmark
    __factors = [
    ('THRESHOLD_OVERLOAD', (90, 95)),
    ('THRESHOLD_UNDERLOAD', (60, 80)),
    ('ALPHA', (0.05, 0.1)),
    ('K_VALUE', (50, 200)),
    ('INTERVAL', (60, 900)),
    ('BOTTOM_PERCENTILE', (0.1, 0.4)),
    ]
    
    def get_script_name(self):
        return 'src/balancer/simulation.py'
    
    def fill_static_params(self, run, treatment_params_map):
        return ['-SCRAMBLER', str(run)]
        
    def get_factors(self):
        return KMandTControllerCB.__factors   
   
   
class TControllerCB(CommandBuilder):
    '''
    Run simulations with the T controller and optimal settings to
    estimate its performance for a large set of time series in a MKI environment. 
    '''
    
    # TController optimal setting used for benchmark
    __factors = [
    ('THRESHOLD_OVERLOAD', (90,)),
    ('THRESHOLD_UNDERLOAD', (25,)),
    ('ALPHA', (0.05,)),
    ('K_VALUE', (170,)),
    ('INTERVAL', (400,)),
    ]
    
    def get_script_name(self):
        return 'src/balancer/simulation.py'
    
    def fill_static_params(self, run, treatment_params_map):
        return ['-SCRAMBLER', str(run)]
        
    def get_factors(self):
        return TControllerCB.__factors
    

class KMControllerCB(CommandBuilder):
    '''
    Run simulations with the KM controller and optimal settings to
    estimate its performance for a large set of time series in a MKI environment. 
    '''
    
    # KMController optimal setting used for benchmark
    __factors = [
      ('THRESHOLD_OVERLOAD', (95,)),
      ('THRESHOLD_UNDERLOAD', (27,)),
      ('K_VALUE', (65,)),
      ('M_VALUE', (65,)),
      ('INTERVAL', (750,)),
      ]
    
    def get_script_name(self):
        return 'src/balancer/simulation.py'
    
    def fill_static_params(self, run, treatment_params_map):
        return ['-SCRAMBLER', str(run)]
            
    def get_factors(self):
        return KMControllerCB.__factors


class InitialPlacementCB(CommandBuilder):
    '''
    Used to find out if the choice of an initial placmenet strategy
    has an impact on the average server cound and migrations of different 
    reactive controllers in MKI environments. 
    '''
    __factors = [
                 ('STRATEGY_INITIAL_PLACEMENT', ('round', 'firstFitVector', 'dotProduct', 'ssapv', 'firstFit')),
                 ('INITIAL_DOMAINS', (10, 18, 50))
                 ]
    
    def get_script_name(self):
        return 'src/balancer/simulation.py'
   
    def fill_static_params(self, run, treatment_params_map):
        return ['-SCRAMBLER', str(run)]
    
    def get_factors(self):
        return InitialPlacementCB.__factors
   
   
class PlacementLowerBoundSensitivityCB(CommandBuilder):
    '''
    Calculates the lower bound server demand for a set of 2k full
    factorial designed schedule configurations and scheudle instances in a MKII 
    environment. 
    
    The goal is to find out which schedule configuration factors or/and 
    if the placement strategy have a significant impact on the competitive value 
    calculated by (heuristic peek server demand / optimal peek server demand).   
    '''
    
    __factors = []
    
    def __init__(self):
        from schedule import schedule_builder
        conf = schedule_builder.ScheduleConfigurationsSensitivity()
        indices = conf.get_all_schedule_ids()
        PlacementLowerBoundSensitivityCB.__factors.append(('SCHEDULE_ID', indices))
    
    def get_script_name(self):
        return 'src/ipmodels/min_reservation.py'
    
    def fill_static_params(self, run, treatment_params_map):
        # Determine schedule domain size set and set it
        schedule = treatment_params_map['SCHEDULE_ID']
        from schedule import schedule_builder
        schedule = schedule_builder.load_schedule(schedule)
        return ['-DOMAIN_SIZES_SET', str(schedule.get_domain_size_set())]
    
    def get_factors(self):
        return PlacementLowerBoundSensitivityCB.__factors
    
   
class PlacementOptimalSensitivityCB(CommandBuilder):
    '''
    Calculates the optimal peek server demand for a set of 2k full
    factorial designed schedule configurations and scheudle instances in a MKII 
    environment. 
    
    The goal is to find out which schedule configuration factors or/and 
    if the placement strategy have a significant impact on the competitive value 
    calculated by (heuristic peek server demand / optimal peek server demand).   
    '''
    
    __factors = []
    
    def __init__(self):
        from schedule import schedule_builder
        conf = schedule_builder.ScheduleConfigurationsSensitivity()
        indices = conf.get_all_schedule_ids()
        PlacementOptimalSensitivityCB.__factors.append(('SCHEDULE_ID', indices))
    
    def get_script_name(self):
        return 'src/ipmodels/align_schedule.py'
    
    def fill_static_params(self, run, treatment_params_map):
        # Determine schedule domain size set and set it
        schedule = treatment_params_map['SCHEDULE_ID']
        from schedule import schedule_builder
        schedule = schedule_builder.load_schedule(schedule)
        return ['-DOMAIN_SIZES_SET', str(schedule.get_domain_size_set())]
    
    def get_factors(self):
        return PlacementOptimalSensitivityCB.__factors
   
class ReallocationPlacementInteractionCB(CommandBuilder):
    '''
    Used to compare different combinations of reallocation AND placement strategies.
    For reallocation, kmcontrol and DSAPP are experimented together with each of the
    following placement strategies: firstFit, worstFit, random, dotProduct
    
    The goal is to find out which combination is preferable in terms of
        1. migrations triggered
        2. servers used
    
    We also experiment without using any reallocation strategies. With and without reallocation
    strategies, we can determine which effect a combination of reallocation can bring.  
    '''
    
    __factors = [
                 ('STRATEGY_PLACEMENT', ('firstFit', 'firstFitDemand', 'bestFit', 'bestFitDemand', 
                                         'worstFit', 'worstFitDemand', 
                                         'l2', 'l2Demand', 'random')),
                 ('STRATEGY_REALLOCATION', ('dsapp', 'kmcontrol', 'None', 'tcontrol'))
                ]

#    __factors = [
#                 ('STRATEGY_PLACEMENT', ('worstFitDemand', )),
#                 ('STRATEGY_REALLOCATION', ('dsapp', ))
#                ]
    
    def __init__(self):
        from schedule import schedule_builder
        conf = schedule_builder.ScheduleConfigurationsProduction()
        indices = conf.get_all_schedule_ids()
        ReallocationPlacementInteractionCB.__factors.append(('SCHEDULE_ID', indices))
    
    def fill_static_params(self, run, treatment_params_map):
        # Determine schedule domain size set and set it
        schedule = treatment_params_map['SCHEDULE_ID']
        from schedule import schedule_builder
        schedule = schedule_builder.load_schedule(schedule)
        return ['-DOMAIN_SIZES_SET', str(schedule.get_domain_size_set())]
    
    def get_script_name(self):
        return 'src/balancer/simulation.py'
    
    def get_factors(self):
        return ReallocationPlacementInteractionCB.__factors
    
   
class PlacementHeuristicSensitivityCB(CommandBuilder):
    '''
    Used to compare differnet placement strategies (heuristics) for a set of 2k full
    factorial designed schedule configurations and scheudle instances in a MKII 
    environment. 
    
    The goal is to find out which schedule configuration factors or/and 
    if the placement strategy have a significant impact on the competitive value 
    calculated by (heuristic peek server demand / optimal peek server demand).   
    '''
    
    __factors = [
                 ('STRATEGY_PLACEMENT', ('firstFit', 'bestFit', 'dotProduct', 'nextFit', 'harmonic')),
                ]
    
    def __init__(self):
        from schedule import schedule_builder
        conf = schedule_builder.ScheduleConfigurationsSensitivity()
        indices = conf.get_all_schedule_ids()
        PlacementHeuristicSensitivityCB.__factors.append(('SCHEDULE_ID', indices))
    
    def get_script_name(self):
        return 'src/balancer/simulation.py'
    
    def fill_static_params(self, run, treatment_params_map):
        # Determine schedule domain size set and set it
        schedule = treatment_params_map['SCHEDULE_ID']
        from schedule import schedule_builder
        schedule = schedule_builder.load_schedule(schedule)
        return ['-DOMAIN_SIZES_SET', str(schedule.get_domain_size_set())]
            
    def get_factors(self):
        return PlacementHeuristicSensitivityCB.__factors
   
   
   
class PlacementOptimalCB(CommandBuilder):
    '''
    Calculates the optimal peek server demand for all schedule instances
    of schedule configurations used to run MKII experiments. 
    '''
    
    __factors = []
    
    def __init__(self):
        ids = []
        ids.extend(range(2000, 2005))
        ids.extend(range(2100, 2105))
        ids.extend(range(2200, 2205))
        ids.extend(range(2300, 2305))
        PlacementOptimalCB.__factors.append(('SCHEDULE_ID', ids))
    
    def get_script_name(self):
        return 'src/ipmodels/align_schedule.py'
    
    def fill_static_params(self, run, treatment_params_map):
        # Determine schedule domain size set and set it
        schedule = treatment_params_map['SCHEDULE_ID']
        from schedule import schedule_builder
        schedule = schedule_builder.load_schedule(schedule)
        return ['-DOMAIN_SIZES_SET', str(schedule.get_domain_size_set())]
    
    def get_factors(self):
        return PlacementOptimalCB.__factors
    
   
class PlacementHeuristicCB(CommandBuilder):
    '''
    Simulates the peek server demand of placement heuristics for all schedule instances
    of schedule configurations used to run MKII experiments. 
    '''
    
    __factors = [
                 ('STRATEGY_PLACEMENT', ('firstFit', 'bestFit', 'dotProduct'))
                ]
    
    def __init__(self):
        ids = []
        ids.extend(range(2000, 2005))
        ids.extend(range(2100, 2105))
        ids.extend(range(2200, 2205))
        ids.extend(range(2300, 2305))
        PlacementHeuristicCB.__factors.append(('SCHEDULE_ID', ids))
    
    def get_script_name(self):
        return 'src/balancer/simulation.py'
    
    def fill_static_params(self, run, treatment_params_map):
        # Determine schedule domain size set and set it
        schedule = treatment_params_map['SCHEDULE_ID']
        from schedule import schedule_builder
        schedule = schedule_builder.load_schedule(schedule)
        return ['-DOMAIN_SIZES_SET', str(schedule.get_domain_size_set())]
            
            
    def get_factors(self):
        return PlacementHeuristicCB.__factors
    
       
def spawn(command):
    return subprocess.call(command)

def clear_file(filename, extension):
    try:
        filename = configuration.path(filename, extension)
        print 'Clearing output file: %s' % (filename)
        
        with open(filename):
            pass
        
        import shutil
        print 'Creating backup of current results file'
        shutil.copyfile(filename, '%s.bak' % filename)
        
        print 'Removing existing results file'
        import os
        os.remove(filename)
    except:
        pass   

if __name__ == '__main__':
    # Read the filename from the command line arguments
    filename = 'sloop'
    if len(sys.argv) != 2:
        print 'Simulation loop expects exactly one argument - target file name'
        sys.exit(1)
    else:
        filename = sys.argv[1]
    
    # Remove output file to get clean results
    clear_file(filename, 'csv')
    clear_file(filename, 'err')
    
    
    # Generate all commands to execute
    commands = None
    
    #########################################################
    ## SET COMMAND BUILDER ##################################
    #########################################################
    # MKI environments
    # commands = KMandTControllerCB().build(filename, False) # KM and T Controller 2k full factorial simulations
    # commands = TControllerCB().build(filename, False) # T Controller optimal settings simulations
    # commands = KMControllerCB().build(filename, False) # KM Controller optimal settings simulations
    # commands = InitialPlacementCB().build(filename, False) # Effect of initial placement strategies on KM controller performance simulations
    #
    # MKII environments
    # commands = PlacementOptimalSensitivityCB().build(filename, False) # Optimal peek server demand for 2k full factorial schedule configurations
    # commands = PlacementHeuristicSensitivityCB().build(filename, False)  # Simulated heuristic peek server demand for 2k full factorial schedule configurations
    commands = ReallocationPlacementInteractionCB().build(filename, False)  # Tests all combinations of placement and re-allocating controllers for all production schedules to find which combination performs best
    # commands = PlacementOptimalCB().build(filename, False) # Optimal peek server demand for schedule configurations used by MK II experiments
    # commands = PlacementHeuristicCB().build(filename, False) # Simulated heuristic peek server demand for schedule configurations used by MK II experiments
    #########################################################
    
    # Run all commands at maximum parallelity
    import multiprocessing
    pool = multiprocessing.Pool(processes=PARALLELITY)
    print pool.map(spawn, commands)
    
    # Exit statement
    print 'Exit'


