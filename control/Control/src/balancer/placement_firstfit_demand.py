from logs import sonarlog
import conf_domainsize
import conf_nodes
import placement_firstfit
import numpy as np

# Setup Sonar logging
logger = sonarlog.getLogger('placement')

class FirstFitDemand(placement_firstfit.FirstFit):
    
    def test_nodes(self, active_nodes, new_domain):
        # Go over all hosts
        for node in active_nodes:
            # Get actual CPU measurements
            curr_cpu_demand = np.percentile(node.get_readings(), 95)
            
            # Memory demand is calculated by summing up all VM reservations
            curr_mem_demand = 0

            # Add up the demands of all domains running on the host              
            for old_domain in node.domains.values():
                # Domain size specification 
                spec = old_domain.domain_configuration.get_domain_spec()
                
                # Sum up mem load 
                curr_mem_demand += spec.total_memory()
            
            # Calculate metrics
            new_domain_spec = conf_domainsize.get_domain_spec(new_domain.size)
            mem_delta = conf_nodes.NODE_MEM - curr_mem_demand - new_domain_spec.total_memory()
            
            # Calculate estiated CPU demand if VM is almost
            vm_cpu_demand = conf_nodes.to_node_load(95, new_domain.size)
            cpu_delta = conf_nodes.UTIL - curr_cpu_demand - vm_cpu_demand
            
            # If metric is positive, the node can host the domain
            if cpu_delta >= 0 and mem_delta >= 0: 
                return node.name 
        
