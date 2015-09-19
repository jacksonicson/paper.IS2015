from balancer.model import types
from ipmodels import cbc_dsapp as dsapp
from logs import sonarlog
from migration_queue import MigrationQueue
from workload.timeutil import minu
import conf_nodes
import conf_domains
import json
import numpy as np
import strategy

# Fixed values
START_WAIT = 0  # Data aggregation phase (ALWAYS 0 FOR THIS CONTROLLER)
INTERVAL = minu(60)  # Control frequency
NUM_CPU_READINGS = 120
MIG_OVERHEAD_SOURCE = 0.00
MIG_OVERHEAD_TARGET = 0.00

# Setup logging
logger = sonarlog.getLogger('controller')

class Strategy(strategy.StrategyBase):
    
    def __init__(self, scoreboard, pump, model):
        super(Strategy, self).__init__(scoreboard, pump, model, INTERVAL, START_WAIT)
        
        # Setup migration queue
        simple = True
        self.migration_queue = MigrationQueue(self, simple, not simple, True)
       
    def start(self):
        # Super call
        super(Strategy, self).start()
        
        
    def dump(self):
        print 'DSAP controller - Dump configuration...'
        logger.info('Strategy Configuration: %s' % json.dumps({'name' : 'DSAP-Strategy',
                                                                 'start_wait' : START_WAIT,
                                                                 'interval' : INTERVAL,
                                                                 }))
        
    def __run_migrations(self):
        
        conversion_table = {}
        prev_assignment = {}
        i = 0
        for node in self.model.get_hosts(types.NODE):
            for domain_name in node.domains.keys():
                conversion_table[i] = domain_name
                prev_assignment[i] = conf_nodes.index_of(node.name)
                i +=1
        
        
        inverse_conversion_table = {domain_name : i for i, domain_name in conversion_table.iteritems()}
        
        
        demand_cpu = {}
        demand_mem = {}
        
        for domain in self.model.get_hosts(types.DOMAIN):
            
            if domain in conf_domains.initial_domains:
                domain_size = conf_domains.initial_domains[conf_domains.initial_domain_index(domain.name)].size
            else:
                domain_size = conf_domains.available_domains[conf_domains.available_domain_index(domain.name)].size
            
            
            domain_index = inverse_conversion_table[domain.name]
                       
            
            cpu_readings = domain.get_readings()
            
            
            domain_load = conf_nodes.to_node_load(np.mean(cpu_readings[-NUM_CPU_READINGS:]), domain_size)
            
            demand_cpu[domain_index] = domain_load
            demand_mem[domain_index] = domain.domain_configuration.get_domain_spec().total_memory()
            
            print 'domain : %d, demand_cpu : %d, demand_memory : %d' % (domain_index, domain_load, domain.domain_configuration.get_domain_spec().total_memory())
            
        # Assignment
        try:
            _, curr_assignment = dsapp.solve(conf_nodes.NODE_COUNT,
                                             conf_nodes.UTIL,
                                             conf_nodes.NODE_MEM,
                                             demand_cpu,
                                             demand_mem,
                                             prev_assignment,
                                             MIG_OVERHEAD_SOURCE,
                                             MIG_OVERHEAD_TARGET)
        except:
            print 'invalid solution #######################'
            # don't change anything and just return in case the model was infeasible
            return
        
        assignment_changed = dsapp.AssignmentChanged(prev_assignment, curr_assignment)
        print 'CHANGE in the Assignment : %s' % assignment_changed
        
        if not assignment_changed:
            # there is no change in the assignment, we can just return
            logger.info("Returning because the previous assignment was optimal...")
            return
            
        
        for index_domain in curr_assignment.keys():
            
            domain_name = conversion_table[index_domain]
            source_node = conf_nodes.get_node_name(prev_assignment[index_domain])
            target_node = conf_nodes.get_node_name(curr_assignment[index_domain])
            
            # Find current node for domain
            source_node = self.model.get_host_for_domain(domain_name).name
            
            # Trigger migration
            model_domain = self.model.get_host(domain_name)
            model_source = self.model.get_host(source_node)
            model_target = self.model.get_host(target_node)
            self.migration_queue.add(model_domain, model_source, model_target)    
    
    def balance(self):
        
        # Wait for migration queue to finish up all migrations
        if not self.migration_queue.empty():
            return
        
        # Trigger migrations
        self.__run_migrations()
    
    def post_migrate_hook(self, success, domain, node_from, node_to, end_time):
        node_from.blocked = self.pump.sim_time() - 1
        node_to.blocked = self.pump.sim_time() - 1
        self.migration_queue.finished(success, domain, node_from, node_to)
    
