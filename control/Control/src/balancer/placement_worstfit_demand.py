import placement_bestfit_demand

class WorstFitDemand(placement_bestfit_demand.BestFitDemand):
    def sort(self, host_choice, _key):
        host_choice = sorted(host_choice, key = _key)
        host_choice.reverse()
        return host_choice
        
        
    