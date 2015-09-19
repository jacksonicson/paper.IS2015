from logs import sonarlog
import conf_domainsize
import conf_nodes
import math
import placement_dotproduct
import numpy as np

# Setup Sonar logging
logger = sonarlog.getLogger('placement')

#############################
## CONFIGURATION           ##
#############################
DOT_PRODUCT = False
COSINE = not DOT_PRODUCT
#############################

class DotProductDemand(placement_dotproduct.DotProduct):
    def test_nodes(self, new_domain, nodelist):
        results = []
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
            
            # Calculate the dot product
            w_cpu = w_mem = 1
            abs_res = math.sqrt(math.pow(resd_cpu, 2) + math.pow(resd_mem, 2))
            abs_vm = math.sqrt(math.pow(domain_cpu_demand, 2) + math.pow(domain_mem_demand, 2))
            dot_product = w_cpu * resd_cpu * domain_cpu_demand + w_mem * resd_mem * domain_mem_demand
            cosine = dot_product / (abs_res * abs_vm)
             
            # Check if this host is able to handle the new domain
            cpu_delta = resd_cpu - domain_cpu_demand
            mem_delta = resd_mem - domain_mem_demand
            if cpu_delta >= 0 and mem_delta >= 0:
                results.append((node, dot_product, cosine))
            else:
                print 'failed for node %s - status: %i mem %i cpu' % (node.name, mem_delta, cpu_delta)
            

        if results:
            # Get the node with the best (greatest) dot product
            results.sort(key=lambda x: x[1])
            results.reverse()
            best_dot_product = results[0][0]
                        
            # Get the node with the best (smallest) cosine
            results.sort(key=lambda x: x[2])
            best_cosine = results[0][0]
            
            return (best_dot_product.name, best_cosine.name)
