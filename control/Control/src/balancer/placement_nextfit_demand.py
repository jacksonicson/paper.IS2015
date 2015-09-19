from logs import sonarlog
import conf_domainsize as domainsize
import conf_nodes as nodes
import placement_nextfit
import conf_schedule
import numpy as np
import conf_nodes

# Setup Sonar logging
logger = sonarlog.getLogger('placement')

class NextFitDemand(placement_nextfit.NextFit):
    
    def placement(self, domain):
        # Get list of inactive nodes
        inactive_nodes = self._get_inactive_nodes()
        
        # Set initial active node
        if self.active_node is None:
            self.active_node = inactive_nodes.pop()

        # Domain specification of the new domain to place
        domain_spec = domainsize.get_domain_spec(domain.size)

        # Calculate total demand of all active domains running on selected node
        mem_demand = 0
                
        for active_domain in self.active_node.domains.values():
            active_domain_configuration = active_domain.domain_configuration
            active_domain_spec = domainsize.get_domain_spec(active_domain_configuration.size)
            mem_demand += active_domain_spec.total_memory()
            
        # Get actual CPU measurements
        curr_cpu_demand = np.percentile(self.active_node.get_readings(), 95)
            
        # Calculate residual capacity
        mem_demand = nodes.NODE_MEM - domain_spec.total_memory() - mem_demand

        # Calculate estiated CPU demand if VM is almost
        domain_cpu_demand = conf_nodes.to_node_load(95, domain.size)
        cpu_demand = conf_nodes.UTIL - domain_cpu_demand - curr_cpu_demand 
        
        # Get new node if current one is overloaded
        if cpu_demand < 0 or mem_demand < 0:
            try:
                self.active_node = inactive_nodes.pop()
            except:
                print 'inactive nodes length: %i' % len(inactive_nodes)
                self.model.dump()
                print 'PROBLEM IN SCHEDULE ID: %i' %conf_schedule.SCHEDULE_ID 
                raise ValueError('FATAL error: No more free nodes available %i - sc %i' % (len(inactive_nodes), conf_schedule.SCHEDULE_ID))
 
        
        # Return selected node
        return self.active_node.name
    
