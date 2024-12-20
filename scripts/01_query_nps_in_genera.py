#queries Wikidata for natural product reports in genera contained in the angiosperms tree of life
#extract genus names from tree file and runs the same SPARQL query changing only the genus name
#results are saved as a CSV file

import pandas as pd
from pathlib import Path
from Bio import Phylo
import logging
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from src.utils import read_config, run_query, get_existing_csv #, #generate_query 

#setup logging
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_file = Path(f"logs/{timestamp}_nps_in_genera.log")
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
tree_path = Path(config["tree_files"]["zuntini_genus"])
if tree_path.exists():
        tree = Phylo.read(tree_path, "newick")
        logging.info(f"Angiosperms phylogenetic tree successfully imported!")
else:
    logging.error(f"No tree file found at {tree_path}.")

#create df from tree (order, family, genus, species)
logging.info(f"Parsing phylogenetic tree...")
tree_leaves = [leaf.name for leaf in tree.get_terminals()] #extract leaf names
tree_leaves = pd.Series(tree_leaves, name='leaf_name')
tree_df = tree_leaves.str.split('_', expand=True)
tree_df = tree_df.iloc[:, :4] #keep first 4 columns
tree_df.columns = ['Order', 'Family', 'Genus', 'Species'] #rename columns
tree_df = pd.concat([tree_leaves, tree_df], axis=1).rename(columns={0: 'leaf_name'}).set_index('leaf_name')
genera_list = pd.Series(tree_df['Genus'].unique())  #list of genera to be queried in Wikidata
logging.info(f'Parsing complete! Querying {len(genera_list)} genera in Wikidata for natural products reports...')

#import query template
logging.info(f"Importing SPARQL query template...")
query_path = Path(config["sparql_queries"]["nps_in_genera"]) #import query template
with open(query_path, "r") as file:
        query_template = file.read()
logging.info(f"Query template successfully imported!")

#function to run a SPARQL query
def run_query(genus, max_attempts=10):
    query = query_template.format(genus=genus) #replace placeholder in the query template
    url = "https://query.wikidata.org/sparql"
    headers = {"Accept": "application/sparql-results+json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for attempt in range(1, max_attempts + 1):
        try: 
            response = requests.get(url, headers=headers, params={"query": query}) #run query
            response.raise_for_status() #raise exception if requests is unsuccessful

            #process output
            query_out = response.json()
            out_df = pd.json_normalize(query_out["results"]["bindings"])
            out_df = out_df[[col for col in out_df.columns if col.endswith(".value")]]
            out_df.columns = [col.replace(".value", "") for col in out_df.columns]
            logging.info(f"Query for '{genus}' genus completed in {attempt} attempts.")
            if out_df.empty:
                logging.info(f"Query for '{genus}' returned no results")
            return out_df, None #return df and None for no errors
        
        except requests.exceptions.HTTPError as http_err:
            if response.status_code == 429: #retry for too many requests
                wait_time = 2 ** attempt
                logging.warning(f"Request limit reached for '{genus}'. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            else: #if any other HTTPError occurs
                logging.error(f"HTTP Error for '{genus}' on attempt {attempt}: {http_err}")
                return None, str(http_err)
        except Exception as e:
            logging.error(f"Unexpected error occurred when querying '{genus}' (attempt n° {attempt}): {e}")
            return None, str(e)
    logging.error(f"Query for '{genus}' failed after {max_attempts} attempts.")
    return None, 'Max attempts reached' 

#function to parallelize SPARQL queries
def query_genera_parallel(genera_list, threads=20, max_attempts=10):
    all_results = []
    failed_tasks = {}

    with ThreadPoolExecutor(max_workers=threads) as executor:
        tasks = {executor.submit(run_query, genus, max_attempts): genus for genus in genera_list}
        for completed_task in as_completed(tasks):
            genus_name = tasks[completed_task]
            try:
                output, error = completed_task.result()
                # output = completed_task.result()
                if error:
                    failed_tasks[genus_name] = error  #store the error in failed_tasks
                else:
                    all_results.append(output)  #append results if errore is None
            except Exception as e:
                failed_tasks[genus_name] = str(e)

    logging.info(f"Processing completed: {len(genera_list)} queries run.")
    logging.info(f"{len(genera_list) - len(failed_tasks)} queries succeeded.")

    return pd.concat(all_results, ignore_index=True) if all_results else pd.DataFrame(), failed_tasks

#if output file already exists, import it and run queries for missing genera
out_path = Path(config["output_files"]["nps_in_genera"])
results_df = get_existing_csv(out_path)

if results_df.empty:
    logging.info(f'Querying {len(genera_list)} genera in Wikidata for natural products reports...')
    results_df, failed_tasks = query_genera_parallel(genera_list, threads=20)
    results_df.to_csv(out_path, index=False) #save results
    logging.info(f"Results saved to {out_path}")

    if failed_tasks:
        failed_queries_path = Path(f"logs/{timestamp}_failed_queries.csv")
        logging.warning(f"{len(failed_tasks)} queries failed! Saving list of failed queries to {failed_queries_path}...")
        failed_df = pd.DataFrame(list(failed_tasks.items()), columns=["Genus", "Reason"])
        failed_df.to_csv(failed_queries_path, index=False)
    else:
        logging.info(f"All queries completed successfully!")

else:
    logging.info(f"Output file already found at {out_path}. Importing existing output file...")
    results_df = pd.read_csv(out_path)   
    genera_to_requery = genera_list[~genera_list.isin(results_df['genus_name'].drop_duplicates())] #check for missing genera

    if not genera_to_requery.empty:
        logging.info(f"{genera_to_requery.shape[0]} genera in the tree are missing in the output file. Re-querying missing genera...")
        new_results_df, failed_tasks = query_genera_parallel(genera_to_requery, threads=20)
        results_df = pd.concat([results_df, new_results_df], ignore_index=True)
        results_df.to_csv(out_path, index=False)
        logging.info(f"Updated results saved to {out_path}")

        if failed_tasks:
            failed_queries_path = Path(f"logs/{timestamp}_failed_queries.csv")
            logging.warning(f"{len(failed_tasks)} queries failed! Saving list of failed queries to {failed_queries_path}...")
            failed_df = pd.DataFrame(list(failed_tasks.items()), columns=["Genus", "Reason"])
            failed_df.to_csv(failed_queries_path, index=False)