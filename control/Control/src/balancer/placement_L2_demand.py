from logs import sonarlog
import conf_domainsize
import conf_nodes
import placement_L2
import math
import numpy as np

# Setup Sonar logging
logger = sonarlog.getLogger('placement')

class L2Demand(placement_L2.L2):
    def test_nodes(self, new_domain, nodelist):
        norms = []
        for node in nodelist: 
            # Aggregate load for the complete host 
            mem_load = 0
              
            for dom in node.domains.values():
                spec = dom.domain_configuration.get_domain_spec()
                mem_load += spec.total_memory()
            
            # Get actual CPU measurements
            curr_cpu_demand = np.percentile(node.get_readings(), 95)
            resd_cpu = conf_nodes.UTIL - curr_cpu_demand
            
            # Calculate residual vector
            resd_mem = conf_nodes.NODE_MEM - mem_load
            
            # VM resource demand
            spec = conf_domainsize.get_domain_spec(new_domain.size)

            # Calculate estiated CPU demand if VM is almost
            domain_cpu_demand = conf_nodes.to_node_load(95, new_domain.size)
            domain_mem_demand = spec.total_memory()
            
            # Calculate the norm
            norm = 1 * math.pow(domain_cpu_demand - resd_cpu, 2) + 1 * math.pow(domain_mem_demand - resd_mem, 2)

            # Check if this host is able to handle the new domain
            cpu_delta = resd_cpu - domain_cpu_demand
            mem_delta = resd_mem - domain_mem_demand
            if cpu_delta >= 0 and mem_delta >= 0:
                norms.append((node, norm, curr_cpu_demand, mem_load))
            else:
                print 'failed for node %s - status: %i mem %i cpu' % (node.name, mem_delta, cpu_delta)
            
        # Find the node with the lowest norm that is able to host the domain
        norms.sort(key=lambda x: x[1])
        spec = conf_domainsize.get_domain_spec(new_domain.size)
        for norm in norms: 
            # Node found 
            return norm[0].name
        
    