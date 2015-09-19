# Load packages
library("plyr")
library("xtable")
library("ggplot2")
library("iterators")
library("foreach")

# Load data
data = read.csv(file='data - experiments.csv', sep=",", head=T, stringsAsFactors=FALSE)

# Filter out empty and invalid lines
data = data[data$Status == 'ok',]

# Rename controllers based on Kendal notation used in the paper
build.controller.name = function(row) {
  demand = 'R'
  if(grepl("Demand", row['Placement.Controller']))
    demand = 'D'  
  
  placement = ''
  switch(sub('Demand', '', row['Placement.Controller']), 
         DotProduct = {
           placement = 'DP'
         }, 
         L2 = {
           placement = 'L2'
         },
         FirstFit = {
           placement = 'FF'
         }, 
         BestFit = {
           placement = 'BF'
         }, 
         WorstFit = {
           placement = 'WF'
         }, 
         Random = {
           placement = 'RD'
         }, 
         {
           placement = sub('Demand', '', row['Placement.Controller'])
         }
  )
  
  reallocation = ''
  switch(row['Reallocation.Controller'],
         KMControl = {
           reallocation = 'KM'
         },
         TControl = {
           reallocation = 'TC'
         },
         None = {
           reallocation = '--'
         },
         DSAPP = {
           reallocation = 'DP'
         }
  )
  str = sprintf("%s/%s/%s", demand, placement, reallocation)
  return(str)
}

# Apply full controller name
data$CONTROLLER = apply(data, 1, build.controller.name)

# Function decides whether a controller was considered good or bad
# based on simulations
is.good = function(controller.name)
{
  switch(controller.name,
         "D/FF/KM" = {
           return("+")
         },
         "R/WF/KM" = {
           return("-")
         },
         "R/WF/TC" = {
           return("-")
         },
         "D/WF/--" = {
           return("+")
         },
         "D/L2/KM" = {
           return("+")
         }
  )
  
  print(sprintf("%s is undefined", controller.name))
  return("UNDEFINED")
}

# Aggregate data by controller and schedule
data$groupby = sprintf('%s.%s', data$Placement.Controller, data$Reallocation.Controller)

# Group all instances of the same schedule configuration
# (e.g. 20100, 20101, 20102, 20103 are all the same schedule configuration 20100)
data$gschedule = floor(data$Schedule / 100) * 100


# Split data frame by 'groupby' and 'gschedule' and process each block by this function
result = ddply(data, c('groupby', 'gschedule'), function(ds) {
  # Helper functions
  # Calculate delta between max and min value in percentage of max value
  delta = function(values) {
    return((1-(min(values) / max(values))) * 100)
  }
  
  # Calculate results
  ds.eval = is.good(ds[1,]$CONTROLLER)
  
  ds.controller = as.character(ds[1,]$CONTROLLER)
  ds.schedule = as.character(ds[1,]$gschedule)
  
  ds.server.count = mean(ds$MEAN.server.count)
  ds.server.count.sd = sd(ds$MEAN.server.count)
  
  ds.max.server.count = mean(ds$MAX.server.count)
  ds.max.server.count.sd = sd(ds$MAX.server.count)
  
  ds.server.cpu.load = mean(ds$MEAN.server.CPU.utilization)
  ds.server.mem.load = mean(ds$MEAN.server.MEM.utilization)
  
  ds.avg.resp.time = mean(ds$MEAN.operations.response.time)
  ds.avg.resp.time.sd = sd(ds$MEAN.operations.response.time)
  
  ds.max.resp.time = mean(ds$MAX.operations.response.time)
  ds.max.resp.time.info = delta(ds$MAX.operations.response.time)
  
  ds.ops = mean(ds$operations.per.second)
  ds.ops.info = delta(ds$operations.per.second)
  
  ds.rtime.thr.violations = mean(ds$operations.response.time.threshold.violations)
  ds.rtime.thr.violations.info = delta(ds$operations.response.time.threshold.violations)
  
  ds.failed.operations = mean(ds$FAILED.operations.count)
  ds.total.operations = mean(ds$Total.seen.operations.count)
  
  ds.live.migrations = mean(ds$live.migrations.count)
  ds.live.migrations.min = min(ds$live.migrations.count)
  ds.live.migrations.max = max(ds$live.migrations.count)
  
  # Service level calculation
  # ds.sla = (1-(ds.failed.operations + ds.rtime.thr.violations) / ds.total.operations) * 100
  ds.sla = (1 - (ds$FAILED.operations.count + ds$operations.response.time.threshold.violations) / ds$Total.seen.operations.count) * 100
  ds.sla.mean = min(ds.sla)
  ds.sla.sd = sd(ds.sla)
  
  
  # Result data frame with only one row
  res = data.frame(
          Eval  = ds.eval, 
          
          Controller=ds.controller, 
          Schedule=ds.schedule, 
          
          Servers = sprintf('%s (%s)', formatC(round(ds.server.count, 2), format="f", digits=2), formatC(round(ds.server.count.sd,2), format="f", digits=2)),
          
          Max.Servers= sprintf('%s (%s)', formatC(round(ds.max.server.count, 2), format="f", digits=2), formatC(round(ds.max.server.count.sd,2), format="f", digits=2)),
          
          CPU=round(ds.server.cpu.load,1),
          MEM=round(ds.server.mem.load,1),
          
          RTime = sprintf('%s (%s)', formatC(round(ds.avg.resp.time, 2), format="f", digits=2), formatC(round(ds.avg.resp.time.sd,2), format="f", digits=2)),
  
          Max.Rtime=round(ds.max.resp.time, 0), 
             
          # Ops=render(ds.ops, ds.ops.info),
          # Thr.Viol=render(ds.rtime.thr.violations, ds.rtime.thr.violations.info),
             
          # FOps=round(ds.failed.operations, 0),
             
          Total.Ops=round(ds.total.operations, 0),
             
          Mig=sprintf('%s [%s/%s]', 
                      formatC(round(ds.live.migrations, digits=0), width=2, flag="0"), 
                      formatC(round(ds.live.migrations.min,0), width=2, flag="0"),
                      formatC(round(ds.live.migrations.max,0), width=2, flag="0")),
             
          # SQ=sprintf('%s', round(ds.sla, 2))
          SQ=sprintf('%s (%s)', formatC(round(ds.sla.mean, 2), format="f", digits=2),
                     formatC(round(ds.sla.sd,3), format="f", digits=3))
          )
  
  return(res)
})

# Remove columns 'groupby' and 'gschedule' form result
result = subset(result, select=-c(groupby, gschedule))

# Sort results
result = result[with(result, order(Schedule, Eval, Controller)),]

# Builds a dense summary table over all experimental results
dense.summary = function() {
  res = ddply(data, c('CONTROLLER'), function(sf) {
    sd.mean = mean(sf$MEAN.server.count)
    sd.sd = sd(sf$MEAN.server.count)
    sd.delta = max(sf$MEAN.server.count) - min(sf$MEAN.server.count)
    
    mig.mean = mean(sf$live.migrations.count)
    mig.sd = sd(sf$live.migrations.count)
    mig.delta = max(sf$live.migrations.count) - min(sf$live.migrations.count)
    
    sf = data.frame(sd.mean = sd.mean,
                    sd.sd = sd.sd,
                    sd.delta = sd.delta,
                    
                    mig.mean = mig.mean,
                    mig.sd = mig.sd,
                    mig.delta = mig.delta)
    return(sf)
  })
  
  return(res)
}

dense.summary.table = dense.summary() 
dense.summary.table = dense.summary.table[with(dense.summary.table, order(sd.mean)),]


# Builds a MRR (mean reciprocal rank) ranking table for all controllers
mrr.ranking = function(data, metrics=c('MEAN.server.count', 'MAX.server.count', 'live.migrations.count')) {
  # Calculate controller positions
  pos.unique = function(x, name) {
    w = unique(x[[name]])
    w = w[order(w)]
    ranks = sapply(x[[name]], function(x) {
      # Get ranking
      return(which(w == x))
    })
    
    # ranks = ranks / max(ranks) # noramlize ranks [0,1]
    x[[sprintf("%s.pos", name)]] = ranks
    return(x)
  }
  
  POS_METHOD = pos.unique
  sapply(metrics, function(metric) {
    data <<- ddply(data, 'Schedule', POS_METHOD, metric)
  })
  
  # Generate a new data frame for a list with one row per controller
  controllers = as.data.frame(unique(data$CONTROLLER))
  colnames(controllers) = c("CONTROLLER")
  
  # Assign a ranking on each controllr
  table = ddply(controllers, c("CONTROLLER"), function(controller) {
    # For all metrics
    ts = sapply(metrics, function(metric) {
      metric = sprintf("%s.pos", metric)
      s = sum(
        sapply(data[data$CONTROLLER == controller[1,1],][[metric]], function(x) {1/x})
      )
      return(s)
    })
    
    mrr = sum(ts) / (length(unique(data$Schedule)) * length(metrics))
    controller$rank = mrr
    return(controller)
    
  })
  
  table = table[with(table, order(-rank)),]
  return(table)
}



