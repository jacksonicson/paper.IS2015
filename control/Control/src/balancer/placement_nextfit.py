from logs import sonarlog
import conf_domainsize as domainsize
import conf_nodes as nodes
import model
import placement
import conf_schedule

# Setup Sonar logging
logger = sonarlog.getLogger('placement')

class NextFit(placement.PlacementBase):
    
    def __init__(self, model):
        super(NextFit, self).__init__(model)
        self.active_node = None

    def _get_inactive_nodes(self):
        # Get list of inactive nodes
        inactive_nodes = []
        print 'total nodes %i' % len(self.model.get_hosts(model.types.NODE))
        for node in self.model.get_hosts(model.types.NODE):
            if not node.domains:
                inactive_nodes.append(node)
        print 'inactive nodes %i' % len(inactive_nodes)
        return inactive_nodes

    def placement(self, domain):
        # Get list of inactive nodes
        inactive_nodes = self.__get_inactive_nodes()
        
        # Set initial active node
        if self.active_node is None:
            self.active_node = inactive_nodes.pop()

        # Domain specification of the new domain to place
        domain_spec = domainsize.get_domain_spec(domain.size)
        
        # Calculate total demand of all active domains running on selected node
        cpu_demand = 0
        mem_demand = 0
                
        for active_domain in self.active_node.domains.values():
            active_domain_configuration = active_domain.domain_configuration
            active_domain_spec = domainsize.get_domain_spec(active_domain_configuration.size)
            
            cpu_demand += active_domain_spec.total_cpu_cores()
            mem_demand += active_domain_spec.total_memory()
            
        # Calculate residual capacity
        cpu_demand = nodes.NODE_CPU_CORES - domain_spec.total_cpu_cores() - cpu_demand
        mem_demand = nodes.NODE_MEM - domain_spec.total_memory() - mem_demand
        
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
    
