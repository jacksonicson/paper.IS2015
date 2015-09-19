import numpy as np

class Status(object):
    def __init__(self, buf):
        self.f_agile = None
        self.f_stable = None
        self.b_bar = None
        self.mw = [0]
        self.x_prev = None
        self.x_bar = None
        
        self.ucl = None
        self.lcl = None
        
        self.forecast = 0
        
        self._buf = buf
        self._bufi = 0
        
    def mean(self):
        return np.mean(self.mw)

    def append(self, x):
        if len(self.mw) > self._buf:
            self.mw[self._bufi] = x
            self._bufi = (self._bufi + 1) % self._buf
        else:
            self.mw.append(x)    

class FlipFlop(object):
    def __init__(self, l=0.1, u=0.9, buf=10):
        self.l = l
        self.u = u
        self.buf = buf
    
    def continous(self, x, status=None):
        '''
        Implementation of the flip flop filter as described by Minkyong Kim and Brian Noble
        EWMA = Exponential Weighted Moving Average
        buffer = Status information that was returned by the previous call 
        '''
        
        # Initialize status
        if status is None:
            status = Status(self.buf)
        
        # Update agile and stable EWMA
        status.f_agile = self.continous_single_exponential_smoothed(status.f_agile, x, self.u)
        status.f_stable = self.continous_single_exponential_smoothed(status.f_stable, x, self.l)
        
        # Update estimated population mean \bar{x}
        status.x_bar = self.continous_single_exponential_smoothed(status.x_bar, x, 0.5)
        
        # Calculate \bar{MW}
        mw_average = status.mean()
            
        # Update upper and lower control limits 
        # (constants are given by the paper)
        ucl = status.x_bar + 3 * (mw_average / 1.128)
        lcl = status.x_bar - 3 * (mw_average / 1.128)
        status.ucl = ucl
        status.lcl = lcl
        
        # Run flip-flop logic
        if status.forecast >= lcl and status.forecast <= ucl:
            # forecast is within control limits
            forecast = status.forecast
        else:
            # Select forecast that is within control limits
            if status.f_agile >= lcl and status.f_agile <= ucl:
                forecast = status.f_agile
            else:
                forecast = status.f_stable
        
        # Update moving range calculation
        if status.x_prev != None:
            delta = abs(x - status.x_prev)
            status.append(delta)
        
        # Return status and forecast
        status.x_prev = x
        status.forecast = forecast 
        return forecast, status
    
    
    def continous_single_exponential_smoothed(self, f_t, data_t, alpha):
        # Smoothing equation (1)
        # f_t is the forecasted value for f_{t+1}
        if f_t == None: 
            return data_t
        
        f_t = alpha * data_t + (1 - alpha) * f_t
        
        return f_t


def flip_flop(samples):
    ff = FlipFlop()
    status = None
    for x in samples:
        forecast, status = ff.continous(x, status) 
    return forecast


