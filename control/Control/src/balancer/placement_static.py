from logs import sonarlog
import model
import placement

# Setup Sonar logging
logger = sonarlog.getLogger('placement')

class Static(placement.PlacementBase):
    def __init__(self, model):
        super(Static, self).__init__(model)
        # make the server 0 to be the special server that has enough capacity
        self.node_index = 0
    
    def placement(self, new_domain):
        nodelist = self.model.get_hosts(model.types.NODE)
        target_node = nodelist[self.node_index].name
        logger.info('static placed new domain %s on host %s' % (new_domain.name, target_node))            
        return target_node
