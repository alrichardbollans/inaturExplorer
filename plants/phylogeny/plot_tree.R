# Circular plot of a very large tree (~200k tips), colouring the branches
# of tips named in df.csv. No tip labels.
# Requires: ape
app_configs = jsonlite::fromJSON('../../app_configs.json')
library(ape)
library(ggtree)
library(ggplot2) # for the scale_color_manual function

library(dplyr) # for filtering
# ---- Settings ----
mode <- "paths"   # "paths"    = colour the full path from root to each tip (shows diversity captured)
# "terminal" = colour only the terminal branch of each tip
col_hl   <- "red"
col_bg   <- "grey80"
lwd_hl   <- 1.5
lwd_bg   <- 0.1

# ---- Read data ----
tree <- read.tree("my_cleaned_deduplicated_tree.tre")
df   <- read.csv(file.path(app_configs$cache_dir, app_configs$accplantsfilename), stringsAsFactors = FALSE)

ntip   <- length(tree$tip.label)
selected_tips <- intersect(tree$tip.label ,df$tree_name)

### Prune tips to make more readable
labels = c("×_Arsorbus_thuringiaca",  "×_Brassarda_juncea",      "×_Cylindronia_robertsii", "Cylindronia_robertsii")
get_genus <- function(labels) {
  # Genus = leading hybrid marker (×, ✕, or a standalone x/X followed by a
  # separator) plus the next word, otherwise just the first word.
  out = sub("^((?:[\u00d7\u2715]|[xX](?=[_ ]))[_ ]*[^_ ]+|[^_ ]+).*$",
            "\\1", labels, perl = TRUE)
}

prune_one_per_genus <- function(old_tree, given_tips) {  
  genus <- get_genus(old_tree$tip.label)
  by_genus <- split(old_tree$tip.label, genus)
  random = FALSE # TRUE = pick representative at random
  extra_rep = TRUE # TRUE = add a rep even if genus already has a selected tip
  keep <- unlist(lapply(by_genus, function(tips) {
    sel <- intersect(tips, given_tips)
    if (length(sel) > 0 && !extra_rep) return(sel)
    pool <- setdiff(tips, sel)
    if (length(pool) == 0) return(sel)
    rep <- if (random) sample(pool, 1) else pool[1]
    c(sel, rep)
  }), use.names = FALSE)
  
  keep <- union(keep, given_tips)
  return(drop.tip(old_tree, setdiff(old_tree$tip.label, keep)))
}

pruned_tree = prune_one_per_genus(tree, selected_tips)


get_highlight_nodes_for_tips <- function(tips_to_highlight, mrca_node, tree_data){
  # Find the node paths from each tip to the root
  # Get node IDs for the tips you want to highlight
  highlight_nodes <- tree_data %>%
    filter(label %in% tips_to_highlight)%>%
    filter(isTip) %>%
    pull(node)
  
  # Create a data frame to store the nodes along the paths to the root
  
  diff = c(1)
  while (length(diff)>0) {
    node_data = tree_data %>% 
      filter(node %in% highlight_nodes)
    new_nodes = node_data$parent
    new_nodes = new_nodes[new_nodes != mrca_node]
    diff = setdiff(new_nodes, highlight_nodes)
    highlight_nodes = c(new_nodes, highlight_nodes)
  }
  return(highlight_nodes)
}

get_plots_for_tips <- function(labelled_tree, tips_to_highlight, highlight_colour){
  line_size=0.02
  label_size = 24
  # mrca_node <- ape::getMRCA(labelled_tree, tips_to_highlight)
  root <- length(labelled_tree$tip.label) + 1L
  stopifnot(!(root %in% labelled_tree$edge[, 2]))   # sanity check: the root is never a child
  
  # Convert the tree to a data frame that we can filter
  circ <- ggtree(labelled_tree, layout = "circular", linewidth = line_size)

  tr_data = circ$data
  highlight_nodes = get_highlight_nodes_for_tips(tips_to_highlight,root,tr_data)
  # print('got higlight nodes')
  # print(highlight_nodes)
  circ <-  circ + 
    geom_tree(aes(color = as.factor(node %in% highlight_nodes), linewidth = as.factor(node %in% highlight_nodes)), show.legend = FALSE) +
    scale_color_manual(values = c("TRUE" = highlight_colour, "FALSE"=col_bg))+ 
    scale_linewidth_manual(values = c("TRUE" = 10*line_size, "FALSE"=line_size))+
    # geom_point2(aes(subset=node==root), color=highlight_colour, size=3)+
    theme(plot.margin = unit(c(0, 0, 0, 0), "cm"))#+
  
  
  return(circ)
}

circ1 = get_plots_for_tips(pruned_tree, selected_tips,col_hl)
# plot(circ1)
# ---- Plot (PNG, since a vector file with 200k tips gets huge/slow) ----
# edge.color / edge.width are indexed by row of tree$edge, which is exactly what mark is.
app_configs = jsonlite::fromJSON('../../app_configs.json')
ggsave(file.path(app_configs$cache_dir, app_configs$phyplotfilename), width = 8, height = 8, dpi = 600)
