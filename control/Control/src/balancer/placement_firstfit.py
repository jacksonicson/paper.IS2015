from logs import sonarlog
import conf_domainsize
import conf_nodes
import model
import placement
import placement_bestfit

# Setup Sonar logging
logger = sonarlog.getLogger('placement')

class FirstFit(placement.PlacementBase):
    def __init__(self, model):
        super(FirstFit, self).__init__(model)
        self.bestfit = placement_bestfit.BestFit(model)
    
    def test_nodes(self, active_nodes, new_domain):
        # Go over all hosts
        for node in active_nodes:
            # Aggregate resource load for this host
            curr_cpu_demand = 0
            curr_mem_demand = 0

            # Add up the demands of all domains running on the host              
            for old_domain in node.domains.values():
                # Domain size specification 
                spec = old_domain.domain_configuration.get_domain_spec()
                
                # Sum up cpu and mem load 
                curr_cpu_demand += spec.total_cpu_cores()
                curr_mem_demand += spec.total_memory()
            
            # Calculate metric
            new_domain_spec = conf_domainsize.get_domain_spec(new_domain.size)
            cpu_delta = conf_nodes.NODE_CPU_CORES - curr_cpu_demand - new_domain_spec.total_cpu_cores()
            mem_delta = conf_nodes.NODE_MEM - curr_mem_demand - new_domain_spec.total_memory()
            
            # If metric is positive, the node can host the domain
            if cpu_delta >= 0 and mem_delta >= 0: 
                return node.name 
        
        
    def placement(self, new_domain):
        nodelist = self.model.get_hosts(model.types.NODE)
        
        # Find active and inactive nodes
        active_nodes = []
        inactive_nodes = []
        for node in nodelist:
            if node.domains:
                active_nodes.append(node)
            else:
                inactive_nodes.append(node)
               
        # Sort active nodes by their creation time
        active_nodes.sort(key=lambda node:node.activation_time)
            
        # Test active nodes    
        target_node = self.test_nodes(active_nodes, new_domain)
        if target_node is None:
            # Check if enough inactive nodes are available
            if not inactive_nodes:
                print 'FATAL: No remaining inactive nodes' 
                import sys
                sys.exit(1)
            target_node = inactive_nodes[0].name

        logger.info('firstfit placed new domain %s on host %s' % (new_domain.name, target_node))            
        return target_node
