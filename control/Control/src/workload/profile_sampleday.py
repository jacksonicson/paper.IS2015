from service import times_client
from timeutil import hour, minu
import numpy as np
import util

def __to_weekday(value):
    day = long(long(value) / hour(24)) % 7
    return day
 
PERCENTILE_EXTREME_VALUES = 99
 
def __sample_day(time, signal, sampling_frequency, period_duration=hour(24), period=1):
    # Remove Weekends/Sundays
    tv = np.vectorize(__to_weekday)
    time = tv(time)
    indices = np.where(time < 5)
    time = np.take(time, indices)
    signal = np.ravel(np.take(signal, indices))
    
    # Counters  
    elements_per_period = period_duration / sampling_frequency
    periods = len(signal) / elements_per_period
    signal = np.resize(signal, periods * elements_per_period)

    # Filter extreme values using a sliding window forecast
    outlier = np.ravel(np.where(signal > np.percentile(signal, 99)))
    for i in outlier:
        window = signal[max(i - 5, 0):i]
        if len(window) < 5:
            window = np.append(window, signal[-5:])
        signal[i] = np.mean(window)

    # Reshape the signal (each profile in its on row)    
    signal = np.reshape(signal, (-1, elements_per_period))
    
    # Extract signal of one profile 
    profile = signal[period]
    
    # Establish frequency of 5 minutes
    target_bucket_count = period_duration / minu(5)
    factor = target_bucket_count / elements_per_period
    profile = np.ravel(np.array(zip(*[profile for _ in xrange(factor)])))

    # Single exponential signal smother 
    # profile = forecasting.single_exponential_smoother(profile, 0.9)[1] 
    
    # Calculate frequency
    frequency = period_duration / len(profile)
    
    return frequency, profile
    

def process_trace(connection, name, cycle_time, day):
    timeSeries = connection.load(name)
    time, demand = util.to_array(timeSeries)        
    return __sample_day(time, demand, timeSeries.frequency, cycle_time, period=day)

if __name__ == '__main__':
    import matplotlib.pyplot as plt
    
    # Connect with Times
    connection = times_client.connect()
    
    # Download TS
    timeSeries = connection.load('RAW_SIS_299_cpu')
    print timeSeries
    
    time, demand = util.to_array(timeSeries)
    signal, freq = __sample_day(time, demand, timeSeries.frequency, hour(24), 4)
        
    # Plotting
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.plot(signal)
    plt.show()
    print freq
    
