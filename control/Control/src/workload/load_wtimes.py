from service import times_client
import util
import wtimes_meta as meta
import conf_load
import conf_domainsize
import numpy as np

# Times connection
connection = times_client.connect()

def __get_handler(index):
    index = meta.get(conf_load.SCRAMBLER, index, conf_load.TIMES_SELECTED_MIX)
    return index 

def __load(name):
    timeSeries = connection.load(name)
    _, demand = util.to_array(timeSeries)
    return timeSeries.frequency, demand

##################################################################

def count():
    return len(conf_load.TIMES_SELECTED_MIX.handles)

def get_cpu_profile(index, domain_size):
    handle = __get_handler(index)
    name = meta.times_name(handle, meta.MUTATION_PNORM, conf_load.TIMES_SELECTED_MIX)
    return __load(name)

def get_cpu_trace(index, domain_size):
    # Load cpu profile
    freq, ts = get_cpu_profile(index, domain_size)
    
    # Upscale
    target_freq = 3
    scale = freq / target_freq
    long_ts = np.ravel(np.array(zip(*[ts for _ in xrange(scale)])))
        
    # Generate random noise
    noise = np.random.standard_normal(len(long_ts))
    noise = np.random.random_sample(len(long_ts)) - 0.5
    noise = np.random.lognormal(mean=1, sigma=0.5, size=len(long_ts))-2
    noise = noise * 7
    
    # Add random noise on time series
    long_ts = np.array(noise) + np.array(long_ts)
    long_ts[long_ts < 0] = 0
    long_ts[long_ts > 100] = 100
    
    return target_freq, long_ts


def get_user_profile(index, domain_size):
    handle = __get_handler(index)
    size = conf_domainsize.get_domain_spec(domain_size).max_user_demand()
    name = meta.times_name(handle, meta.MUTATION_PUSER, conf_load.TIMES_SELECTED_MIX, size)
    return __load(name)

def get_user_profile_name(index, domain_size):
    handle = __get_handler(index)
    
    if domain_size is not None:
        if domain_size < conf_domainsize.count_domain_sizes():
            size = conf_domainsize.get_domain_spec(domain_size).max_user_demand()
        else:
            print 'WARN: No valid user workload profile for given domain size'
            size = None
        
    name = meta.times_name(handle, meta.MUTATION_PUSER, conf_load.TIMES_SELECTED_MIX, size)
    return name
