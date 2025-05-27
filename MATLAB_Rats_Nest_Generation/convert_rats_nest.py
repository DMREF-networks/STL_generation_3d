import pandas as pd

# Load CSV without headers
df = pd.read_csv("pos2.csv", header=None) # position file 
df_adj = pd.read_csv("adj2.csv", header=None) # adjacency matrix

# Sort df by the first column
df = df.sort_values(by=0).reset_index(drop=True)

# Find rows in df_adj that are all zeros
zero_row_indices = df_adj[(df_adj == 0).all(axis=1)].index

# Drop corresponding rows and columns from df_adj
df_adj = df_adj.drop(index=zero_row_indices).drop(columns=zero_row_indices).reset_index(drop=True)

# Drop corresponding rows from df
df = df.drop(index=zero_row_indices).reset_index(drop=True)

# Drop the first and last column of df
df = df.iloc[:, 1:-1]

# Save the cleaned and aligned DataFrames
df.to_csv("ratsnest_xy_2.csv", index=False, header=False)
df_adj.to_csv("ratsnest_adj_2.csv", index=False, header=False)
