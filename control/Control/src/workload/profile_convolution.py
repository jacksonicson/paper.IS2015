from scipy import signal
from service import times_client
from timeutil import *  # @UnusedWildImport
from workload import forecasting
import numpy as np
import sys
import util
 
EXP_SMOOTH_ALPHA = 0.9
TARGET_FREQ = minu(5)
OUTLIER_WINDOW = 5
 
def __extract_profile(time, signal, frequency, period_duration=hour(24),
                     bucket_duration=hour(1), aggregator=np.mean):
    print 'ORIGINAL FREQ: %f' % frequency
    
    # Filter out all weekdays (index 5 and 6)
    def to_weekday(value):
        day = long(long(value) / hour(24)) % 7
        return day 
    tv = np.vectorize(to_weekday)
    time = tv(time)
    indices = np.where(time < 5)
    time = np.take(time, indices)
    signal = np.ravel(np.take(signal, indices))
    
    # Calculate number of values that are in one period 
    values_per_period = period_duration / frequency
    
    # Calculate number of periods that are in the signal
    number_of_periods = len(signal) / values_per_period
    
    # Signal length has to be a multiple of values_per_period
    signal = np.resize(signal, number_of_periods * values_per_period)
    
    # Filter extreme values using a sliding window forecast
    outlier = np.ravel(np.where(signal > np.percentile(signal, 99)))
    for i in outlier:
        window = signal[max(i - OUTLIER_WINDOW, 0):i]
        if len(window) < OUTLIER_WINDOW:
            window = np.append(window, signal[-OUTLIER_WINDOW:])
        signal[i] = np.mean(window)
        
    # Reshape the signal into a 2D matrix, each row holds one period    
    signal = np.reshape(signal, (-1, values_per_period))

    # Calculate number of buckets in each period     
    number_of_buckets = period_duration / bucket_duration
    
    # Calcualte number of values for each bucket  
    values_per_bucket = values_per_period / number_of_buckets
    
    # More then 0 values per bucket
    assert values_per_bucket > 0
    
    # Cut matrix into buckets of 2D matrices
    buckets = np.hsplit(signal, number_of_buckets)
    
    # Reduce all values of each bucket to a single representant
    profile = np.empty(number_of_buckets, np.float32)
    variance = np.empty(len(buckets), np.float32)
    for i, bucket in enumerate(buckets):
        bucket = np.ravel(bucket)
        
        # Aggregation for profile
        value = aggregator(bucket)
        profile[i] = value
        
        # Variance calculation
        variance[i] = np.std(bucket)

    # Increase profile resolution
    target_period_length = period_duration / TARGET_FREQ
    scale = target_period_length / len(profile)
    profile = np.ravel(np.array(zip(*[profile for _ in xrange(scale)])))
    
    # Smooth profile slightly (remove forecast value by -1)
    _, profile, _ = forecasting.single_exponential_smoother(profile, EXP_SMOOTH_ALPHA)
    profile = np.array(profile[:-1])
    
    # Frequency of result signal
    frequency = period_duration / len(profile)
    
    print 'RESULT FREQ: %f' % frequency
    
    return frequency, profile
    

def process_trace(connection, name, cycle_time):
    timeSeries = connection.load(name)
    time, demand = util.to_array(timeSeries)
    return __extract_profile(time, demand, timeSeries.frequency, cycle_time)


def __acf(x, length=20):
    return np.array([1] + [np.corrcoef(x[:-i], x[i:])[0, 1] for i in range(1, length)])

def __period_calc(frequency, demand, time):
    # Approach is from Gmach et al. 
    # Create a copy
    demand = np.array(demand)
    
    # Filter out weekends    
    def to_weekday(value):
        day = long(long(value) / hour(24)) % 7
        return day 
    tv = np.vectorize(to_weekday)
    time = tv(time)
    indices = np.where(time < 5)
    time = np.take(time, indices)
    demand = np.ravel(np.take(demand, indices))
    
    # Calculate a periodogram
    _, ped = signal.periodogram(demand)
    indices1 = np.asarray(np.where(ped > (np.percentile(ped, 99.5)))).tolist()
                       
    # Calculate ACF
    acf = __acf(demand, 1000)[1:]
    indices2 = np.asarray(np.where(acf > np.percentile(acf, 99.5))).tolist()
    
    # Combine both indices
    indices = np.ravel(indices1)
    indices = np.append(indices, indices2)

    # Match period to hours    
    periods = []
    for index in indices:
        # Calculate period in seconds
        index *= frequency
        
        # Find hour that is the closest match to period
        best = sys.maxint
        value = None
        
        # Test 24 to 3 hours
        for h in range(24, 1, -3):
            h = hour(h)
            
            # Calc delta
            delta = abs(index - h)
            if best > delta:
                best = delta
                value = h
                
        # Add hour to periods if it doensn't exist
        if value not in periods:
            periods.append(value)

    # Get the longest period
    ret = np.max(periods)
    return ret, acf, ped
        

if __name__ == '__main__':
    import matplotlib.pyplot as plt
    
    # Connect and load TS
    connection = times_client.connect()
    ll = connection.find('RAW_O2_.*')
    
    for name in ll: 
        timeSeries = connection.load(name)
        time, demand = util.to_array(timeSeries)

        period, acf, ped = __period_calc(timeSeries.frequency, demand, time)
        
        # Calculate profile
        freq, profile = __extract_profile(time, demand, timeSeries.frequency, period, hour(1), lambda x: np.mean(x))
        freq, profile_upper = __extract_profile(time, demand, timeSeries.frequency, period, hour(1), lambda x: np.percentile(x, 95)) 
        freq, profile_lower = __extract_profile(time, demand, timeSeries.frequency, period, hour(1), lambda x: np.percentile(x, 15))

        # Plotting
        fig = plt.figure()
        folder = 'C:/temp/'
        ax = fig.add_subplot(111)
        ax.fill_between(xrange(len(profile)), profile_lower, profile_upper, interpolate=True, facecolor='lightgray', lw=0)
        ax.plot(range(len(profile)), profile)
        plt.savefig('%s/%s_profile.png' % (folder, name), dpi=30)
        plt.close()
        
        plt.plot(xrange(len(acf)), acf)
        plt.savefig('%s/%s_acf.png' % (folder, name), dpi=30)
        plt.close()
        
        plt.plot(xrange(len(demand)), demand)
        plt.savefig('%s/%s_times.png' % (folder, name), dpi=30)
        plt.close()
        
    # Close times
    times_client.close()    
