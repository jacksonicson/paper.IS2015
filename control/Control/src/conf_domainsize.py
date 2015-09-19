import clparams
import sys

# Domain size set for MKI experiments
SET_MKI = 3

# Domain size set for MKII experiments 
SET_MKII = 0
SET_MKII_CORR = 0

# Domain size set for fractional dynamic packing simulations
SET_FRACTIONAL = 2

# Domain size set for integral dynamic packing simulations
SET_INTEGRAL = 1

# Default domain size
DEFAULT = 0

###############################
# # CONFIGURATION             ##
###############################
DOMAIN_SIZES_SET = SET_MKII
###############################

# Load parameters from command line
clparams.load_parameters(sys.modules[__name__])

class MaxUserDemand(object):
    def __init__(self, name, users):
        self.name = name
        self.users = users

# Domain hardware specification
class DomainSpec(object):
    def __init__(self, cpu_cores, memory, hypervisor_memory, probability=1, 
                 clone_source=None, max_user_demand=None,
                 freq=None, cpu_corr=1, phy_cpu_cores=None):
        self._cpu_cores = cpu_cores
        self._memory = memory
        self._hypervisor_memory = hypervisor_memory
        self._probability = probability
        self._clone_source = clone_source
        self._max_user_demand = max_user_demand
        self._freq = freq
        self._cpu_corr = cpu_corr
        self._phy_cpu_cores = phy_cpu_cores
        
    def probability(self):
        return self._probability
        
    def total_cpu_cores(self):
        return self._cpu_cores
        
    def phy_cpu_cores(self):
        if self._phy_cpu_cores is None:
            return self.total_cpu_cores()
        return self._phy_cpu_cores
        
    def total_memory(self):
        return self._memory + self._hypervisor_memory
    
    def max_user_demand(self):
        return self._max_user_demand
    
    def clone_source(self):
        return self._clone_source
    
    def freq(self, freq):
        if self._freq is None:
            return freq
        return self._freq
    
    def cpu_corr(self, load):
        return min(load * self._cpu_corr, 100)


# Domain size sets with number of CPU cores
size_set = []

# Signature
# CPU Cores, Memory, Hypevisor Memory, Probability, Clone Source, Max User Demand, 
# Freq, CPU Correction Factor, Physcial CPU Cores 

# MKII experiments set 0
size_set.append([
        DomainSpec(2, 2048, 100, 0.6, 'playglassdb_v2_small',   MaxUserDemand('SMALL', 100),      75,  0.8, 2),
        DomainSpec(2, 3072, 100, 0.3, 'playglassdb_v2_medium',  MaxUserDemand('MEDIUM', 150),     75,  1.1, 2),
        DomainSpec(2, 4096, 100, 0.1, 'playglassdb_v2_large',   MaxUserDemand('LARGE', 200),      75,  1, 3)
        ])

# Integral dynamic packing simulations
size_set.append([
        DomainSpec(1, 2048, 100, 0.25),
        DomainSpec(2, 4096, 100, 0.25),
        DomainSpec(3, 6144, 100, 0.25),
        DomainSpec(4, 12288, 100, 0.25)
        ])

# Fractional dynamic packing simulations
size_set.append([
        DomainSpec(2.29, 7024.69, 100, 0.05),
        DomainSpec(1.27, 3887.67, 100, 0.05),
        DomainSpec(3.53, 10856.24, 100, 0.05),
        DomainSpec(2.49, 7663.73, 100, 0.05),
        DomainSpec(3.21, 9854.69, 100, 0.05),
        DomainSpec(3.64, 11166.75, 100, 0.05),
        DomainSpec(3.63, 11163.76, 100, 0.05),
        DomainSpec(2.27, 6971.48, 100, 0.05),
        DomainSpec(1.01, 3087.37, 100, 0.05),
        DomainSpec(3.19, 9792.80, 100, 0.05),
        DomainSpec(1.50, 4602.40, 100, 0.05),
        DomainSpec(0.05, 142.03, 100, 0.05),
        DomainSpec(3.85, 11828.27, 100, 0.05),
        DomainSpec(0.83, 2549.46, 100, 0.05),
        DomainSpec(2.94, 9017.97, 100, 0.05),
        DomainSpec(2.31, 7090.72, 100, 0.05),
        DomainSpec(0.61, 1863.09, 100, 0.05),
        DomainSpec(1.71, 5238.52, 100, 0.05),
        DomainSpec(3.61, 11082.31, 100, 0.05),
        DomainSpec(1.28, 3924.32, 100, 0.05),
        ])

# MKI experiments set
size_set.append([
        DomainSpec(2, 2048, 100, 1, 'playglassdb_v2_medium')
        ])


def count_domain_sizes():
    return len(size_set[DOMAIN_SIZES_SET])

def get_domain_size_clone_sources():
    sources = []
    for spec in size_set[DOMAIN_SIZES_SET]:
        sources.append(spec.clone_source())
    return sources
    
def get_domain_spec(domain_size=DEFAULT):
    '''
    Returns domain size configuration for a given domain size
    '''
    return size_set[DOMAIN_SIZES_SET][domain_size]

if __name__ == '__main__':
    '''
    Generates domainsize configurations for set3 (non-divisiable domain sizes) 
    '''
    count = 20  # Number of configurations to create
    cpu_cores = 4  # Number of CPU cores max for a VM
    mem = 12288  # Maximum memory for a VM
    import random
    for i in xrange(count):
        r = random.random() 
        print 'DomainSpec(%0.2f, %0.2f, 100, %0.2f),' % (r * cpu_cores, r * mem, 1.0 / float(count))
        
    
