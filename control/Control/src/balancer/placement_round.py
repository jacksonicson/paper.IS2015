from logs import sonarlog
import model
import placement

# Setup Sonar logging
logger = sonarlog.getLogger('placement')

class RoundRobin(placement.PlacementBase):
    def __init__(self, model):
        super(RoundRobin, self).__init__(model)
        self.node_index = 0
    
    def placement(self, new_domain):
        nodelist = self.model.get_hosts(model.types.NODE)
        target_node = nodelist[self.node_index].name
        self.node_index = (self.node_index + 1) % len(nodelist)        
        logger.info('round placed new domain %s on host %s' % (new_domain.name, target_node))            
        return target_node
