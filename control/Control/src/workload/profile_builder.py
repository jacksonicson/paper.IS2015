from schedule import schedule_builder
from service import times_client as tc
from times import ttypes
import conf_load
import numpy as np
import profile_convolution
import profile_modifier
import profile_sampleday
import wtimes_meta as wmeta
import conf_domainsize

# Do not write TS to sonar
DRY_RUN = False

def __write_profile(name, ts, frequency, overwrite=True):
    # Check if the profile exists
    if len(tc.connection().find(name)) > 0:
        # Double check if it is allowed to overwrite profiles in Times
        if overwrite:
            tc.connection().remove(name)
        else:
            print 'WARNING - will not overwrite profile %s' % name
            return
        
    # Create a new ts
    print '    writing profile handles %s' % (name)
    tc.connection().create(name, frequency)
    
    # Crete elements array
    elements = []
    for i in xrange(len(ts)):
        item = ts[i]
        
        element = ttypes.Element()
        element.timestamp = i * frequency
        element.value = item 
        elements.append(element)

    # Append elements to ts
    tc.connection().append(name, elements)

def __store_profile_yarns(mix, handle, normalizing_value, profile, profile_frequency):
    # 1) RAW profile (e.g. for plotting)
    raw_profile = np.array(profile)
    if not DRY_RUN:
        __write_profile(wmeta.times_name(handle, wmeta.MUTATION_PRAW, mix), raw_profile, profile_frequency)
    
    # 2) NORMALIZED profile (normalized with the set maximum, see above) (e.g. to feed into SSAPv)
    maxval = float(normalizing_value[handle.htype.id])
    profile /= maxval
    norm_profile = np.array(profile)
    norm_profile[norm_profile > 1] = 1
    norm_profile *= 100  # Times does not support float values
    if not DRY_RUN:
        __write_profile(wmeta.times_name(handle, wmeta.MUTATION_PNORM, mix), norm_profile, profile_frequency)
    
    # 3) Store USER profiles (-> e.g. for Rain workload driver)
    
    for size in xrange(conf_domainsize.count_domain_sizes()):
        size = conf_domainsize.get_domain_spec(size).max_user_demand()
        user_profile = profile * size.users
        user_profile = np.array(user_profile)
        user_profile += 5
        user_profile_frequency = profile_frequency / (wmeta.CYCLE_TIME / schedule_builder.EXPERIMENT_DURATION)
        user_profile_name = wmeta.times_name(handle, wmeta.MUTATION_PUSER, mix, size)
        print 'FREQ - USER YARN: %s @ %f' % (user_profile_name, user_profile_frequency)
        if not DRY_RUN:
            __write_profile(user_profile_name, user_profile, user_profile_frequency)


def __get_normalizing_value(handles):
    # Holds set maximum value for each handle type
    type_max = {}
    
    # Get maximum for each set (key is set_id)
    for handle in handles:
        if type_max.has_key(handle.htype.id) == False:
            type_max[handle.htype.id] = []
            
        type_max[handle.htype.id].extend(handle.profile)
            
    for key in type_max.keys():
        type_max[key] = handle.htype.max(type_max[key])
            
    return type_max


def __build_modified_profiles(mix):
    for handle in mix.handles:
        print 'processing modified profile %s ...' % (handle.name)
        
        # Load TS
        ts_name = wmeta.times_name(handle, wmeta.MUTATION_PNORM, mix)

        # Modify CPU normal profile     
        profile = profile_modifier.process_trace(tc.connection(), ts_name,
                                                            handle.modifier, handle.additive,
                                                            handle.scale, handle.shift)
        
        # Attach profile to handle
        handle.profile_frequency, handle.profile = profile
        
    # Store profiles
    for handle in mix.handles:
        profile = np.array(handle.profile)
        profile_frequency = handle.profile_frequency
        
        for size in xrange(conf_domainsize.count_domain_sizes()):
            size = conf_domainsize.get_domain_spec(size).max_user_demand()
            user_profile = (profile / 100.0) * size.users
            profile_frequency = profile_frequency / (wmeta.CYCLE_TIME / schedule_builder.EXPERIMENT_DURATION)
            user_profile = np.array(user_profile)
            user_profile += 5
            if not DRY_RUN:
                print 'storing modified profile %s ...' % (handle.name)
                __write_profile(wmeta.times_name(handle, wmeta.MUTATION_PUSER, mix), user_profile,
                                profile_frequency)


def __build_sampleday(mix, handles):
    # Build profiles from sample days
    for handle in handles:
        print 'processing sample day %s ...' % (handle.name)
        profile = profile_sampleday.process_trace(tc.connection(), wmeta.times_name(handle, wmeta.MUTATION_RAW),
                                                  wmeta.CYCLE_TIME, handle.htype.day)
        
        # Attach profile to handle
        handle.profile_frequency, handle.profile = profile
        
    # Max value in each set of TS
    normalizing_value = __get_normalizing_value(handles)

    # Store profiles
    for handle in handles:
        print 'storing sample day %s ...' % (handle.name)
        __store_profile_yarns(mix, handle, normalizing_value, handle.profile, handle.profile_frequency)
 

def __build_convolutions(mix, handles):
    # Build profiles by convolution
    for handle in handles:
        print 'processing convolution: %s ...' % (handle.name)
        profile = profile_convolution.process_trace(tc.connection(), wmeta.times_name(handle, wmeta.MUTATION_RAW),
                                                    wmeta.CYCLE_TIME)
        
        # Attach profile to handle
        handle.profile_frequency, handle.profile = profile
        
    # Get normalizing value for each handle type
    normalizing_value = __get_normalizing_value(handles)

    # Store profiles
    for handle in handles:
        print 'storing convolution: %s ...' % (handle.name)
        __store_profile_yarns(mix, handle, normalizing_value, handle.profile, handle.profile_frequency)
        

def __build_profiles(mix):
    sampleday = []
    convolution = []
    for handle in mix.handles: 
        if handle.htype.day != None:
            sampleday.append(handle)
        else:
            convolution.append(handle)
            
    print 'Build sample days %i' % (len(sampleday))
    __build_sampleday(mix, sampleday)
    
    print 'Build profiles %i' % (len(convolution))
    __build_convolutions(mix, convolution)

    if mix.modified: 
        print 'Building modified %i' % (len(mix.handles))
        __build_modified_profiles(mix) 
    
if __name__ == '__main__':
    connection = tc.connect()
    __build_profiles(conf_load.TIMES_SELECTED_MIX)
    tc.close()
