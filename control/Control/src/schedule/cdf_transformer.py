'''
Created on Oct 15, 2013

@author: bob, wolke
'''

import configuration
import csv
import json
import math
import matplotlib.pyplot as plt

parent_dir = 'cdf/raw/'
dir_names = ['instance_lifetime/', 'interval_arrivals/', 'popular_unpopular_instance_lifetime/']
meta_filename = 'meta.txt'

class MetaCDF(object):
    
    def __init__(self, filename):
        # Origin coordinates are substracted from each x and y coordinate
        self.origin_x = None
        self.origin_y = None
                
        # Pixel and unit coordinates for x
        self.low_x_scala_0 = None
        self.low_x_scala_1 = None
        self.high_x_scala_0 = None
        self.high_x_scala_1 = None
        
        # Pixel and unit coordinates for y
        self.low_y_scala_0 = None
        self.low_y_scala_1 = None
        self.high_y_scala_0 = None
        self.high_y_scala_1 = None

        # Load parameters from file        
        self.__load_parameters(filename)
        
        
    def __load_parameters(self, filename):
        # Read CSV file reader
        meta_file_reader = csv.reader(open(filename, 'r'))
        
        # Read header line 
        header_names = meta_file_reader.next()
        
        # Read single data line
        header_values = meta_file_reader.next()
        
        # Assign each attribute to the appropriate values in class
        for i, header_name in enumerate(header_names):
            if hasattr(self, header_name):
                setattr(self, header_name, float(header_values[i]))
        
        # Remove origin of all parameters
        self.low_x_scala_0 -= self.origin_x
        self.high_x_scala_0 -= self.origin_x
        self.low_y_scala_0 = self.origin_y - self.low_y_scala_0
        self.high_y_scala_0 = self.origin_y - self.high_y_scala_0
    
    
    def transform(self, pair):
        # Remove origin of the coordinate
        pair.x -= meta_info.origin_x
        pair.y = meta_info.origin_y - pair.y
        
        # Perform transformation
        pair.x = self.__transform(pair.x, self.low_x_scala_0, self.high_x_scala_0, 
                                  self.low_x_scala_1, self.high_x_scala_1, math.log10, lambda x: math.pow(10, x))
        
        pair.y = self.__transform(pair.y, self.low_y_scala_0, self.high_y_scala_0,
                                  self.low_y_scala_1, self.high_y_scala_1, lambda x:x, lambda x:x)
        
        
        return pair

    
    def __transform(self, value, low_s0, high_s0, low_s1, high_s1, trans_axis, detrans_axis):
        '''
        Transform a given x point [px] into target scale
        '''
        
        # Calculate a factor to convert fro [px] to transformed units
        # If exopnential x-scale is assumed (log as inverse function): 
        # a=\frac{x_2-x_1}{log(t_1)-log(t_2)}\frac{[px]}{[time]} 
        a = (high_s0 - low_s0) / (trans_axis(high_s1) - trans_axis(low_s1)) 
        
        # Calculate map coordinate
        # b = \frac{a}{t-x_1}[time]
        target = (value - low_s0) / a
        
        # Calculate the final time by inverse-calculating x-scale
        # If exponential x-scale is assumed
        # x = 10^{log(t1)+b}[time]
        target = trans_axis(low_s1) + target
        target = detrans_axis(target)
        
        return target


class Pair(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y

def transform_cdf_coordinates(file_name, meta_info):
    coordinates_reader = csv.reader(open(file_name, 'r'))
    coordinates = []
    
    x = 0.0
    y = 0.0
    
    for row in coordinates_reader:
        # compute absolute coordinates
        x += float(row[0])
        y += float(row[1])
        
        coordinates.append(Pair(x, y))
    
    for pair in coordinates:
        pair = meta_info.transform(pair)
    
    return coordinates


def plotCDFGraph(x_label, y_label, cdf_functions, outfilename):
    fig = plt.figure()
    subplot = fig.add_subplot(111)
    subplot.set_ylabel(y_label)
    subplot.set_xlabel(x_label)
    
    legends = []
    for legend in cdf_functions:
        legends.append(legend)
        
        x_values = []
        y_values = []
        for pair in cdf_functions[legend]:
            x_values.append(math.log(pair.x))
            y_values.append(pair.y)
        
        subplot.plot(x_values, y_values)
        
    plt.legend(legends)
    plt.show()


if __name__ == '__main__':
    x_labels = ['Instance Lifetime (min)', 'Arrival Intervals (min)', 'Instance Lifetime (min)']
    y_label = 'CDF'
    
    for i, dir_name in enumerate(dir_names):
        root_dir = parent_dir + dir_name
        metafile_lines = [line.rstrip('\n') for line in open(root_dir + meta_filename)]
        
        meta_info = MetaCDF(root_dir + metafile_lines[0] + '.csv')
        metafile_lines = metafile_lines[1:]
        
        cdf_functions = {}
        for file_name in metafile_lines:
            print root_dir + file_name + '.csv'
            coordinates = transform_cdf_coordinates(root_dir + file_name + '.csv', meta_info)
            cdf_functions[file_name] = coordinates
            
            # create map only for JSON
            y_x_dict = {}
            for pair in coordinates:
                y_x_dict[pair.y] = pair.x
            data_coordinates = json.dumps(y_x_dict, sort_keys=True)
            json_output = 'schedules/' + 'cdf_' + dir_name[:-1] + '_' + file_name + '.json'
            with open(json_output, 'w') as outfile:
                json.dump(data_coordinates, outfile)
        plotCDFGraph(x_labels[i], y_label, cdf_functions, configuration.path(x_labels[i], '.png'))
