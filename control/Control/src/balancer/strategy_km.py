from balancer import strategy
from balancer.model import types
from logs import sonarlog
import clparams
import conf_nodes
import json
import sys

######################
# # CONFIGURATION    ##
######################
START_WAIT = 120
DEBUG = False

# Old factors
THRESHOLD_OVERLOAD = 95
THRESHOLD_UNDERLOAD = 25
K_VALUE = 65  # sliding windows size
M_VALUE = 50  # m values out of the window k must be above or below the threshold
INTERVAL = 900

# # New factors 0
THRESHOLD_OVERLOAD = 95
THRESHOLD_UNDERLOAD = 30
K_VALUE = 64  # sliding windows size
M_VALUE = 51  # m values out of the window k must be above or below the threshold
INTERVAL = 900

# # New factors 1
THRESHOLD_OVERLOAD = 95
THRESHOLD_UNDERLOAD = 27
K_VALUE = 65  # sliding windows size
M_VALUE = 65  # m values out of the window k must be above or below the threshold
INTERVAL = 750

# Constant
PROACTIVE = False
PERCENTILE = 95.0
######################

# Setup logging
logger = sonarlog.getLogger('controller')

# Load parameters from command ilne
clparams.load_parameters(sys.modules[__name__]) 
print '##############################'

class Strategy(strategy.StrategyBase):
    
    def __init__(self, scoreboard, pump, model):
        super(Strategy, self).__init__(scoreboard, pump, model, INTERVAL, START_WAIT)
        
    def dump(self):
        print 'Dump Sandpiper controller configuration...'
        logger.info('Strategy Configuration: %s' % json.dumps({'name' : 'Sandpiper',
                                                                 'start_wait' : START_WAIT,
                                                                 'interval' : INTERVAL,
                                                                 'threshold_overload' : THRESHOLD_OVERLOAD,
                                                                 'threshold_underload' : THRESHOLD_UNDERLOAD,
                                                                 'percentile' : PERCENTILE,
                                                                 'k_value' :K_VALUE,
                                                                 'm_value' : M_VALUE
                                                                 }))
    
    
    def post_migrate_hook(self, success, domain, node_from, node_to, end_time):
        if success:
            # Release block
            node_from.blocked = end_time
            node_to.blocked = end_time
            
            # Reset CPU consumption: Necessary because the old CPU readings
            # may trigger another migrations as they do not represent the load
            # without the VM
            node_from.flush(50)
            node_to.flush(50)
        else:
            node_from.blocked = end_time
            node_to.blocked = end_time
        
      
    ############################################
    ## HOTSPOT DETECTOR ########################
    ############################################
    
    def _detect_hotspots(self):
        '''
        Sets a flag if a node is overloaded or underloaded. Forecasts are used
        to detect hotspots. 
        '''
        
        for node in self.model.get_hosts(types.NODE):
            # Check past readings
            readings = node.get_readings()
            
            # m out of the k last measurements are used to detect overloads 
            overload = 0
            underload = 0
            for reading in readings[-K_VALUE:]:
                if reading > THRESHOLD_OVERLOAD: overload += 1
                if reading < THRESHOLD_UNDERLOAD: underload += 1

            # Stabilizer
            if PROACTIVE:
                forecast = node.f_t
                overload = forecast > THRESHOLD_OVERLOAD
                underload = forecast < THRESHOLD_UNDERLOAD
            else:
                overload = (overload >= M_VALUE)
                underload = (underload >= M_VALUE)
             
            # Update overload state for the node                          
            node.overloaded = overload
            node.underloaded = underload
            
            
    ############################################
    ## MIGRATION MANAGER #######################
    ############################################
    def _migration_manager(self):
        '''
        Calculates volume for nodes and domains
        Sorts nodes depending on their volume
        '''
        
        # Calculate volumes of each node
        nodes = []
        domains = []
        for node in self.model.get_hosts():
            # Calculate node volume
            volume = 1.0 / max(0.001, float(100.0 - node.percentile_load(PERCENTILE, K_VALUE)) / 100.0)
            node.volume = volume
            
            if node.type == types.NODE:
                # calculate volume size based on node memory size
                node.volume_size = volume / conf_nodes.NODE_MEM 
                nodes.append(node)
            elif node.type == types.DOMAIN:
                # Calculate volume size based on domain memory size
                memory = node.domain_configuration.get_domain_spec().total_memory()
                print memory
                node.volume_size = volume / memory
                domains.append(node)
       
        # Sort nodes to their volume in DECREASING order
        # Multiplication with a big value to shift post comma digits to the front (integer)
        nodes.sort(lambda a, b: int((b.volume - a.volume) * 100000))
        
        # Return sorted list of nodes and domains
        return nodes, domains
        
        
    def __run_migration(self, is_overload_migration, nodes, domains, source_node):
        # Current time
        time_now = self.pump.sim_time()
        
        # Sleep between two migrations on a node
        sleep_time = 60
        
        # Sort domains by their VSR (volume size ratio) value in decreasing order 
        node_domains = []
        node_domains.extend(source_node.domains.values())
        node_domains.sort(lambda a, b: int(b.volume_size - a.volume_size))
        
        # Try to migrate all domains by decreasing VSR value
        for domain in node_domains:
            # Iteration sequence depends on overload or underload
            if is_overload_migration:
                iteration = range(nodes.index(source_node) + 1, len(nodes))[::-1]  # reversed(range(nodes.index(source_node) + 1, len(nodes)))
            else:
                iteration = range(nodes.index(source_node))[::-1]  # range(nodes.index(source_node) - 1)
            
            def find_migration_target(active_nodes_only):
                # Try all active nodes as a migration target
                for target in iteration:
                    # Reference to the target node in the model
                    target = nodes[target]
                    
                    # Skip inactive nodes
                    if active_nodes_only and len(target.domains) == 0:
                        continue
                    
                    # Calculate target memory status
                    target_free_memory = conf_nodes.NODE_MEM
                    for target_domains in target.domains.values():
                        mem = target_domains.domain_configuration.get_domain_spec().total_memory()
                        target_free_memory -= mem
                    
                    # Check validity of target node                
                    test = True
                    domain_cpu_factor = target.cpu_cores / domain.cpu_cores
                    test &= (target.percentile_load(PERCENTILE, K_VALUE) + domain.percentile_load(PERCENTILE, K_VALUE) / domain_cpu_factor) < THRESHOLD_OVERLOAD  # Overload threshold
                    test &= (target_free_memory - domain.domain_configuration.get_domain_spec().total_memory()) > 0
                    test &= (time_now - target.blocked) > sleep_time
                    test &= (time_now - source_node.blocked) > sleep_time
                    
                    # Migration is allowed - do it
                    if test: 
                        print 'Migration: %s from %s to %s' % (domain.name, source_node.name, target.name)
                        self.migrate(domain, source_node, target)
                        
                        if is_overload_migration:
                            print 'OVERLOAD MIG'
                            self.scoreboard.add_overload_migration()
                        
                        # Exit migration function with success
                        return True
                    
                # Exit migration function without success
                return False
                
            # Try migrating to an active target node
            success = False
            success |= find_migration_target(True)
            
            # Try migrating to an all target nodes
            success |= find_migration_target(False)
            
            if not success and is_overload_migration:
                print 'WARN: could not find viable migration target for %s' % (domain.name)

        
    def _migration_trigger(self, nodes, domains):
        ############################################
        ## MIGRATION TRIGGER #######################
        ############################################
        for node in nodes:
            # Dump node information
            if DEBUG: node.dump() 
            
            # If node is overloaded or underloaded trigger
            # a migration
            if node.overloaded:
                self.__run_migration(True, nodes, domains, node)
            elif node.underloaded:
                self.__run_migration(False, nodes, domains, node)
        
    def balance(self):
        self._detect_hotspots()
        nodes, domains = self._migration_manager()
        self._migration_trigger(nodes, domains)
        
