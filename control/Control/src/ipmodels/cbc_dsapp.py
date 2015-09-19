'''
Created on 02.06.2015

@author: Andreas
'''

from pulp import *
from numpy import empty 


###############################
### Configuration            ##
server_count = None
service_count = None
server_capacity_CPU = None
server_capacity_MEM = None
demand_cpu = None
demand_mem = None
overhead_CPU_SOURCE = None
overhead_CPU_TARGET = None
curr_allocation = None
###############################

# Resource IDs
CPU = 0
MEM = 1

# Overhead IDs
SOURCE_OVERHEAD = 0
TARGET_OVERHEAD = 1

SERVER_COST = 15

def migration_overhead(source_overhead):
    ''' We do not differentiate between the overheads for different resources
    as we are considering only CPU overhead'''
    if source_overhead:
        return overhead_CPU_SOURCE
    else:
        return overhead_CPU_TARGET

def demand(service, resource):
    if resource == CPU:
        return demand_cpu[service]
    else:
        return demand_mem[service]
    
def createVariables():
    global var_allocation
    global var_server_active
    global var_migration_slacks_SOURCE
    global var_migration_slacks_TARGET
    
    # Server active flags
    var_server_active = empty(server_count, dtype=object)
    for i in xrange(server_count):
        v = LpVariable("server%i" % i, 0, 1, LpInteger)
        var_server_active[i] = v

    # Allocation flags
    var_allocation = empty((server_count, service_count), dtype=object)
    for i in xrange(server_count): 
        for j in xrange(service_count):
            v = LpVariable("allocation%i%i" % (i, j), 0, 1, LpInteger)
            var_allocation[i, j] = v
     
    # Migration slacks
    var_migration_slacks_SOURCE = empty((server_count, service_count), dtype=object)
    var_migration_slacks_TARGET = empty((server_count, service_count), dtype=object)
    for i in xrange(server_count):
        for j in xrange(service_count):
            v_minus = LpVariable("minusMigSlack%i%i" % (i, j), 0, 1, LpInteger)
            var_migration_slacks_SOURCE[i, j] = v_minus
            
            v_plus = LpVariable("plusMigSlack%i%i" % (i, j), 0, 1, LpInteger)
            var_migration_slacks_TARGET[i, j] = v_plus
    
def setupConstraints(model):
    # Allocate all services
    for j in xrange(service_count):
        model += lpSum([var_allocation[i, j] for i in xrange(0, server_count)]) == 1.0
    
    # Capacity constraint
    for i in xrange(server_count):
        cpu_load = lpSum([demand(j, CPU) * var_allocation[i, j] +
                            migration_overhead(True) * var_migration_slacks_SOURCE[i, j] +
                            migration_overhead(False) * var_migration_slacks_TARGET[i, j]
                           for j in xrange(service_count)])
        model += cpu_load <= (var_server_active[i] * server_capacity_CPU)
         
        mem_load = lpSum([demand(j, MEM) * var_allocation[i, j] for j in xrange(service_count)])
        model += mem_load <= (var_server_active[i] * server_capacity_MEM)
    
    # Slack variables constraint
    for i in xrange(server_count):
        for j in xrange(service_count): 
            left_side_1 = (-1) * isHostServer(i, j) + var_allocation[i, j] - var_migration_slacks_SOURCE[i, j]
            model += left_side_1 <= 0.0
         
            left_side_2 = isHostServer(i, j) - var_allocation[i, j] - var_migration_slacks_TARGET[i, j]
            model += left_side_2 <= 0.0
    
def isHostServer(i, j):
    if curr_allocation[j] == i:
        return 1.0
    else:
        return 0.0

def setupObjective():
    expr = 0
    
    expr += lpSum([SERVER_COST * var_server_active[i] for i in xrange( server_count)])
    expr += lpSum([var_migration_slacks_SOURCE[i,j] for j in xrange(service_count) for i in xrange(server_count)]) 
    
    model = LpProblem("DSAPP", LpMinimize)
    model += expr
    return model                   

def getAssignment():
    global var_allocation
    assignment = {}
    
    for j in xrange(service_count):
        for i in xrange(server_count):
            if var_allocation[i, j].varValue > 0.5:
                assignment[j] = i
                break
        
    return assignment
    
def getServerCounts():
    server_counts = 0

    for i in xrange(server_count):
        if var_server_active[i].varValue > 0:
            server_counts += 1
    
    return server_counts

def AssignmentChanged(assignment1, assignment2):
    for key in assignment1:
        if assignment1[key] != assignment2[key]:
            return True
    return False

def solve(_server_count, _server_capacity_cpu, _server_capacity_mem, _demand_cpu, _demand_mem, _curr_allocation, _overhead_CPU_SOURCE, _overhead_CPU_TARGET):
    global server_count
    global service_count
    global server_capacity_CPU
    global server_capacity_MEM
    global demand_cpu
    global demand_mem
    global overhead_CPU_SOURCE
    global overhead_CPU_TARGET
    global curr_allocation
    
    server_count = _server_count
    service_count = len(_demand_cpu)
    server_capacity_CPU = _server_capacity_cpu
    server_capacity_MEM = _server_capacity_mem
    demand_cpu = _demand_cpu
    demand_mem = _demand_mem
    overhead_CPU_SOURCE = _overhead_CPU_SOURCE * server_capacity_CPU
    overhead_CPU_TARGET = _overhead_CPU_TARGET * server_capacity_CPU
    curr_allocation = _curr_allocation
         
    createVariables()
    model = setupObjective()
    setupConstraints(model) 
    model.solve(COIN(maxSeconds=20 * 60))
    
    print 'Model status:', LpStatus[model.status]
    
    # Extract results
    assignment = getAssignment()
    server_counts = getServerCounts()
    
    #return server_counts, assignment
    return server_counts, assignment

# Test program
if __name__ == '__main__':
    print "Testing DSAP plus"
    
    server_count = 6
    # One server has 6 cores
    server_capacity_CPU = 6
    server_capacity_MEM = 6
    service_count = 18
    demand_cpu = empty((service_count), dtype=float)
    demand_mem = empty((service_count), dtype=float)
    assignment = [[i, i + 1, i + 2] for i in xrange(0, service_count - 2, 3)]
    print 'First assignment:'
    print assignment
    
    curr_allocation = {}
    for j in xrange(service_count):
        for i, vm_set in enumerate(assignment):
            if j in vm_set:
                curr_allocation[j] = i
                break
    
    # A) Filling demand values with random data for testing purposes
    for j in xrange(service_count):
        demand_cpu[j] = 2
        demand_mem[j] = 2
    
    # Solve problem
    server_counts, assignment = solve(server_count, server_capacity_CPU, server_capacity_MEM, demand_cpu, demand_mem, curr_allocation, 0.08, 0.1)
    print 'Target assignment:'
    print 'Servers required: %s' % server_counts
    print assignment
    
    print "Testing DSAP plus _finished_"
    
