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


### Prune tips to make more readable
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

get_plots_for_tips <- function(labelled_tree, tips_to_highlight, highlight_colour=col_hl, extra_tips=NULL, extra_highlight_colour=NULL){
  line_size=0.02
  label_size = 24
  # root <- length(labelled_tree$tip.label) + 1L
  # stopifnot(!(root %in% labelled_tree$edge[, 2]))   # sanity check: the root is never a child
  mrca_node <- ape::getMRCA(labelled_tree, tips_to_highlight)
  # Convert the tree to a data frame that we can filter
  circ <- ggtree(labelled_tree, layout = "circular", linewidth = line_size)
  
  tr_data = circ$data
  highlight_nodes = get_highlight_nodes_for_tips(tips_to_highlight,mrca_node,tr_data)
  
  if(!is.null(extra_tips)){
    
    highlight_nodes_for_extras = get_highlight_nodes_for_tips(extra_tips,ape::getMRCA(labelled_tree, extra_tips),tr_data)
    
    
  }else{
    highlight_nodes_for_extras = NULL
  }
  
  f = factor(
    ifelse(circ$data$node %in% highlight_nodes_for_extras, "extra",
           ifelse(circ$data$node %in% highlight_nodes,            "main", "bg")),
    levels = c("bg", "main", "extra")
  )
  circ1 <- circ +
    geom_tree(
      aes(
        color = f,
        linewidth = f
      ),
      show.legend = FALSE
    ) +
    scale_color_manual(values = c(
      "main"  = highlight_colour,
      "extra" = extra_highlight_colour,
      "bg"    = col_bg
    )) +
    scale_linewidth_manual(values = c(
      "main"  = 10 * line_size,
      "extra" = 20 * line_size,
      "bg"    = 3 * line_size
    )) +
    theme(plot.margin = unit(c(0, 0, 0, 0), "cm"))
  
  plot(circ1)
  
  
  return(circ1)
}
