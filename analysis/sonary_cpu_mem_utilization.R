library(extrafont)
library(plyr)
library(ggplot2)
library(scales)

# Load fonts
if(exists('fonts.loaded') == FALSE)
{
  print("Loading fonts...")
  fonts.loaded = TRUE
  loadfonts()
}

# Load Sonar queries
queries = read.csv("sonar_cpu_mem_utilization.csv", sep='\t', stringsAsFactors=FALSE)

# Load data from Sonar
res = adply(queries, 1, function(row) {
  print(row)
  query = "python D:/work/control/Control/src/sonar/rsonar.py"
  tquery = sprintf("%s --host %s --sensor %s --from-date %s --from-time %s --to-date %s --to-time %s",
                   query,
                   row$host,
                   row$sensor,
                   row$fromdate,
                   row$fromtime,
                   row$todate,
                   row$totime
                   )
  data = read.csv(pipe(tquery))
  colnames(data) = c('stime', 'svalue')
  data$stime = as.POSIXct(data$stime, origin="1970-01-01")
  return(data)
})


# Create new plot
p = ggplot(data=res, aes(stime, svalue, color=sensor, group=sensor))
p = p + geom_step(size=0.7)

# Add annotation for memory limit
p = p + geom_hline(yintercept=85, color="black", linetype="longdash", size=0.7)

# Theme
p = p + labs(x="Time [h]", y="Utilization")
p = p + theme_bw(base_size=12, base_family="Roboto")
p = p + theme(legend.position=c(0.9, 0.85), legend.background = element_rect(fill=alpha('white', 0.8)))
p = p + scale_color_discrete(name="Sensor", labels=c("CPU", "Memory"))


# Save plot
ggsave(p, file="target/mkII_sonar_resource_utilization.pdf", width=6, height=4)
embed_fonts('target/mkII_sonar_resource_utilization.pdf')
print(p)
