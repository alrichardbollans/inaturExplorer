print('running plot_tree.R')
# Requires: ape
app_configs = jsonlite::fromJSON('../../app_configs.json')
# Optional first argument: directory holding the accepted names csv and receiving outputs
args <- commandArgs(trailingOnly = TRUE)
data_dir <- if (length(args) >= 1) args[1] else file.path(app_configs$cache_dir,'users','adamrb2')
source('helpers.R')

# ---- Read data ----
tree <- ape::read.tree("my_cleaned_deduplicated_tree.tre")
df   <- read.csv(file.path(data_dir, app_configs$accplantsfilename), stringsAsFactors = FALSE)

# ntip   <- length(tree$tip.label)
selected_tips <- intersect(tree$tip.label ,df$tree_name)


tree = prune_one_per_genus(tree, selected_tips)
gc()
circ1 = get_plots_for_tips(tree, selected_tips)
gc()
print('saving plot')
# ---- Plot (PNG, since a vector file with 200k tips gets huge/slow) ----
# edge.color / edge.width are indexed by row of tree$edge, which is exactly what mark is.
ggsave(file.path(data_dir, app_configs$phyplotfilename), width = 2.6, height = 2.6,units = 'in', dpi = 600)
