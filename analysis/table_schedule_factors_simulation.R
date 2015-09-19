library(xtable)

results = read.csv(file="table_schedule_factors_simulation.csv", sep="\t", head=T)

# Latex
print(xtable(results,
             digits=0, 
      ), 
      include.rownames=FALSE, 
      include.colnames=TRUE, 
      latex.environments=c("center"),
      floating.environment='table', 
      table.placement='htb', 
      booktabs=TRUE,
      sanitize.colnames.function = identity,
      sanitize.rownames.function = identity,
      sanitize = identity,
)

# HTML for presentations
print(xtable(results,
             digits=0, 
      ), 
      type='html',
      include.rownames=FALSE, 
      include.colnames=TRUE, 
      sanitize.colnames.function = identity,
      sanitize.rownames.function = identity,
      sanitize = identity,
)