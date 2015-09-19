from logs import sonarlog
import conf_domainsize
import model
import conf_nodes
import placement
import math

# Setup Sonar logging
logger = sonarlog.getLogger('placement')

class L2(placement.PlacementBase):
    def __init__(self, model):
        super(L2, self).__init__(model)
        
    def test_nodes(self, new_domain, nodelist):
        norms = []
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
            
            # Calculate the norm
            norm = 1 * math.pow(spec.total_cpu_cores() - resd_cpu, 2) + 1 * math.pow(spec.total_memory() - resd_mem, 2)

            # Check if this host is able to handle the new domain
            cpu_delta = resd_cpu - spec.total_cpu_cores()
            mem_delta = resd_mem - spec.total_memory()
            if cpu_delta >= 0 and mem_delta >= 0:
                norms.append((node, norm, cpu_load, mem_load))
            
        # Find the node with the lowest norm that is able to host the domain
        norms.sort(key=lambda x: x[1])
        spec = conf_domainsize.get_domain_spec(new_domain.size)
        for norm in norms: 
            # Check if this host is able to handle the new domain 
            if conf_nodes.NODE_CPU_CORES < (norm[2] + spec.total_cpu_cores()) or conf_nodes.NODE_MEM < (norm[3] + spec.total_memory()):
                continue
            
            # Node found 
            return norm[0].name
        
        
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
        name = self.test_nodes(domain, active_nodes)
        if name is None: 
            name = inactive_nodes[0].name
        
        return name
        
        
