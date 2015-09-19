import conf_load

# Import modules according to the load profile source definition
wrap = None
if conf_load.LOAD_SOURCE == 'sonar':
    import load_sonar
    wrap = load_sonar
elif conf_load.LOAD_SOURCE == 'times':
    import load_wtimes
    wrap = load_wtimes
elif conf_load.LOAD_SOURCE == 'times_MKI':
    import load_wtimes_MKI
    wrap = load_wtimes_MKI

'''
Wrapper functions (interface) around the load profile modules 
'''

def count():
    return wrap.count()

def get_cpu_profile(index, domain_size):
    return wrap.get_cpu_profile(index, domain_size)

def get_cpu_trace(index, domain_size):
    return wrap.get_cpu_trace(index, domain_size)

def get_user_profile(index, domain_size):
    return wrap.get_user_profile(index, domain_size)

def get_user_profile_name(index, domain_size):
    return wrap.get_user_profile_name(index, domain_size)