# QQ plot of effect size
qq_plot = function(aov_result, filename)  
{
  effects = model.tables(aov_result, 'effects', se=FALSE)
  
  # Extract effect size for each factor and interaction
  effects.names = c()
  effects.values = c() 
  for(name in names(effects$tables)) {
    table = get(name, effects$tables)
    
    # Add to list
    effects.names = append(effects.names, name)
    effects.values = append(effects.values, as.numeric(tail(table, n=1)))
  }
  
  # Create a data frame
  effects.df = data.frame(list(value=effects.values, name=effects.names))
  
  # Sort data frame
  effects.df = effects.df[with(effects.df, order(value)),]
  
  # Calculate quantiles
  effects.df$quantiles = quantile(rnorm(1000), seq(0, 100, length.out = nrow(effects.df)) / 100)
  
  # Plot
  v = ggplot(data=effects.df, aes(x=quantiles, y=value)) + 
    geom_point(aes(color=name, size=name)) + 
    geom_smooth(method = "lm", se=F)
  
  print(v)
}


# Residual plots
plot_residuals = function(values, aov_res, name)
{
  # Get fitted aov values, residualds and standardized residuals
  frame.res = values
  frame.res$M1.i = 1:nrow(values)
  frame.res$M1.Fit = fitted(aov_res)
  frame.res$M1.Resid = resid(aov_res)
  frame.res$M1.SResid = rstandard(aov_res)
  
  # Create a QQ plot on residuals
  v = ggplot(frame.res, aes(sample = M1.Resid)) + 
    stat_qq()
  ggsave(filename=sprintf('result - %s residuals.png', name), plot=v, width=5, height=5, dpi=100)
  embed_fonts(sprintf('result - %s residuals.png', name))
  
  # Plot residuals vs. fitted values
  v = ggplot(frame.res, aes(M1.Fit, M1.Resid)) + 
    geom_point() +
    xlab("Fitted Values") +
    ylab("Residuals")
  print(v)
}

# Variable coding
code = function(var) 
{
  var = (var - (min(var) + max(var)) / 2.) / ((max(var) - min(var)) / 2.)
  return(var)
}

decode=function(var, level)
{
  var = var * (max(level) - min(level)) / 2 + (min(level) + max(level)) / 2
  return(var)
}


# Contour plot function
contour_plot = function(model, data, ranges, aest, name, type_name, levelsx=NULL, levelsy=NULL, transform=NULL) 
{
  # Prediction
  model = lm(model, data=data)
  new.data = expand.grid(ranges)
  new.data$X = predict(model, new.data)
  
  if(!is.null(transform)) 
  {
    new.data$X = transform(new.data$X)
  }
  
  # Plotting
  v = ggplot(new.data, aest)
  v = v + geom_contour(aes(colour = ..level..))
  
  if(!is.null(levelsx) & !is.null(levelsy))
  {
    # Add ticks with decoded variables
    breaks = seq(-1,1,0.4)
    labels = decode(breaks, levelsx)
    v = v + scale_x_continuous(breaks=breaks, labels=labels)  
    
    labels = decode(breaks, levelsy)
    v = v + scale_y_continuous(breaks=breaks, labels=labels)  
  }
  
  # Save contour plot
  print(v)
}

