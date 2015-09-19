from logs import sonarlog
import json
import strategy

# Setup logging
logger = sonarlog.getLogger('controller')

class Strategy(strategy.StrategyBase):
    
    def __init__(self, scoreboard, pump, model):
        super(Strategy, self).__init__(scoreboard, pump, model, 10 * 60, 120)
        
    def dump(self):
        print 'Dump controller configuration...'
        logger.info('Balancer Configuration: %s' % json.dumps({'name' : 'None',
                                                                 }))
    def balance(self):
        pass
    
