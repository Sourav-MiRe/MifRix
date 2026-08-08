function(AP, FP){
  
  if(class(AP)[1] != class(FP)[1]){
    stop("AP and FP must both be vectors or both be data frames.")
  }
  
  if(is.vector(AP) && is.numeric(AP)){
    
    if(length(AP) != length(FP)){
      stop("AP and FP vectors must have the same length.")
    }
    
    CS <- mapply(function(ap, fp){
      vals <- c(ap, fp)
      mean(vals) * (1 - Gini(vals))
    }, AP, FP)
    
    return(data.frame(AP = AP,FP = FP,CS = CS,stringsAsFactors = FALSE))
  }
  
  if(is.data.frame(AP)){
    
    if(!identical(colnames(AP), colnames(FP))){
      stop("AP and FP data frames must have identical columns.")
    }
    
    composite_df <- AP
    
    disease_cols <- names(AP)[sapply(AP, is.numeric)]
    
    for(disease in disease_cols){
      
      composite_df[[disease]] <-
        mapply(function(ap, fp){
          vals <- c(ap, fp)
          mean(vals) * (1 - Gini(vals))
        },
        AP[[disease]],
        FP[[disease]])
    }
    
    return(composite_df)
  }
  
  stop("Unsupported input type.")
}
