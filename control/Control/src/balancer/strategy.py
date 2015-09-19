from logs import sonarlog
import configuration
import json
import numpy as np

# Setup Sonar logging
logger = sonarlog.getLogger('controller')

'''
Simulates the wait time for a transaction. 
'''
class SimulatedMigration:
    def __init__(self, pump, domain, node_from, node_to, migration_callback, info):
        # Reference to message pump
        self.pump = pump
        
        # Callback handler
        self.migration_callback = migration_callback
        
        # Migration information
        self.domain = domain
        self.node_from = node_from
        self.node_to = node_to
        self.info = info
    
    def run(self):
        # Set migration start time
        self.start = self.pump.sim_time()
        
        # Parameters are determined by experimental results
        # wait = 60 # const value used before
        wait = np.random.lognormal(mean=3.29, sigma=0.27, size=100)
        # wait = np.random.lognormal(mean=4, sigma=0.27, size=100)
        wait = wait[50]
        
        # Simulate migration wait time
        self.pump.callLater(wait, self.__callback)
        
    def __callback(self):
        # Set migration end time
        self.end = self.pump.sim_time()
        
        # Call migration callback
        self.migration_callback(self.domain, self.node_from, self.node_to,
                                self.start, self.end, self.info, True, None)
        self.finished = True
        
        
        

class StrategyBase(object):
    def __init__(self, scoreboard, pump, model, interval, start_wait):
        '''
        Strategy is initialized but not started.
        WARNING: The model is not built at this point and cannot be used
        therefore. Code that requires the model needs to be executed in start() 
        '''
        
        # Reference to scoreboard
        self.scoreboard = scoreboard
        
        # Reference to the message pump
        self.pump = pump 
        
        # Data model
        self.model = model
        
        # Execution interval
        self.interval = interval
        
        # Start wait
        self.start_wait = start_wait
        
        # Migration id counter
        self.migration_id_counter = 0
        
        
    def balance(self):
        '''
        Override this
        Called regularly to trigger control actions 
        '''
        pass
    
    def start(self):
        '''
        Override this and call super
        Executed when the strategy is actually started 
        '''
        print 'Sleeping before activating balancer strategy: %i' % self.start_wait
        logger.log(sonarlog.SYNC, 'Releasing load balancer')
        self.pump.callLater(self.start_wait, self.run)
    
    def __migration_callback(self, domain, node_from, node_to, start, end, info, status, error):
        
        # Get model objects for source and target node
        node_from = self.model.get_host(node_from)
        node_to = self.model.get_host(node_to)
        
        # Migration duration
        duration = end - start
        
        # Migration info in a JSON object
        data = json.dumps({'domain': domain,
                           'from': node_from.name,
                           'to': node_to.name,
                           'start' : start,
                           'end' : end,
                           'duration' : duration,
                           'id': info.migration_id,
                           'source_cpu' : info.source_load_cpu,
                           'target_cpu' : info.target_load_cpu})
        
        
        # Get domain object from model
        # Domain might not exist after this migration callback
        # Reason: It was shut down by the infrastructure service during the migration
        domain = self.model.get_host(domain)
        
        # Check if migration was successful
        if status == True:
            # Update model - if domain still exists (infrastructure service handin)
            if domain is not None: 
                node_to.domains[domain.name] = domain
                del node_from.domains[domain.name]
        
            # Call post migration hook
            self.post_migrate_hook(True, domain, node_from, node_to, end)
            
            # Log migration status
            print 'Migration finished'
            logger.info('Live Migration Finished: %s' % data)
            
        else:
            if domain is not None: 
                # Call post migration hook
                self.post_migrate_hook(False, domain, node_from, node_to, end)
                
                # Log migration status
                print 'Migration failed'
                logger.error('Live Migration Failed: %s' % data)
            else:
                # Call post migration hook
                self.post_migrate_hook(True, domain, node_from, node_to, end)
                
                # Log migration status
                print 'Migration finished - domain was removed during migration'
                logger.info('Live Migration Finished: %s' % data)
            
            
        # Always remove migration from model
        # Update migration counters
        node_from.active_migrations_out -= 1
        node_to.active_migrations_in -= 1
            
        # Release locks
        node_from.blocked = end
        node_to.blocked = end
            
        # Log number of empty servers
        self.model.reallocated()
        self.model.log_active_server_info()
        
        # Update scoreboard
        self.scoreboard.add_migration_type(end, info)
        
        
    def migrate(self, domain, source, target):
        '''
        Trigger the migration of domain from source to target node which are the names
        of the domain and nodes as string. kvalue is only used for reporting purpose. 
        '''
        
        print 'Migration triggered'
        
        # Assert migration
        self.model.dump()
        domain = self.model.get_host(domain.name)
        node_from = self.model.get_host(source.name)
        node_to = self.model.get_host(target.name)
        assert(source != target)
        assert(domain.name in node_from.domains.keys())
        assert(domain.name not in node_to.domains.keys())
        
        # Update counter
        migration_id = self.migration_id_counter
        self.migration_id_counter += 1
        
        # Block source and target nodes: Set block times in the future  
        # to guarantee that the block does not run out until the migration is finished
        now_time = self.pump.sim_time()
        source.blocked = now_time + 60 * 60
        target.blocked = now_time + 60 * 60
        
        # Update migration counters
        source.active_migrations_out += 1
        target.active_migrations_in += 1
        
        # Log migration start
        data = json.dumps({'domain': domain.name,
                           'from': source.name,
                           'to': target.name,
                           'id': migration_id})
        logger.info('Live Migration Triggered: %s' % data)
        print 'Live Migration Triggered: %s' % data
        
        # Backup current model status - for later analytics
        class info(object):
            pass
        info = info()
        info.migration_id = migration_id
        info.source_load_cpu = source.mean_load(20)
        info.target_load_cpu = target.mean_load(20)
        
        # Swtich between production and simulation configuration
        if configuration.PRODUCTION:
            # Import this only in production mode. Simulation systems don't have the libs installed
            from virtual import allocation
            
            # Verify model
            print 'Verifying current allocation...'
            status = self.model.verify_current_allocation()
            print 'Verification status: %r' % status
            
            # Call migration code and hand over the migration_callback reference
            allocation.migrateDomain(domain.name, source.name, target.name,
                                     self.__migration_callback, maxDowntime=configuration.MIGRATION_DOWNTIME, info=info)
        else:
            # Simulate migration
            migration = SimulatedMigration(self.pump, domain.name, source.name, target.name,
                                           self.__migration_callback, info)
            migration.run()
            
            
    def run(self):
        # Run load balancing code
        print 'Running load balancer...'
        self.balance()

        # DEBUGGING        
        # Dump scoreboard information 
#        if not configuration.PRODUCTION:
#            print 'Scoreboard:'
#            self.scoreboard.dump()
            
        # Wait for next control cycle
        self.pump.callLater(self.interval, self.run)
                
