from timeutil import *  # @UnusedWildImport
import numpy as np
import util

class Element(object):
    '''
    Define an workload modification element which starts at start minutes,
    ends at end minutes has a height in absolute percfent and a top width:
         topWidth
       +----------+
       |          |
       |          | height
    ---+          +-----
     start       end
    '''
    
    def __init__(self, start, width, height, top_width=None):
        if top_width == None:
            top_width = width
        
        self.start = start
        self.width = width
        self.height = height
        self.top_width = top_width

MOD0 = [
        Element(hour(0), hour(4), 50),
        Element(hour(4), hour(1), 10),
        Element(hour(5), hour(6), 30)
        ]

MOD1 = [
        Element(hour(3), hour(3), 80),
        Element(hour(7), hour(3), 40),
        Element(hour(10), hour(4), 70)
        ]

MOD2 = [
        Element(hour(0), hour(3), 20),
        Element(hour(9), hour(3), 90),
        Element(hour(13), hour(2), 70),
        Element(hour(15), hour(6), 30),
        Element(hour(21), hour(3), 20),
        ]

MOD3 = [
        Element(hour(8), hour(1), 30),
        Element(hour(9), hour(1), 30),
        Element(hour(10), hour(2), 50),
        Element(hour(12), hour(2), -20),
        Element(hour(14), hour(1), -30),
        Element(hour(15), hour(1), -10),
        ]

MOD4 = [
        Element(hour(0), hour(8), 5),
        Element(hour(8), hour(10), 50),
        Element(hour(18), hour(6), 10),
        ]

MOD5 = [
        Element(hour(3), hour(3), 15),
        Element(hour(10), hour(3), 150),
        Element(hour(15), hour(3), -20),
        ]

MOD6 = [
        Element(hour(3), hour(3), 20),
        Element(hour(8), hour(10), -10),
        Element(hour(18), hour(4), 30),
        ]

MOD7 = [
        Element(hour(1), hour(3), -10),
        Element(hour(7), hour(3), -50),
        Element(hour(10), hour(8), -20),
        Element(hour(18), hour(3), 60),
        Element(hour(21), hour(3), 30),
        ]

MOD8 = [
        Element(hour(0), hour(8), 5),
        Element(hour(8), hour(6), 60),
        Element(hour(16), hour(3), 10),
        Element(hour(19), hour(3), -20),
        ]

MOD9 = [
        Element(hour(1), hour(3), +30),
        Element(hour(7), hour(3), -50),
        Element(hour(10), hour(8), -20),
        Element(hour(18), hour(3), 60),
        Element(hour(21), hour(3), 30),
        ]

def __generate_mod_ts(demand, modification, interval_length):
    result = np.zeros((len(demand),))
    
    for element in modification:
        i = lambda t: int(t / interval_length)
        i_start = i(element.start)
        i_end = i(element.start + element.width)
        result[i_start : i_end] = element.height

    # Smoothing
    window = 20
    weights = np.repeat(1.0, window) / window
    result = np.convolve(result, weights)[0:-1 * window + 1 ]
    
    mu, sigma = 0, 2
    a = np.random.normal(mu, sigma, len(demand))
    result += a
    
    # Divide for multiplication
    result /= 100.0
    
    return result

def __generate_TS(demand, modification, interval_length, additive=0):
    result = __generate_mod_ts(demand, modification, interval_length)
    
    # Apply result to the demand curve by multiplication
    demand += demand * result + additive * result
    return demand
    
def __stretch(demand, f=1.0):
    f_start = int((len(demand) - (len(demand) / f)) / 2)
    stretch = np.zeros(len(demand)) 
    for i in xrange(len(demand)):
        stretch[i] = demand[f_start + int(i / f)]
        
    return stretch
    
def __shift(demand, interval_length, s=0.0):
    i = lambda t: int(t / interval_length)
    s = i(s)
    if s > 0:
        print 'shift right'
        l = len(demand)
        tmp = np.concatenate((demand[-s:], demand[:l - s]))
        return tmp
    elif s < 0:
        print 'shift left'
        l = len(demand)
        s = abs(s)
        tmp = np.concatenate((demand[s:], demand[:s]))
        return tmp
    else:
        return demand
        
    
def __scale(demand, f=1.0):
    demand *= f
    return demand
    
def __limit(demand, limit=100):
    exp = demand > limit
    demand[exp] = 100
    return demand
    
def __add_modifier(time, demand, interval, modifier, _additive, _scale, _shift):
    demand = __generate_TS(demand, modifier, interval, _additive)
    demand = __shift(demand, interval, _shift)
    demand = __stretch(demand, _scale[0])
    demand = __scale(demand, _scale[1])
    
    return __limit(demand)

def process_trace(connection, name, modifier, additive, scale, shift):
    timeSeries = connection.load(name)
    time, demand = util.to_array(timeSeries)
    interval = timeSeries.frequency
    return timeSeries.frequency, __add_modifier(time, demand, interval, modifier, additive, scale, shift)


if __name__ == '__main__':
    import matplotlib.pyplot as plt
    
    modifications = [MOD0, MOD1, MOD2, MOD3, MOD4, MOD5,
                     MOD6, MOD7, MOD8, MOD9]
    
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.set_xlabel('Time in minutes')
    ax.set_ylabel('Change factor')
        
    i_mix = 0
    for mod in modifications:
        i_mix += 1
        demand = np.zeros(288)
        result = __generate_mod_ts(demand, mod, minu(5))
        ax.plot(range(0, len(result) * 5, 5), result, linewidth=0.7, label='MIX%i' % i_mix)
    
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels)
        
    # plt.show()
    plt.savefig('C:/temp/convolution/modifiers.pdf')
    plt.savefig('C:/temp/convolution/modifiers.png') 
