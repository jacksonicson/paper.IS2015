library(plyr)
library(xtable)
library(ggplot2)
library(RColorBrewer)
library(reshape)
library(MASS)
library(knitr)
library(gridExtra)
library(plyr)
library(extrafont)
library(stringr)
library(tum)

# Load fonts
if(exists('fonts.loaded') == FALSE)
{
  fonts.loaded = TRUE
  loadfonts()
}

# Load data file
data = read.csv(file="cbc_all.csv", sep="\t", head=T)
# data = read.csv(file="c:/temp/verify_sim.csv", sep="\t", head=T)

# Build controller names
build.controller.name = function(row) {
  demand = 'R'
  if(grepl("Demand", row['STRATEGY_PLACEMENT']))
    demand = 'D'  
  
  placement = ''
  switch(sub('Demand', '', row['STRATEGY_PLACEMENT']), 
         dotProduct = {
           placement = 'DP'
         }, 
         l2 = {
           placement = 'L2'
         },
         firstFit = {
           placement = 'FF'
         }, 
         bestFit = {
           placement = 'BF'
         }, 
         worstFit = {
           placement = 'WF'
         }, 
         random = {
           placement = 'RD'
         }
  )
  
  reallocation = ''
  switch(row['STRATEGY_REALLOCATION'],
         kmcontrol = {
           reallocation = 'KM'
         },
         tcontrol = {
           reallocation = 'TC'
         },
         None = {
           reallocation = '--'
         },
         dsapp = {
           reallocation = 'DP'
         }
  )
  str = sprintf("%s/%s/%s", demand, placement, reallocation)
  return(str)
}

# Check if controller in a row is demand based
is.demand = function(row) {
  if(grepl("Demand", row['STRATEGY_PLACEMENT']))
    return(TRUE)
  return(FALSE)
}

# Check if controller in a row is dynamic
is.dynamic = function(row) {
  if(row['STRATEGY_REALLOCATION'] == 'None')
    return(FALSE)
  return(TRUE)
}

# Apply full controller name
data$CONTROLLER = apply(data, 1, build.controller.name)

# Apply status flags for clustering
data$DEMAND = apply(data, 1, is.demand)
data$DYNAMIC = apply(data, 1, is.dynamic)

# Add a combined controller name
#data$CONTROLLER = sprintf("%s/%s", data$STRATEGY_PLACEMENT, data$STRATEGY_REALLOCATION)

# List of schedule ids
schedule_ids = unique(data$SCHEDULE_ID)

# Placement strategies
strategies.placement = unique(data$STRATEGY_PLACEMENT)

# Reallocation strategies
strategies.reallocation = unique(data$STRATEGY_REALLOCATION)

# All metrics
ALL_METRICS = c('avg..srv..count', 'max..servers', 'Migrations')

# Calculates position of all controllers for one schedule
# x is a subset of data with the same schedule id
# name is the metric that is used to rank controllers (avg, max server count, migrations, ...)
pos.all = function(x, name) {
  x = x[with(x, order(x[[name]])),]
  ranks = 1:nrow(x)
  
  # ranks = ranks / max(ranks) # noramlize ranks [0,1]
  x[[sprintf("%s.pos", name)]] = ranks
  return(x)
}

# The same as pos.all but if two controllers performed equally good
# they get the same ranking
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

# Calculate controller positions for different metrics
POS_METHOD = pos.unique
data = ddply(data, 'SCHEDULE_ID', POS_METHOD, 'max..servers')
data = ddply(data, 'SCHEDULE_ID', POS_METHOD, 'avg..srv..count')
data = ddply(data, 'SCHEDULE_ID', POS_METHOD, 'Migrations')

# Average for each controller over all schedules
rank.AVG = function(metric) {
  # Generate a new data frame for a list with one row per controller
  controllers = as.data.frame(unique(data$CONTROLLER))
  colnames(controllers) = c("CONTROLLER")
  
  # Calculate rank of each controller
  controllers = ddply(controllers, c("CONTROLLER"), function(controller) {
    
    m = mean(data[data$CONTROLLER == controller[1,1],][[metric]])
    s = sd(data[data$CONTROLLER == controller[1,1],][[metric]])
    controller$rank = sprintf("%.2f (%.2f)", m, s)
    return(controller)
  })
  
  return(controllers)
}

# MRR ranking of each controller over all schedules
rank.MRR = function(metrics) {
  # Generate a new data frame for a list with one row per controller
  controllers = as.data.frame(unique(data$CONTROLLER))
  colnames(controllers) = c("CONTROLLER")
  
    
  # Calculate rank of each controller
  controllers = ddply(controllers, c("CONTROLLER"), function(controller) {
    ts = sapply(metrics, function(metric) {
      metric = sprintf("%s.pos", metric)
      s = sum(
        sapply(data[data$CONTROLLER == controller[1,1], ][[metric]], function(x) {1/x})
        )
      return(s)
    })
    mrr = sum(ts) / (length(unique(data$SCHEDULE_ID)) * length(metrics))
    controller$rank = mrr
    return(controller)
  
  })
  
  return(controllers)
}

# COUNT ranking of each controller over all schedules
rank.COUNT = function(metrics) {
  # Generate a new data frame for a list with one row per controller
  controllers = as.data.frame(unique(data$CONTROLLER))
  colnames(controllers) = c("CONTROLLER")
  
  # Calculate rank of each controller
  controllers = ddply(controllers, c("CONTROLLER"), function(controller) {
    
    # Get list of rankings for this controller
    ts = sapply(metrics, function(metric) {
      set = data[data$CONTROLLER == controller[1,1], ][[metric]]
      return(set)
    })
    ranks = melt(ts)$value
    controller$rank = mean(ranks)
    return(controller)
    
  })
  
  return(controllers)
}



# Builds a table of controllers and their rankings given by the 
# ranking funktion in the parameter and a set of metrics
# Example: build.rank.table(rank.MRR, c('avg..srv..count', 'Migrations'))
build.rank.table = function(method, metrics) {
  controllers = as.data.frame(unique(data$CONTROLLER))
  colnames(controllers) = c("CONTROLLER")
  
  # Individual rank average
  sapply(metrics, function(metric) {
    result = method(metric)
    colnames(result) = c('CONTROLLER', sprintf('MRR.%s',metric))
    controllers <<- merge(result, controllers, by.x='CONTROLLER', by.y='CONTROLLER')
  })
  
  # Individual concrete value averages
  sapply(metrics, function(metric) {
    result = rank.AVG(metric)
    colnames(result) = c('CONTROLLER', sprintf('AVG.%s',metric))
    controllers <<- merge(result, controllers, by.x='CONTROLLER', by.y='CONTROLLER')
  })
    
  # Aggregated metric
  result = method(metrics)
  controllers = merge(result, controllers, by.x='CONTROLLER', by.y='CONTROLLER')
  
  # Sort controllers by their ranking
  controllers = controllers[with(controllers, order(-rank)),]
  
  # Sort columns of data frame
  metrics = c('CONTROLLER', 'rank', sapply(metrics, function(x) { return(sprintf("MRR.%s", x)) }),
                                    sapply(metrics, function(x) { return(sprintf("AVG.%s", x)) }))
  controllers = controllers[,metrics]
  
  return(controllers)
}

sim_mrr_results = build.rank.table(rank.MRR, c('avg..srv..count', 'max..servers', 'Migrations'))



# Builds a heatmap over all controllers and schedule instances for a given metric.
# Saturation is determined by the actual metric values, *not* rankings. 
# Example: heatmap.mrr('avg..srv..count')
heatmap.mrr = function(metric, corr=0, mark=function(re, p) {}) {
  # Calculate ranking and attach it to data (e.g. MRR value)
  # data$ranking holds the ranking value for each controller
  ranking = rank.MRR(metric)
  colnames(ranking) = c('CONTROLLER', 'ranking')
  ranking$CONTROLLER = as.character(ranking$CONTROLLER)
  data = join(data, ranking, by='CONTROLLER', type='left', match='first')
    
  # Build Matrix of controller (x) and schedule instance (y)
  fmatrix = function(row) {
    
    # Heatmap over metric itself as a data frame
    ll = as.list(row[[metric]])
    df = as.data.frame(ll)
    
    # Apply names on the data frame
    colnames(df) = row$CONTROLLER
    
    return(df)
  }
  r = ddply(data, 'SCHEDULE_ID', fmatrix)
  r = subset(r, select = -c(SCHEDULE_ID)) # Remove column SCHEDULE_ID
  r = t(as.matrix(r)) # Transposed matrix
  
  # Fill na fields (missing data)
  r[is.na(r)] = corr
  
  # Heatmap (melt everything)
  r = melt(r)
  names(r) = c('CONTROLLER', 'schedule', 'metric')
  r = join(r, ranking, by='CONTROLLER', type='left', match='first')
  
  # Sort by ranking
  r = transform(r, CONTROLLER=reorder(CONTROLLER, ranking))
  
  # New ggplot with data is r, X1 and X2 are axis and value is matrix value
  p = ggplot(data=r, aes(x=CONTROLLER, y=schedule))
  p = p + geom_tile(aes(fill=metric))
  p = p + theme_bw(base_size=9)
  p = p + scale_y_discrete(expand=c(0,0), limits=c(1:20))
  p = p + scale_x_discrete(expand=c(0,0))
  
  # Theme
  p = p + theme_bw(base_family="Roboto")
  p = p + theme(legend.position = 'none',
               axis.text.x = element_text(size=9, angle=290, 
                                       hjust=0, colour="black"))
  p = p + labs(x="Controller combination", y="Schedule")
  
  # Fill heatmap with white to black
  p = p + scale_fill_gradient(low="white", high="black")
  
  # Increase plot margin on the top to get space for markers
  p = p + theme(plot.margin = unit(c(4,1,1,1), "lines"))
  
  # Helper function which is used to generate a marker
  add.marker = function(p, text, start, end) 
  {
      text.grob = textGrob(text, gp=gpar(fontsize=10))
      p = p + annotation_custom(grob = text.grob,  xmin = start, xmax = start+end, ymin = 21, ymax = 25)
      
      p = p + annotation_custom(grob = linesGrob(), xmin = start, xmax = start, ymin = 21, ymax = 25)
      p = p + annotation_custom(grob = linesGrob(), xmin = start+end, xmax = start+end, ymin = 21, ymax = 25)
      p = p + annotation_custom(grob = linesGrob(), xmin = start, xmax = start+end, ymin = 25, ymax = 25)
      return(p)
  }
  
  # Call marker function with a callback handle on the add.marker helper function
  p = mark(add.marker, p)
  
  # Draw outside the clipping area
  gt = ggplot_gtable(ggplot_build(p))
  gt$layout$clip[gt$layout$name=="panel"] = "off"

  # Create pdf export
  name = sprintf("target/mkII_heatmap_%s.pdf", str_replace_all(metric, "\\.\\.", "_"))
  pdf(name, width=10, height=5)
  grid.draw(gt)
  dev.off()
  embed_fonts(name)

  # Save export for markdown
  ret.gt = gt
  
  # Create svg export for presentations
  p = p + theme_black()
  p = p + theme(legend.position = 'none',
                axis.text.x = element_text(size=9, angle=290, 
                                           hjust=0, colour="white"))
  p = p + labs(x="Controller combination", y="Schedule")
  
  # Draw outside the clipping area
  gt = ggplot_gtable(ggplot_build(p))
  gt$layout$clip[gt$layout$name=="panel"] = "off"
  
  name = sprintf("target/mkII_heatmap_%s.svg", str_replace_all(metric, "\\.\\.", "_"))
  svg(filename=name, bg="transparent", width = 10, height = 5)
  grid.draw(gt)
  dev.off()
  
  return(ret.gt)
}

# Test heatmap for migrations
t = heatmap.mrr('avg..srv..count', 6, function(fmark, p) {
  p = fmark(p, 'Reservation\nStatic', 0.5, 6)
  p = fmark(p, 'Reservation +\nDynamic', 6.5, 5)
  p = fmark(p, 'Demand\nStatic', 11.5, 5)
  p = fmark(p, 'Mostly Reservation + Dynamic', 16.5, 18)
  p = fmark(p, 'Demand + Dymamic', 34.5, 10)
  return(p)
})
grid.draw(t)

# Returns rankins positions for a given controller and a set of metrics 
# Example: positions.for('FirstFit+None')
positions.for = function(controller, metrics=ALL_METRICS) {
  res = data[data$CONTROLLER == controller, c("CONTROLLER", sprintf("%s.pos", metrics))]
  res = melt(id="CONTROLLER", res)$value
  return(res)
}


# Adds a flag to a given data table that indicates if a row holds a demand
# or reservation controller
add.demand.flag = function(data) {
  data$demand = FALSE
  data[grep('Demand', data$STRATEGY_PLACEMENT),]$demand=TRUE
  return(data)
}




# Runs an ANOVA analysis over all data that checks if placment and reallocation
# controller or their interaction have an effect on the ranking position
# for the average server demand metric. 
anova.fit = function() {
  # Effect of placement and reallocation strategy on average server count position
  model = avg..srv..count.pos ~ STRATEGY_PLACEMENT * STRATEGY_REALLOCATION
  
  # Reduce data
  x = data
  x = x[data$STRATEGY_REALLOCATION %in% c('kmcontrol', 'tcontrol', 'dsapp'),]
  
  # Get best power transformation
  r=boxcox(model, data=data, lambda=seq(-5,5, len=20), plot=FALSE)
  ll = r$x[which.max(r$y)]

  # Shapiro wilk test for normality
  print(shapiro.test(x$avg..srv..count.pos^ll))
  
  # Convert to factors
  x$STRATEGY_PLACEMENT = as.factor(x$STRATEGY_PLACEMENT)
  x$STRATEGY_REALLOCATION = as.factor(x$STRATEGY_REALLOCATION)
  x$avg..srv..count.pos = x$avg..srv..count.pos^ll
  
  # Fit anova model
  fit = aov(model, x)  
  
  # Return fitted model
  return(fit)
}

average.cluster.differences = function() {
  # Clusters are based on average server demand
  ranking = rank.MRR('avg..srv..count')
  ranking = ranking[with(ranking, order(rank)),]
  
  # Merge rankings with controller data (left inner)
  m.ranking = join(ranking, data, by='CONTROLLER', type='left', match='first')
  
  # Calculate summary statistics for one cluster (based on average server demand sorting)
  calc.summary = function(cluster.name, demand, dynamic) {
    # Get controllers in this cluster
    cluster = ranking[ranking$CONTROLLER %in% m.ranking[m.ranking$DEMAND == demand & m.ranking$DYNAMIC == dynamic,]$CONTROLLER,]
    
    # Attach columns: average server demand, SCHEDUL_ID
    cluster = merge(cluster, data[,c('CONTROLLER', 'SCHEDULE_ID' ,'avg..srv..count')], by='CONTROLLER')
    
    # Attach columns: Migrations
    cluster = merge(cluster, data[,c('CONTROLLER', 'SCHEDULE_ID' ,'Migrations')], by=c('CONTROLLER', 'SCHEDULE_ID'))
    
    asd.mean = mean(cluster$avg..srv..count)
    asd.sd = sd(cluster$avg..srv..count)
    asd.delta = max(cluster$avg..srv..count) - min(cluster$avg..srv..count)
    
    mig.mean = mean(cluster$Migrations)
    mig.sd = sd(cluster$Migrations)
    mig.delta = max(cluster$Migrations) - min(cluster$Migrations)
    
    return( list(cluster = cluster.name, 
                 asd.mean = round(asd.mean,2), 
                 asd.sd = round(asd.sd,2),
                 asd.delta = round(asd.delta,2),
                 mig.mean = round(mig.mean,2),
                 mig.sd = round(mig.sd,2),
                 mig.delta = round(mig.delta,2)
    ) 
    )
  }
  
  
  summary = data.frame(
    cluster = c(),
    
    asd.mean = c(),
    asd.sd = c(),
    asd.delta = c(),
    
    mig.mean = c(),
    mig.sd = c(),
    mig.delta = c(),
    
    stringsAsFactors=FALSE
  )
  
  summary = rbind(summary, as.data.frame(calc.summary('Reservation Static', FALSE, FALSE)))
  summary = rbind(summary, as.data.frame(calc.summary('Demand Static', TRUE, FALSE)))
  summary = rbind(summary, as.data.frame(calc.summary('Reservation + Reallocation', FALSE, TRUE)))
  summary = rbind(summary, as.data.frame(calc.summary('Demand + Reallocation', TRUE, TRUE)))
  
  return(summary)
}

sum = average.cluster.differences()
# print(sum)