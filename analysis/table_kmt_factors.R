library(xtable)

results = read.csv(file="table_kmt_factors.csv", sep="\t", head=T)
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