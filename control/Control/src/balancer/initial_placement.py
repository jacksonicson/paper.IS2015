from logs import sonarlog
from workload.timeutil import *  # @UnusedWildImport
import conf_domains
import conf_nodes

# Setup logging
logger = sonarlog.getLogger('initial_placement')

class InitialPlacement(object):
    def _count_active_servers(self, assignment):
        buckets = [True for _ in xrange(len(conf_nodes.NODES))]
        active_servers = 0
        active_server_list = []
        for service in assignment.keys():
            inode = assignment[service]
            if buckets[inode]:
                buckets[inode] = False
                active_servers += 1
                active_server_list.append(conf_nodes.get_node_name(inode))
            
        return active_servers, active_server_list
            
    '''
    Returns a tuple of migrations and number of active servers. Migrations is a dictionary 
    with domain indices as keys and node indices as values. 
    [domain index] -> server index  
    '''
    def execute(self):
        # Dump nodes configuration
        conf_nodes.dump(logger)
        
