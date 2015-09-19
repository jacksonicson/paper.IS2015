from logs import sonarlog
import model
import random
import placement

# Setup Sonar logging
logger = sonarlog.getLogger('placement')
        
class RandomPlacement(placement.PlacementBase):
    def __init__(self, model):
        super(RandomPlacement, self).__init__(model)
        
    def placement(self, domain):
        # Select a random node for placement
        nodes = self.model.get_hosts(model.types.NODE)
        selected = random.randint(0, len(nodes) - 1)
        return nodes[selected].name

