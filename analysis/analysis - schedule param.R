# Load packages
library("plyr")
library("xtable")
library("ggplot2")
source("analysis - schedule param plots.R")
require(reshape)
require(MASS)
require(knitr)

# Schedule configurations
# Data in this file is ued to query optimal and heuristic data
configurations = read.csv(file=sprintf("schedule_configurations4.csv"), sep="\t", head=T)

# Heuristic peak server demand for each schedule instance
heuristics = read.csv(file=sprintf("sch_conf_sensitivity_heuristics4.csv"), sep="\t", head=T)

# Lower bound results
lowerBounds = read.csv(file=sprintf("sch_conf_sensitivity_lowerbound5.csv"), sep="\t", head=T)

# List of placement heuristics found in the data
placement.heuristics = unique(heuristics$STRATEGY_PLACEMENT)

# Add demand_based column that indicates of a row is a demand based (TRUE) or reservation based (FALSE) result
heuristics$demand_based = FALSE
lowerBounds$demand_based = FALSE
heuristics[grep('Demand', heuristics$STRATEGY_PLACEMENT, fixed=TRUE),]$demand_based = TRUE
lowerBounds[grep('Demand', lowerBounds$STRATEGY_PLACEMENT, fixed=TRUE),]$demand_based = TRUE

# Add column for schedule configuration base id
heuristics$schedule_base_id = floor(heuristics$SCHEDULE_ID / 100) * 100
lowerBounds$schedule_base_id = floor(lowerBounds$SCHEDULE_ID / 100) * 100

# Merge configuration settings into heuristics data frame
heuristics = merge(heuristics, configurations, by.x='schedule_base_id', by.y='schedule_id')

# Remove columns not required in lower bounds
lowerBounds = subset(lowerBounds, select=-c(RUN, STRATEGY_PLACEMENT, STRATEGY_REALLOCATION, schedule_base_id))

# Rename columns on lower bounds
colnames(lowerBounds)[3:4] = c('lb.max..servers', 'lb.avg..srv..count')

# Merge lower bounds into heuristics data frame
heuristics = merge(lowerBounds, heuristics, by=c('SCHEDULE_ID', 'demand_based', 'DOMAIN_SIZES_SET'))

# Calculate competitive values
heuristics$normalized.avg = heuristics$avg..srv..count / heuristics$lb.avg..srv..count
heuristics$normalized.max = heuristics$max..servers / heuristics$lb.max..servers

# Check if lower bounds are broken 
if(sum(heuristics$normalized.avg < 1) + sum(heuristics$normalized.max < 1) > 0)
  stop("ERROR: Competitive value less than 1")

#################################################################################
# Backwards compatibility #######################################################
res = heuristics
ores = heuristics
#################################################################################

# Filter: returns only demand based results
filter.demand = function(res) {
  res = res[res$demand_based == TRUE,]
  return(res)
}

# Filter: returns only reservation based results
filter.non.demand = function(res) {
  res = res[res$demand_based == FALSE,]
  return(res)
}

# Creates a new histogram with ggplot2 but does not include data
my.histogram = function(title) {
  p = ggplot()
  p = p + scale_fill_brewer(palette="Dark2", name="Controllers")
  p = p + labs(title = title)
  p = p + theme(legend.position="top")
  p = p + xlab("Count")
  p = p + ylab("Normalized value")
  return(p)
}

# Creates a latex table for a given data frame
latex.table = function(data, caption, label) {
  print(xtable(data,
               digits=0,
               caption=caption,
               label=label
  ), 
  include.rownames=FALSE,
  include.colnames=TRUE,
  latex.environments=c("center", "footnotesize"),
  floating.environment='table',
  table.placement='htb'
  )
}

# Plots histograms of normalized values for each strategy individually
per.strategy.histogram = function(mode='max') {
  o = sapply(placement.heuristics[placement.heuristics], function(heuristic) {
    
    res = ores
    res = res[res$STRATEGY_PLACEMENT == heuristic,]
    
    if(mode == 'max')
      model = normalized.max ~ launches * lifetime * inter_arrival
    else
      model = normalized.avg ~ launches * lifetime * inter_arrival
    
    
    cur = boxcox(model, data=res, lambda=seq(-15,15, len=50), plotit=FALSE)
    best = cur$x[which.max(cur$y)]
    
    if(model == 'max') {
      res$normalized.max = res$normalized.max^best
      hist(res$normalized.max, main=heuristic)
    } 
    else {
      res$normalized.avg = res$normalized.avg^best
      hist(res$normalized.avg, main=heuristic)
    }
  })
}


# Does significance analysis for each strategy individually
per.strategy.significance = function(p=0.001, mode='avg') {
  # Apply analysis for each heuristic
  sapply(placement.heuristics[placement.heuristics], function(heuristic) {
    res = ores
    res = res[res$STRATEGY_PLACEMENT == heuristic,]
    
    if(mode == 'avg')
      model = normalized.avg ~ launches * lifetime * inter_arrival * DOMAIN_SIZES_SET
    else
      model = normalized.max ~ launches * lifetime * inter_arrival * DOMAIN_SIZES_SET
    
    cur = boxcox(model, data=res, lambda=seq(-15,15, len=200), plotit=FALSE)
    best = cur$x[which.max(cur$y)]
    
    if(model == 'max') {
      res$normalized.max = res$normalized.max^best
    } 
    else {
      res$normalized.avg = res$normalized.avg^best
    }
    
    # ANOVA model
    ar = aov(model, res)
    s = summary(ar)
    
    # Get probability result column
    l = s[[1]][["Pr(>F)"]] 
    
    # Get rownames
    names = rownames(s[[1]])
    
    # Get all rownames where probability is below 1% level and tidy them up
    signifi = names[l < p]
    signifi = signifi[!is.na(signifi)]
    signifi = gsub("[[:space:]]*$","", signifi)
    
    # Write results as bullet point list
    cat(sprintf("* %s \n", heuristic))
    o = lapply(signifi, function(name) {
      cat(sprintf("  * %s \n", name))
    })
    
    cat("\n\n")
    
    # Plot ANOVA charts
    plot(ar)
    
    # Newline
    cat("\n\n")
  })
}

