'''
Created on Oct 16, 2013

@author: bob
'''

import json
import random

class CDFRandomNumber(object):
    
    def __init__(self, json_filename):
        self.json_filename = 'cdf/%s.json' % json_filename
        
        with open(self.json_filename) as data_file:
            data_coordinates = json.load(data_file)
            data_coordinates = json.loads(data_coordinates)
        
        result_map = {}
        for key in data_coordinates.keys():
            result_map[float(key)] = data_coordinates.pop(key)
        
        self.data_coordinates = result_map

            
    def get_random(self):
        # Create random number if necessary
        random_probability = random.random() 
                
        # Get a sorted list of probability keys
        probabilities = sorted(self.data_coordinates)
        max_probability = max(probabilities)
        
        # We return the highest minute in case the random probability is above the max probability in the distribution
        if max_probability <= random_probability:
            return self.data_coordinates[max_probability]
        
        # Fit best probability and interpolate result
        corresponding_min = 0
        previous_probability = 0.0
        previous_minute = 0.0
        for probability in probabilities:
            if probability >= random_probability:
                # calculate the parameters a,b from the y = ax + b so that we can compute y for
                # arbitrary x. In our case, x is the probability and y is the corresponding minute
                previous_minute = 0
                if previous_probability in self.data_coordinates:
                    previous_minute = self.data_coordinates[previous_probability]
                
                
                a = (self.data_coordinates[probability] - previous_minute) / (probability - previous_probability)
                b = self.data_coordinates[probability] - a * probability
                corresponding_min = a * random_probability + b
                return corresponding_min
                # return self.data_coordinates[probability]
            
            # Update previous probability
            previous_probability = probability
            
        # Nothing found
        return self.data_coordinates[max_probability]

if __name__ == '__main__':
    cdf_random_number = CDFRandomNumber('cdf_popular_unpopular_instance_lifetime_unpopular')
    
    out = open('C:/temp/test.csv', 'w')
    out.write('I, V\n')
    for i in range(1000):
        minute = cdf_random_number.get_random()
        line = '%i, %f' % (i, minute)
        print line
        out.write('%s\n' % line)
        
    out.close()
    print 'Done'
        
