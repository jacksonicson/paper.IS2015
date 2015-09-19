from service import times_client
import conf_load
import util
import wtimes_meta as meta

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
    # TS name_CPU_profile_norm
    # TS name_CPU_profile_norm_modified
    handle = __get_handler(index)
    name = 'mkI_%s_profile_norm' % (handle.name)
    return __load(name)

def get_cpu_trace(index, domain_size):
    handle = __get_handler(index)
    name = 'mkI_%s_profile_norm' % (handle.name)
    return __load(name)

def get_user_profile(index, domain_size):
    # TS name_CPU_profile_user 
    # TS name_CPU_profile_user_modified
    handle = __get_handler(index)
    name = 'mkI_%s_profile_user' % (handle.name)
    return __load(name)

def get_user_profile_name(index, domain_size):
    handle = __get_handler(index)
    name = 'mkI_%s_profile_user' % (handle.name)
    return name
