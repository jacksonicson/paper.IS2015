from logs import sonarlog
import conf_domainsize
import model
import conf_nodes
import placement

# Setup Sonar logging
logger = sonarlog.getLogger('placement')

class BestFit(placement.PlacementBase):
    def __init__(self, model):
        super(BestFit, self).__init__(model)
    
    def sort(self, host_choice, _key):
        return sorted(host_choice, key = _key)
        
    def test_nodes(self, new_domain, node_list):
        host_choice = []
        for node in node_list:
            # Aggregate load for the complete host 
            cpu_load = 0
            mem_load = 0
              
            # Calculate the node utilization by accumulating all domain loads
            for dom in node.domains.values():
                spec = dom.domain_configuration.get_domain_spec()
                cpu_load += spec.total_cpu_cores()
                mem_load += spec.total_memory()
            
            # Calculate metric
            spec = conf_domainsize.get_domain_spec(new_domain.size)
            cpu_delta = conf_nodes.NODE_CPU_CORES - (cpu_load + spec.total_cpu_cores())
            mem_delta = conf_nodes.NODE_MEM - (mem_load + spec.total_memory())
            metric = cpu_delta * mem_delta
            
            # Server is not able to handle the domain
            if cpu_delta < 0 or mem_delta < 0:
                continue
            
            # Add metric to the choice list
            host_choice.append((node.name, metric))
              
        # Check if we found at least one host
        if not host_choice:
            return None
          
        # Sort host choice list
        host_choice = self.sort(host_choice, lambda x: x[1])
        
        # Pkc hte one with the lowest metric (best fit)
        return host_choice[0][0] 
        
    def placement(self, domain):
        node_list = self.model.get_hosts(model.types.NODE)
        
        # Find active and inactive nodes
        active_nodes = []
        inactive_nodes = []
        for node in node_list:
            if node.domains:
                active_nodes.append(node)
            else:
                inactive_nodes.append(node)
                
        # No need to sort the active nodes. We'll always pick
        # the node that fits best independent to the list order.
                
        # Find the best fit on active nodes
        node = self.test_nodes(domain, active_nodes)
        if node is None:
            node = inactive_nodes[0].name
        
        logger.info('bestfit placed domain %s on host %s' % (domain.name, node))
        return node
            
            
            
             
        
        
