from fflop import filter
import matplotlib.pyplot as plt
import numpy as np

data = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 7, 14, 16, 15, 15, 14, 15, 8, 8, 12, 15, 16, 20, 19, 21, 18, 17, 16, 15, 16, 14, 15, 16, 17, 20, 20, 20, 23, 25, 27, 25, 24, 25, 25, 19, 20, 13, 14, 11, 15, 12, 13, 11, 8, 10, 7, 6, 6, 8, 4, 5, 9, 4, 9, 8, 4, 7, 10, 5, 7, 3, 5, 5, 7, 8, 11, 12, 15, 19, 20, 20, 22, 19, 17, 12, 10, 5, 4, 4, 7, 5, 6, 7, 8, 9, 8, 9, 7, 7, 6, 11, 8, 8, 6, 6, 6, 5, 7, 7, 8, 7, 6, 14, 13, 12, 13, 13, 14, 11, 7, 7, 7, 6, 7, 7, 7, 9, 7, 8, 8, 8, 6, 10, 7, 9, 10, 8, 8, 7, 10, 7, 10, 6, 14, 21, 28, 28, 27, 28, 23, 17, 13, 12, 14, 16, 17, 19, 19, 20, 19, 23, 27, 27, 27, 28, 28, 25, 21, 23, 21, 22, 26, 27, 30, 28, 29, 33, 28, 22, 24, 18, 23, 18, 21, 20, 23, 23, 21, 20, 19, 18, 16, 18, 18, 20, 23, 26, 32, 34, 37, 36, 40, 37, 37, 31, 23, 23, 18, 14, 17, 17, 17, 17, 16, 17, 14, 12, 11, 11, 9, 9, 8, 6, 7, 7, 5, 9, 8, 8, 8, 9, 8, 4, 3, 2, 3, 3, 2, 2, 2, 3, 2, 3, 2, 3, 4, 5, 10, 12, 14, 15, 14, 13, 13, 10, 9, 10, 9, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

def main(scale):
    # Add some random noise
    demand = np.array(data)
    rand = np.random.normal(loc=0, scale=scale, size=len(demand))
    demand += rand

    # Run smoother
    s0 = []
    s1 = []
    ua = []
    ul = []
    status = None
    f_t = None
    ff = filter.FlipFlop()
    for x in demand:
        forecast, status = ff.continous(float(x), status)
        s0.append(forecast)
        
        ua.append(status.ucl)
        ul.append(status.lcl)
        
        f_t = ff.continous_single_exponential_smoothed(f_t, x, 0.1)
        s1.append(f_t)
    
    # Plot original time series
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.plot(demand)
    
    # Plot filtered time series
    ax.plot(s0, lw=1, c='red')
    
    # Plot bands
    ax.fill_between(xrange(0, len(ua)), ua, ul, interpolate=True, facecolor='lightgray', lw=0)
    
    # Show plot
    plt.show()


if __name__ == '__main__':
    scales = [0.5, 1, 1.5, 2]
    for scale in scales:
        main(scale)
