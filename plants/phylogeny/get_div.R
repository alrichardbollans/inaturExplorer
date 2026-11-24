library(ape)
get_induced_tree_from_species <- function(tree, species_list){
  if(length(species_list)<2){
    cat("Not more than one species for", species_list, "\n")
  } else{
    subtree = ape::keep.tip(tree, species_list)
    return(subtree)
  }

}

calculate_phylogenetic_diversity <- function(tree, species_in_tree){
  subtree = get_induced_tree_from_species(tree, species_in_tree)
  # Calculate the phylogenetic diversity
  # Faiths measure (Faith 1992)
  phy_diversity <- sum(subtree$edge.length)

  return(phy_diversity)

}

# ---- Read data ----
app_configs = jsonlite::fromJSON('../../app_configs.json')
tree <- read.tree("my_cleaned_deduplicated_tree.tre")
df   <- read.csv(file.path(app_configs$cache_dir, app_configs$accplantsfilename), stringsAsFactors = FALSE)

selected_tips <- intersect(tree$tip.label ,df$tree_name)

user_div = calculate_phylogenetic_diversity(tree, selected_tips)
total_div = sum(tree$edge.length)
proportion = user_div/total_div

df = data.frame(c(user_div, total_div, proportion, length(selected_tips), length(tree$tip.label)),row.names =c('user_div', 'total_div', 'proportion', 'user_tips', 'total_tips'))
names(df) = 'diversity_measures'
write.csv(df,file.path(app_configs$cache_dir, app_configs$phydivfilename))
