from libvirt import VIR_MIGRATE_LIVE, VIR_MIGRATE_UNDEFINE_SOURCE, \
    VIR_MIGRATE_PERSIST_DEST
from threading import Thread
import conf_domains
import libvirt
import conf_nodes
import sys
import time
import traceback
import util
import configuration

# Script requires production mode
configuration.force_production_mode()

# Libvirt global error handler
def err_handler(ctxt, err):
    filters = [(42, 10)]
    for f in filters:
        if err[0] == f[0] and err[1] == f[1]:
            return
        
    print 'Libvirt error %s: %s' % (ctxt, err)
    
# Register error handler in libvirt
libvirt.registerErrorHandler(err_handler, 'context') 

class MigrationThread(Thread):
    '''
    Each domain migration is executed in its own thread
    '''
    
    def __init__(self, domain, node_from, node_to, migration_callback, info):
        super(MigrationThread, self).__init__()
        
        # Migration parameters
        self.domain = domain
        self.node_from = node_from
        self.node_to = node_to
        self.migration_callback = migration_callback
        self.info = info
        self.exited = False
    
    def run(self):
        # Log live migration duration
        self.start = time.time()
        
        # Get connections to the source and target node
        lv_connection_from = util.connect(self.node_from)
        lv_connection_to = util.connect(self.node_to)
                
        # Success and error status
        success, error = False, None
        try:
            # Lookup domain on source node
            # This call might fail in the following constellation: 
            # 1. Controller decides to migrate a VM and triggers migration thread
            # 2. VM gets deallocated by Rain
            # 3. Migration thread starts and tries to lookup the domain
            self.lv_domain = lv_connection_from.lookupByName(self.domain)
            
            # Trigger migration
            self.lv_domain = self.lv_domain.migrate(lv_connection_to,
                                    VIR_MIGRATE_LIVE | VIR_MIGRATE_UNDEFINE_SOURCE | VIR_MIGRATE_PERSIST_DEST,
                                    self.domain, None, 0)
            
            # Sleep a bit
            time.sleep(5)
            
            # Check if domain is actually there
            test_lv_domain = lv_connection_to.lookupByName(self.domain)
            
            # Migration is successful if domain was found on target node
            success = test_lv_domain != None
            
        except libvirt.libvirtError as e:
            print 'Migration failed'
            error = e
        except Exception as e:
            print 'Migration failed'
            error = e
        except:
            print 'Migration failed'
            error = sys.exc_info()[0]
        finally:
            # Log migration duration
            self.end = time.time()

            # Callback with success and error status            
            self.migration_callback(self.domain, self.node_from, self.node_to,
                                    self.start, self.end, self.info,
                                    success, error)
            
            # Set exited flag
            self.exited = True
                

def migrateDomain(domain, node_from, node_to, migration_callback, info=None, maxDowntime=60000):
    '''
    Migrates domain from source node to target node. After the migration a callback function
    is triggered. The info value allows to attach a state to the migration. 
    '''
        
    # Start a new migration thread
    thread = MigrationThread(domain, node_from, node_to, migration_callback, info)
    thread.start()
    
    # Update maximum downtime. This is only possible after the start of an migration. 
    while thread.exited == False:
        # Wait until domain is migrating
        time.sleep(1)
        
        # Update maximum downtime
        try:
            # Second argument is an unused flag
            thread.lv_domain.migrateSetMaxDowntime(maxDowntime, 0)
            print 'Max migration time sucessfully set to %i milliseconds' % maxDowntime
            
            # Exit migration downtime setting loop
            break
        except:
            pass
    

def migrateAllocation(migrations):
    '''
    Gets a list of migrations. Each list element is a tupel of the structure: 
    (domain name, target node index in the nodes model)
    '''
    
    # trigger migrations
    for migration in migrations:
        # Get domain and target node
        domain_name = migration[0]
        target_node = conf_nodes.get_node_name(migration[1])
        
        # Search the node which currently holds the domain
        lv_domain, lv_connection_source = util.find_domain(domain_name)
        if lv_domain == None:
            print 'WARN: Skipping migration - could not find domain: %s' % (domain_name)
            continue
        
        # Check if domain is running (parater is an unused flag)
        domain_state = lv_domain.state(0)[0]
        if domain_state != 1:
            # Destroy 
            print '(Re)starting the domain %s' % (domain_name)
            
            # If domain is not shut off 
            if domain_state != 5: 
                try:
                    lv_domain.destroy()
                except: pass
            
            # Start domain and wait for it
            try:
                lv_domain.create()
                time.sleep(10)
            except: pass
        
        # Is migration necessary
        source_host = util.get_hostname(lv_connection_source)
        target_host = target_node  

        # Skip if migration is not necessesary        
        if source_host == target_host:
            print 'Skipping migration - identical source and target node %s = %s' % (source_host, target_host)
            continue
        
        # Check if mig
        try:
            # Get target node connection
            lv_connection_target = util.connections[target_node]

            # Trigger migration without bandwith limitation (last parameter)            
            print 'Migrating domain: %s -> %s' % (domain_name, target_host)
            lv_domain = lv_domain.migrate(lv_connection_target,
                                    VIR_MIGRATE_LIVE | VIR_MIGRATE_UNDEFINE_SOURCE | VIR_MIGRATE_PERSIST_DEST,
                                    domain_name, None, 0)
        except:
            print 'Skipping - migration failed'
            traceback.print_exc(file=sys.stdout)
            

def determine_current_allocation():
    '''
    Determines the current domain to node allocation in the infrastructure
    '''
    
    # Create empty allocation map
    allocation = { node : [] for node in conf_nodes.NODES }
        
    # Get data for each node
    for node in conf_nodes.NODES:
        # Get connection to node
        lv_connection = util.connections[node]
        
        # List all active domains
        lv_domains = lv_connection.listDomainsID()
        for lv_id in lv_domains:
            # Get domain name for id
            lv_domain = lv_connection.lookupByID(lv_id)
            name = lv_domain.name()
            
            # Filter all domains that are not configured 
            if conf_domains.is_initial_domain(name):
                # Add domain to allocation map
                allocation[node].append(name)
            else:
                print 'Skipping domain %s while determing current allocation - it is not in the domain list!' % name

    return allocation

