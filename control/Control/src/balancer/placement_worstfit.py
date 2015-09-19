import placement_bestfit

class WorstFit(placement_bestfit.BestFit):
    def __init__(self, model):
        super(WorstFit, self).__init__(model)
    
    def sort(self, host_choice, _key):
        host_choice = sorted(host_choice, key = _key)
        host_choice.reverse()
        return host_choice
        
        
    