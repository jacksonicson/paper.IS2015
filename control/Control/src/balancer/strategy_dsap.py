from logs import sonarlog
from migration_queue import MigrationQueue
import conf_domains
import conf_domainsize
import initial_placement_dsap_helper
import json
import conf_nodes
import numpy as np
import strategy
from schedule import schedule_builder

######################
#  CONFIGURATION    ##
######################
NUM_BUCKETS = 6  # Number of allocation buckets
TOTAL_EXPERIMENT_DURATION = schedule_builder.EXPERIMENT_DURATION 
PERCENTILE = 99 
MIGRATION_LIMIT = 30
######################

# Fixed values
START_WAIT = 0  # Data aggregation phase (ALWAYS 0 FOR THIS CONTROLLER)
INTERVAL = 10  # Control frequency

# Setup logging
logger = sonarlog.getLogger('controller')

class Strategy(strategy.StrategyBase):
    
    def __init__(self, scoreboard, pump, model):
        super(Strategy, self).__init__(scoreboard, pump, model, INTERVAL, START_WAIT)
        
        # Setup migration queue
        simple = True
        self.migration_queue = MigrationQueue(self, simple, not simple)
        
        # Build allocations
        self.placement = initial_placement_dsap_helper.DSAPPlacement()
        self.initial_migrations, self.active_server_info = self.placement.execute(NUM_BUCKETS,
                                                            lambda x: np.percentile(x, PERCENTILE),
                                                            MIGRATION_LIMIT)
            
        # Current bucket
        self.curr_bucket = 0
        
        
       
    def start(self):
        # Initialization time
        self.time_null = self.pump.sim_time()
        
        # Super call
        super(Strategy, self).start()
        
        
    def dump(self):
        print 'DSAP controller - Dump configuration...'
        logger.info('Strategy Configuration: %s' % json.dumps({'name' : 'DSAP-Strategy',
                                                                 'start_wait' : START_WAIT,
                                                                 'interval' : INTERVAL,
                                                                 'num_bucketsl' : NUM_BUCKETS,
                                                                 }))
        
    def __run_migrations(self, bucket_index):
        # Assignment
        curr_assignment = self.placement.assignment_list[bucket_index]
        
        # Previous assignment (based on model data - not uncertain calculation data)
        # Calculated data might be different from model data due to failed migrations
        # prev_assignment = self.placement.assignment_list[(bucket_index - 1) % NUM_BUCKETS]
        prev_assignment = self.model.get_assignment_list()
        
        for index_domain in curr_assignment.keys():
            # Get data
            domain_name = conf_domains.initial_domains[index_domain].name
            source_node = conf_nodes.get_node_name(prev_assignment[index_domain])
            target_node = conf_nodes.get_node_name(curr_assignment[index_domain])
            
            # Find current node for domain
            source_node = self.model.get_host_for_domain(domain_name).name
            
            # Trigger migration
            model_domain = self.model.get_host(domain_name)
            model_source = self.model.get_host(source_node)
            model_target = self.model.get_host(target_node)
            self.migration_queue.add(model_domain, model_source, model_target)
    
    def __run_optimized_migrations(self, bucket_index):
        # Create allocations lists for GOAP 
        # Assignment
        curr_assignment = self.placement.assignment_list[bucket_index]
        
        # Previous assignment
        prev_assignment = self.placement.assignment_list[(bucket_index - 1) % NUM_BUCKETS]
        
        as_current = [0 for _ in xrange(conf_domains.count())]
        as_next = [0 for _ in xrange(conf_domains.count())]
        
        for index_domain in xrange(conf_domains.count()):
            as_current[index_domain] = prev_assignment[index_domain]
            as_next[index_domain] = curr_assignment[index_domain]
                    
        # Get current domain loads
        domain_load = []
        for mapping in conf_domains.initial_domains:
            domain_name = mapping.domain
            load = self.model.get_host(domain_name).mean_load(20)
            domain_load.append(conf_nodes.to_node_load(load, conf_domainsize.DEFAULT))
                    
        # Schedule migrations
        from ai import astar
        migrations = astar.plan(conf_nodes.NODE_COUNT, as_current, as_next, domain_load)
        
        # Trigger migrations
        dep = None
        for migration in migrations:
            domain_name = conf_domains.initial_domains[migration[0]].domain
            source_node = conf_nodes.get_node_name(migration[1])
            target_node = conf_nodes.get_node_name(migration[2])
            
            print 'domain %s - source %s - target %s' % (domain_name, source_node, target_node) 
            
            model_domain = self.model.get_host(domain_name)
            model_source = self.model.get_host(source_node)
            model_target = self.model.get_host(target_node)
            
            # dep = self.migration_queue.add(model_domain, model_source, model_target, dep)
            dep = self.migration_queue.add(model_domain, model_source, model_target)
        return 
        
    
    def balance(self):
        # Current bucket index
        bucket_duration = TOTAL_EXPERIMENT_DURATION / NUM_BUCKETS
        time = self.pump.sim_time() - self.time_null  # relative time since end of ramp-up and start of steady-state
        timeg = time # global time in TS data  
        bucket_index = int(timeg / bucket_duration)  # always floor this value
        bucket_time = bucket_duration - (timeg - bucket_duration * bucket_index)
        
        # bucket_index %= NUM_BUCKETS
        print 'bucket index %i' % bucket_index
        print 'time till next bucket %i' % (bucket_time)
        if bucket_index >= NUM_BUCKETS:
            return

        # Schedule migrations only once per bucket
        if self.curr_bucket == bucket_index:
            return
        
        # Wait for migration queue to finish up all migrations
        if not self.migration_queue.empty():
            return
        
        # Update current bucket status
        self.curr_bucket = bucket_index
        
        # Trigger migrations to get new bucket allocation
        self.__run_migrations(self.curr_bucket)
        # self.__run_optimized_migrations(self.curr_bucket)
    
    
    def post_migrate_hook(self, success, domain, node_from, node_to, end_time):
        node_from.blocked = self.pump.sim_time() - 1
        node_to.blocked = self.pump.sim_time() - 1
        self.migration_queue.finished(success, domain, node_from, node_to)
    
