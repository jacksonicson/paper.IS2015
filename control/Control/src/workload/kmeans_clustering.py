'''
Created on Aug 28, 2013

@author: bob
'''

'''
Used to match ACF of SIS data with a set of sample ACF functions 
to find similar TSs. 
'''

from service import times_client as tc
import conf_load
import wtimes_meta as wmeta
import util
import numpy as np
import dtw
import sys
import time

dtw_cache = {}

sample_names_org = ['SIS_93_cpu', 'SIS_163_cpu', 'SIS_91_cpu', 'SIS_345_cpu']

class Element:
    def __init__(self, name, acf):
        self.name = name
        self.acf = acf
        self.total_distance = 0

class Cluster:
    def __init__(self, name, elements, centroid_element):
        self.name = name
        self.elements = elements
        self.centroid_element = centroid_element
        
    def addElement(self, element):
        self.elements.append(element)
        self.getCentroid()
        
    
    def getCentroid(self):        
        # Get new cluster mean
        for i, entry in enumerate(self.elements):
            summ = 0
            for j, test in enumerate(self.elements):
                if i == j:
                    continue
                calc = -1
                if (entry.name, test.name) in dtw_cache.keys():
                    calc = dtw_cache[(entry.name, test.name)] 
                else:  
                    calc = dtw.Dtw(entry.acf, test.acf, lambda x,y: np.abs(x - y)).calculate()
                    dtw_cache[(entry.name, test.name)] = calc
                    
                summ += calc
            entry.total_distance = summ
        
        self.elements.sort(key=lambda x: x.total_distance)
        self.centroid_element = self.elements[0]
        
cache = {}
def __acf(handle):
    name = wmeta.times_name(handle, wmeta.MUTATION_RAW)
    
    if name in cache.keys():
        return cache[name]
    
    prof = time.time() * 1000
    
    timeSeries = connection.load(name)
    _, demand = util.to_array(timeSeries)
    acf = np.array([1] + [np.corrcoef(demand[:-i], demand[i:])[0, 1] for i in range(1, 100)])
    acf = acf[1:]
    # Remove the prefix RAW_
    org_name = name
    name = name[4:]
    
    e = Element(name, acf)
    cache[org_name] = e
    
    prof = time.time() * 1000 - prof
    print 'time: %s - %i' % (name, prof)
    
    return e




def __findRightCluster(element, sample_elements, clusters):
    min_acf = sys.maxint
    cluster = None
    
    # find right cluster
    for i, sample_element in enumerate(sample_elements):
        
        calc = -1
        if (element.name, sample_element.name) in dtw_cache.keys():
            calc = dtw_cache[(element.name, sample_element.name)]
        else:
            print 'calc dtw'
            d = dtw.Dtw(element.acf, sample_element.acf, lambda x,y: np.abs(x - y))
            calc = d.calculate()
            dtw_cache[(element.name, sample_element.name)] = calc
        
        if calc < min_acf:
            min_acf = calc
            cluster = clusters[i]
    return cluster


def __search(mix, old_sample_names, sample_names, level):
    
    sample_elements = []
    clusters = []
    for sample in sample_names:
        handle = wmeta.Handle(sample, None)
        element = __acf(handle)
        sample_elements.append(element)
        cluster = Cluster(element.name, [element], element)
        clusters.append(cluster)
    
    crt = 0
    for handle in mix.handles: 
        element = __acf(handle)

        if crt > 100: 
            break
        crt += 1

        # find the right cluster
        cluster = __findRightCluster(element, sample_elements, clusters)
        cluster.addElement(element)
    
    # Terminate either if level has reached or no centroid changes from last time
    print level
    
    if level < 10 and old_sample_names != sample_names:
        old_sample_names = sample_names[:]
        print old_sample_names
        del sample_names[:]
        for cluster in clusters:
            sample_names.append(cluster.centroid_element.name)
        __search(mix, old_sample_names, sample_names, level+1)
    else:
        for cluster in clusters:
            print 'CLUSTER'
            for element in cluster.elements:
                print '  %s' % element.name

if __name__ == '__main__':
    connection = tc.connect()
    __search(conf_load.TIMES_SELECTED_MIX, [], sample_names_org, 0)
    tc.close()
