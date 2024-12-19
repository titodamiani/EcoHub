#TODO: Add description
#TODO: Save failed queries with time stamp in log folder. Make it more informative

import pandas as pd
from pathlib import Path
from Bio import Phylo
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from src.utils import read_config, generate_query, run_query

#setup logging
log_file = Path(f"logs/nps_in_genera_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",  # Custom date format without milliseconds
    handlers=[
        logging.FileHandler(log_file, mode='w'), #logs to file
        logging.StreamHandler()])  #logs to also to console

#load config
logging.info(f"Reading config file...")
config = read_config(config_path="config/config.yaml")

#import Angiosperms tree
logging.info(f"Importing Angiosperms phylogenetic tree...")
tree_file_path = Path(config["input_files"]["phylogenetic_tree"])
if tree_file_path.exists():
        tree = Phylo.read(tree_file_path, "newick")
        logging.info(f"Angiosperms phylogenetic tree successfully imported!")
else:
    logging.error(f"No tree file found at {tree_file_path}.")


#extract leaf names
logging.info(f"Parsing phylogenetic tree...")
tree_leaves = [leaf.name for leaf in tree.get_terminals()]
tree_leaves = pd.Series(tree_leaves, name='leaf_name')
logging.info(f'Tree contains {len(tree_leaves)} leaves')
logging.info(f"{tree_leaves.str.endswith('sp.').sum()} species names are not defined (e.g., 'Lessertia_sp.')")

#create df with order, family, genus, species
logging.info(f'Converting tree into pandas dataframe...')
tree_df = tree_leaves.str.split('_', expand=True)
tree_df = tree_df.iloc[:, :4] #keep first 4 columns
tree_df.columns = ['Order', 'Family', 'Genus', 'Species'] #rename columns
tree_df = pd.concat([tree_leaves, tree_df], axis=1).rename(columns={0: 'leaf_name'}).set_index('leaf_name')

#list of genera in the tree to be queried in Wikidata
logging.info(f'Extracting list of genera...')
genera_list = tree_df['Genus'].unique()
logging.info(f'Tree contains {len(genera_list)} unique genera')

#run SPARQL queries (parallelized)
logging.info(f'Querying {len(genera_list)} genera in Wikidata for natural products reports...')

def process_genera_parallel(genera_list, threads=20, max_attempts=5):
    all_results = []
    failed_tasks = {}

    with ThreadPoolExecutor(max_workers=threads) as executor:
        tasks = {executor.submit(run_query, genus, max_attempts): genus for genus in genera_list}

        for completed_task in as_completed(tasks):
            genus_name = tasks[completed_task]
            try:
                output = completed_task.result()
                all_results.append(output)  # Append all results, including None
                if output.empty:
                    logging.info(f"Query for '{genus_name}' returned no results")
            except Exception as e:
                failed_tasks[genus_name] = str(e)

    logging.info(f"Processing completed: {len(genera_list)} queries run.")
    logging.info(f"{len(genera_list) - len(failed_tasks)} queries succeeded.")

    return pd.concat(all_results, ignore_index=True) if all_results else pd.DataFrame(), failed_tasks

#run queries
results_path = Path(config["output_files"]["nps_in_genera"])
if results_path.exists():  #check if results file already exists
    logging.info(f"Output file already found at {results_path}. Importing existing output file...")
    results_df = pd.read_csv(results_path)

    #missing genera in output file
    genera_list_series = pd.Series(genera_list)
    genera_to_requery = genera_list_series[~genera_list_series.isin(results_df['genus_name'].drop_duplicates())]
    logging.info(f"{genera_to_requery.shape[0]} genera in the tree are missing in the output file. Re-querying missing genera...")

    if not genera_to_requery.empty:
        new_results_df, failed_tasks = process_genera_parallel(genera_to_requery, threads=20)
        results_df = pd.concat([results_df, new_results_df], ignore_index=True)
        results_df.to_csv(results_path, index=False)
        logging.info(f"Updated results saved to {results_path}")
else:
    #run SPARQL queries (parallelized)
    results_df, failed_tasks = process_genera_parallel(genera_list, threads=20)

    #save results
    results_df.to_csv(results_path, index=False)
    logging.info(f"Results saved to {results_path}")

if failed_tasks:
    failed_queries_path = log_file.with_name(f"failed_queries_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    logging.warning(f"{len(failed_tasks)} queries failed! Saving list of failed queries to {failed_queries_path}...")
    failed_df = pd.DataFrame(list(failed_tasks.items()), columns=["Genus", "Reason"])
    failed_df.to_csv(failed_queries_path, index=False)
else:
    logging.info(f"All queries completed successfully!")