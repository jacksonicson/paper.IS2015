from logs import sonarlog
import model
import random

# Setup Sonar logging
logger = sonarlog.getLogger('placement')

class PlacementBase(object):
    '''
    Base class for implementing dynamic placement logic
    '''
    
    def __init__(self, model):
        self.model = model
    
    def placement(self, domain):
        nodes = self.model.get_hosts(model.types.NODE)
        return nodes[0].name  # place everything on the first node
        
