import numpy as np

def to_array(timeSeries):
    time = np.empty(len(timeSeries.elements))
    demand = np.empty(len(timeSeries.elements))
    
    for i in range(0, len(timeSeries.elements)):
        time[i] = timeSeries.elements[i].timestamp
        demand[i] = timeSeries.elements[i].value
        
    return time, demand

def to_array_collector(timeSeries, timeframe):
    time = np.empty(len(timeSeries))
    demand = np.empty(len(timeSeries))
        
    iout = 0
    for i in xrange(0, len(timeSeries)):
        test = timeSeries[i].timestamp
        if test < timeframe[0] or test > timeframe[1]:
            continue
        
        time[iout] = timeSeries[i].timestamp
        demand[iout] = timeSeries[i].value
        iout += 1
        
    time = time[0:iout]
    demand = demand[0:iout]
        
    return time, demand


def downsample_ts(ts, reduce_fn, bucketCount=24):
    '''
    Reduce the length of the time series to the length of
    the given bucket count 
    '''
    
    ts_len = len(ts)
    elements_per_bucket = ts_len / bucketCount
    
    downsampled_ts = []
    for bucket in xrange(bucketCount):
        offset_start = bucket * elements_per_bucket
        offset_end = min(ts_len, (bucket + 1) * elements_per_bucket)
        bucket_data = ts[offset_start : offset_end]
        downsampled_ts.append(reduce_fn(bucket_data))
        
    return downsampled_ts

 


