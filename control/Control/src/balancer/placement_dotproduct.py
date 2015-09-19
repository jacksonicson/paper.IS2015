from logs import sonarlog
import conf_domainsize
import model
import conf_nodes
import placement
import math

# Setup Sonar logging
logger = sonarlog.getLogger('placement')

#############################
## CONFIGURATION           ##
#############################
DOT_PRODUCT = False
COSINE = not DOT_PRODUCT
#############################

class DotProduct(placement.PlacementBase):
    def __init__(self, model):
        super(DotProduct, self).__init__(model)
        
    def test_nodes(self, new_domain, nodelist):
        results = []
        for node in nodelist: 
            # Aggregate load for the complete host 
            cpu_load = 0
            mem_load = 0
              
            for dom in node.domains.values():
                spec = dom.domain_configuration.get_domain_spec() 
                cpu_load += spec.total_cpu_cores()
                mem_load += spec.total_memory()
            
            # VM resource demand
            spec = conf_domainsize.get_domain_spec(new_domain.size)
                
            # Calculate residual vector
            resd_cpu = conf_nodes.NODE_CPU_CORES - cpu_load
            resd_mem = conf_nodes.NODE_MEM - mem_load
            
            # Calculate the dot product
            w_cpu = w_mem = 1
            abs_res = math.sqrt(math.pow(resd_cpu, 2) + math.pow(resd_mem, 2))
            abs_vm = math.sqrt(math.pow(spec.total_cpu_cores(), 2) + math.pow(spec.total_memory(), 2))
            dot_product = w_cpu * resd_cpu * spec.total_cpu_cores() + w_mem * resd_mem * spec.total_memory()
            cosine = dot_product / (abs_res * abs_vm)
             
            # Check if this host is able to handle the new domain
            cpu_delta = resd_cpu - spec.total_cpu_cores()
            mem_delta = resd_mem - spec.total_memory()
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
        
        
    def placement(self, domain):
        nodelist = self.model.get_hosts(model.types.NODE)
        
        # Find active and inactive nodes
        active_nodes = []
        inactive_nodes = []
        for node in nodelist:
            if node.domains:
                active_nodes.append(node)
            else:
                inactive_nodes.append(node)
        
        # Test active nodes    
        names = self.test_nodes(domain, active_nodes)
        name = None
        if names is None: 
            name = inactive_nodes[0].name
        else:
            if DOT_PRODUCT: 
                name = names[0] # dot product
            elif COSINE:
                name = names[1] # cosine
            else:
                print 'FATAL: UNDEFINED RESULT TYPE'
        
        return name
    
        
        
