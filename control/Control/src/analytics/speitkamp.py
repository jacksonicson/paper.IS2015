from service import times_client
from workload import util
import numpy as np
import matplotlib.pyplot as plt

class TsStat():
    def __init__(self, name):
        self.name = name

def __calc_stats(con):
    stats = []
    names = con.find('RAW_SIS_.*_cpu')
    for i, name in enumerate(names): 
        print 'processing %s... (%i%%)' % (name, (i*100/len(names)))
        timeSeries = con.load(name)
        _, values = util.to_array(timeSeries)
        
        stat = TsStat(name)
        stats.append(stat)
        
        stat.mean = np.mean(values)
        stat.median = np.percentile(values, 50)
        stat.min = np.min(values)
        stat.max = np.max(values)
        stat.std = np.std(values)
        
    return stats

def __print_load_table(stats):
    values = [x.mean for x in stats]
    print 'MIN, MAX, AND MEDIAN OF -- MEAN LOAD'
    print 'MIN: %f' % np.min(values)
    print 'MEDIAN: %f' % np.median(values)
    print 'MAX: %f' % np.max(values)

def __print_variation_table(stats):
    values = [x.std for x in stats]
    print 'MIN, MAX, AND MEDIAN OF -- COEFFICIENT OF VARIATION'
    print 'MIN: %f' % np.min(values)
    print 'MEDIAN: %f' % np.median(values)
    print 'MAX: %f' % np.max(values)

def __print_utilization_table(stats):
    maxvalues = [x.max for x in stats]
    minvalues = [x.min for x in stats]
    avgvalues = [x.median for x in stats]
    
    print 'MEAN OF -- MIN, MAX, AND MEDIAN UTILIZATION'
    print 'AVG MIN: %f' % np.mean(minvalues)
    print 'AVG MEDIAN: %f' % np.mean(avgvalues)
    print 'AVG MAX: %f' % np.mean(maxvalues)
    
def __plot_hist_average_load(stats):
    values = [x.mean for x in stats]
    plt.hist(values)
    plt.savefig('C:/temp/hist.png')

if __name__ == '__main__':
    # Connect and load TS
    connection = times_client.connect()
    stats = __calc_stats(connection)
    times_client.close()
    
    __print_load_table(stats)
    __print_variation_table(stats)
    __print_utilization_table(stats)
    __plot_hist_average_load(stats)
    