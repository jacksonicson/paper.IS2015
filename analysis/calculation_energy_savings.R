# R script to calculate the energy consumption

# Idle energy consumption [Watts]
p.idle = 160 

# Busy energy consumption [Watts]
p.busy = 270 # Watts

# Energy consumption range [Watts]
p.range = p.busy - p.idle

# Energy demand equation
p.eqn = function(utilization, dvs=1) {
  utilization = utilization / 100
  demand = p.idle + p.range * (utilization / dvs)
  return(demand)
}

# Number of servers without consolidation
servers.default = 2

# Number of servers with consolidation
servers.consolidated = 1

# Utilization of servers in default  [%]
util.default = 30

# Utilization of consolidated servers [%]
util.consolidated = servers.default / servers.consolidated * util.default

# Energy demand default scenario [Watts]
p.default = servers.default * p.eqn(util.default)

# Energy demand consolidated scenario [Watts]
p.consolidated = servers.consolidated * p.eqn(util.consolidated)

# Savings due to consolidation [%]
p.savings = round((p.default - p.consolidated) / p.default * 100, 1)

# Energy demand default scenario with DVS [Watts]
p.default.dvs = servers.default * p.eqn(util.default, 2)

# Savings due to consolidation [%]
p.savings.dvs = round((p.default.dvs - p.consolidated) / p.default.dvs * 100, 1)
