from logs import sonarlog
import conf_domainsize as domainsize
import conf_nodes as nodes
import model
import placement

logger = sonarlog.getLogger('placement')

##############################
# CONFIGURATION             ##
##############################
INTERVALS = 4
##############################

class Interval(object):
    def __init__(self, index, lower, upper):
        self.index = index
        self.lower = lower
        self.upper = upper
        
    def fits(self, domain_spec):
        fits = True
        fits &= self.lower <= domain_spec.total_cpu_cores()
        fits &= self.upper > domain_spec.total_cpu_cores()
        return fits

'''
Implements the harmonic fit bin packing online algorithm 
to allocate domains to hosts.

Based on the HARMONIC-M bin packing heuristic described in 
"Lee et al. - A Simple Online Bin Packing Algorithm":
http://dl.acm.org/citation.cfm?id=3833
'''
class Harmonic(placement.PlacementBase):
    
    def __init__(self, model):
        super(Harmonic, self).__init__(model)
        self.__build_intervals()
    
    def __build_intervals(self):
        # Valiate interval count and node count
        if INTERVALS < 1:
            raise ValueError("One interval required") 
        if nodes.NODE_COUNT < INTERVALS:
            raise ValueError("Node count must be above interval count")
        
        # Intervals list        
        self.intervals = []
        
        # For each interval (shift interval inex by +1) 
        for interval in xrange(1, INTERVALS + 1):
            # Upper bound is the max. number of CPU cores a domain will have in this interval
            upper_bound = float(nodes.NODE_CPU_CORES) / (interval)
            
            # Lower bound is the min. number of CPU cores a domain will have in this interval
            if interval + 1 == INTERVALS + 1:
                lower_bound = 0 # last interval
            else:
                lower_bound = float(nodes.NODE_CPU_CORES) / (interval + 1)
                
            # Add interval
            self.intervals.append(Interval(interval, lower_bound, upper_bound))
            
    def __check_capacity(self, host, domain):
        # Calculate total demand of all active domains running on selected node
        cpu_demand = 0
        mem_demand = 0
                
        for active_domain in host.domains.values():
            active_domain_configuration = active_domain.domain_configuration
            active_domain_spec = domainsize.get_domain_spec(active_domain_configuration.size)
            
            cpu_demand += active_domain_spec.total_cpu_cores()
            mem_demand += active_domain_spec.total_memory()
            
        # Domain specification of the new domain to place
        domain_spec = domainsize.get_domain_spec(domain.size)
            
        # Calculate residual capacity
        cpu_demand = nodes.NODE_CPU_CORES - domain_spec.total_cpu_cores() - cpu_demand
        mem_demand = nodes.NODE_MEM - domain_spec.total_memory() - mem_demand
        
        # Get new node if current one is overloaded
        return cpu_demand >= 0 and mem_demand >= 0
        
        
    def placement(self, domain):
        # Get all hosts
        hosts = self.model.get_hosts(model.types.NODE)
        
        # Find interval for new domain
        domain_spec = domainsize.get_domain_spec(domain.size)
        for interval in self.intervals:
            if interval.fits(domain_spec):
                break 
        
        if interval == None:
            raise ValueError("Could not find a suitable interval for domain")
        
        # Find all active hosts for the given interval and unused hosts
        interval_hosts = []
        unused_hosts = []
        for host in hosts: 
            if host.domains:
                try:
                    if host.harmonic_interval == interval.index:
                        interval_hosts.append(host)
                except:
                    unused_hosts.append(host)
                    pass
            else:
                unused_hosts.append(host)

        # Selected target node        
        selected = None       
         
        # Check if one of the interval hosts has enough free resources to handle the new domain
        for host in interval_hosts:
            if self.__check_capacity(host, domain):
                selected = host
                break
            
        # Open a new host
        if selected is None:
            selected = unused_hosts.pop()
            
            # Set harmonic interval index            
            selected.harmonic_interval = interval.index

        # Return selected node
        return selected.name
