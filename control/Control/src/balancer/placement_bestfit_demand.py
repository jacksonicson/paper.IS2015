from logs import sonarlog
import conf_domainsize
import conf_nodes
import placement_bestfit
import numpy as np

# Setup Sonar logging
logger = sonarlog.getLogger('placement')

class BestFitDemand(placement_bestfit.BestFit):
    def sort(self, host_choice, _key):
        return sorted(host_choice, key = _key)
        
    def test_nodes(self, new_domain, node_list):
        host_choice = []
        for node in node_list:
            # Get actual CPU measurements
            curr_cpu_demand = np.percentile(node.get_readings(), 95)
            
            # Memory demand is calculated by summing up all VM reservations
            mem_load = 0
              
            # Calculate the node utilization by accumulating all domain loads
            for dom in node.domains.values():
                spec = dom.domain_configuration.get_domain_spec()
                mem_load += spec.total_memory()
            
            # Calculate metric
            spec = conf_domainsize.get_domain_spec(new_domain.size)
            mem_delta = conf_nodes.NODE_MEM - (mem_load + spec.total_memory())
            
            
            # Calculate estiated CPU demand if VM is almost
            vm_cpu_demand = conf_nodes.to_node_load(95, new_domain.size)
            cpu_delta = conf_nodes.UTIL - curr_cpu_demand - vm_cpu_demand
            
            # Calculate fit metric
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
        
        
