from workload import forecasting as smooth
from collector import ttypes
from fflop import filter
from logs import sonarlog
from workload import load
import conf_domainsize
import conf_domains
import json
import conf_nodes
import numpy as np

################################
# CONFIGURATION               ##
WINDOW = 7000
################################

# Setup logging 
logger = sonarlog.getLogger('controller')

# Enum of node types
def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    return type('Enum', (), enums)
types = enum('NODE', 'DOMAIN')

# Model
class Model(object):
    
    def __init__(self, pump, scoreboard):
        self.pump = pump
        self.scoreboard = scoreboard
        self.subscribe_handlers = []
        self.hosts = {}
        
    def __update_TS_of_domain(self, domain):
        # Load trace
        configuration = domain.domain_configuration
        index = configuration.loadIndex
        freq, ts = load.get_cpu_trace(index, domain.domain_configuration.size)
        
        # Attach TS to domain 
        domain.ts = ts
        domain.ts_freq = freq
        
    
    def __update_all_TS_assignment(self):
        # Iterate over all domains and assign them a TS
        for domain in self.get_hosts(types.DOMAIN):
            self.__update_TS_of_domain(domain)
    
    
    def __update_scoreboard(self):
        pass
        
      
      
    def reallocated(self):
        self.__update_scoreboard()
     
      
    def new_domain(self, host, domain):
        # Create a new domain
        cores = domain.get_domain_spec().total_cpu_cores()
        dom = Domain(domain.name, cores)
        dom.creation_time = self.pump.sim_time()
        dom.domain_configuration = domain
        
        # Ensure that domain is not registered already
        if domain.name in self.hosts:
            print 'WARN: Domain %s already registered in model' % domain.name
            return
        
        # Add it to the host and and the hosts list
        self.hosts[domain.name] = dom
        self.hosts[host].add_domain(dom, self.pump.sim_time())
        
        # Block node for migrations
        now_time = self.pump.sim_time()
        self.hosts[host].blocked = now_time + 5 * 60
        
        # Connect with times 
        self.__update_TS_of_domain(dom)
        
        # Count domain launch in scoreboard
        self.scoreboard.add_domain_launch()
        
        # Update scoreboard
        self.__update_scoreboard()
        
        # Notify subscribe handlers
        self.notify_subscribe_handler(dom, True)
        
        return dom
      
      
    def reset(self):
        for host in self.get_hosts():
            host.blocked = 0
      
      
    def add_subscribe_handler(self, handler):
        self.subscribe_handlers.append(handler)
        
        
    def notify_subscribe_handler(self, host, alive):
        for handler in self.subscribe_handlers:
            handler(host, alive)  
    
    
    def get_hosts(self, host_type=None):
        if host_type == None:
            return self.hosts.values()
        
        filtered = []
        for host in self.hosts.values():
            if host.type == host_type:
                filtered.append(host) 
        
        return filtered


    def get_host(self, hostname):
        if self.hosts.has_key(hostname):
            return self.hosts[hostname]
        return None


    def get_host_for_domain(self, domain):
        for host in self.get_hosts(types.NODE):
            if host.has_domain(domain):
                return host
        return None
    

    def get_assignment_list(self):
        '''
        Only required by the DSAP controller that works with 
        indices on the nodes and dyndomain lists. 
        '''
        assignment = {}
        for node in self.get_hosts(types.NODE):
            for domain_name in node.domains.keys():
                assignment[conf_domains.initial_domain_index(domain_name)] = conf_nodes.index_of(node.name)
        return assignment


    def server_active_info(self):
        active_count = 0
        active_names = []
        for node in self.get_hosts(types.NODE):
            if node.domains:
                active_names.append(node.name)
                active_count += 1
        return active_count, active_names
    
    
    def verify_current_allocation(self):
        # Local import because libvirt is not available everywhere
        from virtual import allocation
        
        # Determine current infrastructure allocation
        allocation = allocation.determine_current_allocation()
        
        # Go over all node names
        for node_name in allocation.iterkeys():
            # Check if node is registered
            if node_name not in self.hosts:
                print 'FATAL ERROR: Node %s is not registered in model!' % node_name
                return False
            
            # Get host
            node = self.hosts[node_name]
            
            # Go over all domains of this node
            for domain_name in allocation[node_name]:
                # Check if domain is registered as a domain node
                if domain_name not in self.hosts:
                    print 'FATAL ERROR: Domain %s is not registered in model!' % node_name
                    return False
                
                # Check if domain is registered on the right server node
                if domain_name not in node.domains:
                    print 'FATAL ERROR: Domain %s is not registered in Node %s in model!' % (domain_name, node_name)
                    return False

        # No errors found
        return True
    
    
    def model_from_current_allocation(self):
        # Local import because libvirt is not available everywhere
        from virtual import allocation
        
        # Determine current infrastructure allocation
        allocation = allocation.determine_current_allocation()

        #  Mapping        
        self.hosts = {}
        
        # Go over all node names
        for node_name in allocation.iterkeys():
            # Create a new node
            node = Node(node_name, conf_nodes.NODE_CPU_CORES)
            self.hosts[node_name] = node
            
            # Go over all domains of this node
            for domain_name in allocation[node_name]:
                # Create a new domain and add it to the node 
                domain = Domain(domain_name, conf_domainsize.get_domain_spec().total_cpu_cores())
                domain.domain_configuration = conf_domains.find_any_domain_by_name(domain_name)
                node.add_domain(domain)
                self.hosts[domain_name] = domain
                
        # Update TS assignment for all domains
        self.__update_all_TS_assignment()
        
        # Update scoreboard status
        self.__update_scoreboard()


    def model_from_migrations(self, migrations):
        self.hosts = {}
        
        # Create list of nodes based on migration targets
        _nodes = []
        for node in conf_nodes.NODES: 
            mnode = Node(node, conf_nodes.NODE_CPU_CORES)
            self.hosts[node] = mnode
            _nodes.append(mnode)
            
        # Create list of domains 
        _domains = {}
        for domain_config in conf_domains.initial_domains:
            # Create a new domain
            dom = Domain(domain_config.name, conf_domainsize.get_domain_spec(domain_config.size).total_cpu_cores())
            dom.domain_configuration = domain_config
            
            # Add domain to hosts list
            self.hosts[domain_config.name] = dom
            _domains[domain_config.name] = dom
            
        # Assign domains to nodes based on migrations
        for migration in migrations:
            _nodes[migration[1]].add_domain(_domains[migration[0]])
            
        # Update TS assignment for all domains
        self.__update_all_TS_assignment()
        
        # Update scoreboard status
        self.__update_scoreboard()
    
    
    def del_domain(self, domain):
        # Get name of domain
        domain_name = domain.name
        
        # Check if domain is known 
        if domain_name in self.hosts:
            # Check node
            node = self.get_host_for_domain(domain_name)
            
            # Delete domain from node
            node.del_domain(domain_name, self.pump.sim_time())
                        
            # Delete domain itself
            del self.hosts[domain_name]
            
            # Update scoreboard
            self.__update_scoreboard()
            
            # Notify subscribe handlers
            self.notify_subscribe_handler(node, False)
            
            return True
        else:
            logger.error('Model cannot delete domain %s because it does not exist' % domain)
            
        return False
    
    def log_active_server_info(self):
        self.scoreboard.add_active_info(self.server_active_info()[0], self.pump.sim_time())
        
        active_server_info = self.server_active_info()
        print 'Updated active server count: %i' % active_server_info[0]
        logger.info('Active Servers: %s' % json.dumps({'count' : active_server_info[0],
                                                       'servers' : active_server_info[1],
                                                       'timestamp' : self.pump.sim_time()}))
        return active_server_info
    
    
    def dump(self):
        print 'Dump model status...'
        json_map = {}
        for node in self.get_hosts(host_type=types.NODE):
            # Fill json map of the model state
            json_map[node.name] = []
            for domain in node.domains.values():
                json_map[node.name].append(domain.name)
                
            # Print model if node is not empty
            if node.domains.values():
                print 'Node: %s' % (node.name)
                for domain in node.domains.values():
                    print '   Domain: %s' % domain.name 
                
        logger.info('Controller Initial Model: %s' % json.dumps(json_map))
    

class __Host(object):
    '''
    This is a private class which should not be used outside of this
    module. It is the base method for all entities representing concrete
    elements of the infrastructure.  
    '''
    
    def __init__(self, name, cores):
        self.name = name
        
        # Number of cores 
        self.cpu_cores = cores
        
        # Stores readings over the window
        self.readings = [0 for _ in xrange(0, WINDOW)]
        
        # Current index in the ring buffer
        self.counter = 0
        
        # Double exponential smoothing parameters
        self.globalCounter = 0
        self.f_t = 0
        self.c_t = 0
        self.T_t = 0
        
    def put(self, reading):
        # Add readings to a sliding window
        self.readings[self.counter] = reading.value
        self.counter = (self.counter + 1) % WINDOW
        
        # Calculates double exponential smoothing
        if self.globalCounter == 2:
            # Double exponential smoothing
            self.c_t = float(self.readings[0]) 
            self.T_t = float(self.readings[1] - self.readings[0])
            self.f_t = self.c_t + self.T_t
            self.globalCounter += 1
            
            # Flip flop filter
            self.ff = filter.FlipFlop()
            self.ff_status = None
            
        elif self.globalCounter > 2:
            # Double exponential smoothing
            self.f_t, self.c_t, self.T_t = smooth.continuouse_double_exponential_smoothed(self.c_t,
                                                                       self.T_t,
                                                                       reading.value,
                                                                       0.3, 0.1)
            # Flip flop filter
            self.ff_forecast, self.ff_status = self.ff.continous(reading.value, self.ff_status)
            
        else:
            self.globalCounter += 1

    
    def forecast(self):
        return self.f_t
    
    def flush(self, value=0):
        self.readings = [value for _ in xrange(0, WINDOW)]
        
    def mean_load(self, k=None):
        if k == None:
            return np.mean(self.readings)
        
        sorted_readings = self.get_readings()
        return np.mean(sorted_readings[-k:])
    
    def percentile_load(self, percentile, k=None):
        if k == None:
            sorted_readings = self.readings
        else:
            sorted_readings = self.get_readings()[-k:]
        
        return np.percentile(sorted_readings, percentile)
    
    
    def get_readings(self):
        index = (self.counter) % WINDOW
        result = []
        for _ in xrange(WINDOW):
            result.append(self.readings[index])
            index = (index + 1) % WINDOW
            
        return result
    
        
    
class Domain(__Host):
    def __init__(self, name, cores):
        super(Domain, self).__init__(name, cores)
                
        # Type of this object
        self.type = types.DOMAIN
        
        # Time when the domain was created
        self.creation_time = 0
        
        # Reference to the domain configuration
        self.domain_configuration = None
        
    def get_watch_filter(self):
        return ttypes.SensorToWatch(self.name, 'psutilcpu')
    

class Node(__Host):
    def __init__(self, name, cores):
        super(Node, self).__init__(name, cores)
                
        # Type of this object
        self.type = types.NODE
        
        # Migrations
        self.active_migrations_out = 0
        self.active_migrations_in = 0
        
        # Activation time
        self.activation_time = None
        
        # Holds a mapping of domains
        self.domains = {}
    
    def clean(self):
        self.active_migrations_in = 0
        self.active_migrations_out = 0
        self.activation_time = None
        self.domains.clear()
    
    def del_domain(self, domain_name, time=None):
        del self.domains[domain_name]
        if not self.domains:
            self.activation_time = None
    
    def add_domain(self, domain, time=None):
        if not self.domains:
            self.activation_time = time
        self.domains[domain.name] = domain
        
    def has_domain(self, domain):
        return self.domains.has_key(domain)
            
    def get_watch_filter(self):
        return ttypes.SensorToWatch(self.name, 'psutilcpu')
    
    def dump(self):
        domains = ', '.join(self.domains.keys())
        print 'Host: %s Load: %f Volume: %f Domains: %s' % (self.name, self.mean_load(5), self.volume, domains)





    


