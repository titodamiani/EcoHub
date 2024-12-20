
import yaml
from pathlib import Path
import requests
import pandas as pd
import time
import logging


########## Load config.yaml files ##########
def read_config(config_path: str, filepaths: bool=True, **kwargs):
    """
    Load a config.yaml file as dictionary.

    Parameters:
    config_path (str): path to the YAML configuration file.
    filepaths (bool): if True, convert all string values to Path objects.
    **kwargs: keyword arguments representing keys in the YAML file.

    Returns:
    dict: config.yaml file as dictionary.

    Raises:
    KeyError: if one of the keys in kwargs is not found in the config.yaml.
    """

    #load config.yaml as dict
    with open(config_path, "r") as handle:
        config = yaml.safe_load(handle)
    
    #keep portion of config.yaml based on provided keys 
    try:
        for argument, value in kwargs.items(): #iterates over config levels provided in kwargs"
            if value not in config: #if one of the provided levels is not in the config.yaml, raise error.
                raise KeyError(f'Key {value} not found in the config.yaml') 
            if isinstance(config[value], str): #if config[value] is a string, return it and end the loop
                return config[value]
            else: #if config[value] is not a string (i.e., it's still a dict), update config to be the nested dict and go to next iteration
                config = config[value]
        
        #convert str paths to Path objects
        if filepaths:
            config = {k: Path(v) if isinstance(v, str) else v for k, v in config.items()}
    
        return config
    
    except KeyError as e:
        raise KeyError(str(e))
    

########## Load existing CSVs ##########
def get_existing_csv(file_path):
    """Load existing results from CSV if file exists."""
    if file_path.exists():
        logging.info(f"Output file already found at {file_path}. Importing existing output file...")
        return pd.read_csv(file_path)
    else:
        return pd.DataFrame()  # Return empty DataFrame if no file exists


########## Run SPARQL query ##########
def run_query(query, genus, max_attempts=5):
    url = "https://query.wikidata.org/sparql"
    headers = {"Accept": "application/sparql-results+json",
               "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for attempt in range(1, max_attempts + 1):
        try:
            #run query
            response = requests.get(url, headers=headers, params={"query": query})
            response.raise_for_status()

            #process output
            query_out = response.json()
            out_df = pd.json_normalize(query_out["results"]["bindings"])
            out_df = out_df[[col for col in out_df.columns if col.endswith(".value")]]
            out_df.columns = [col.replace(".value", "") for col in out_df.columns]
            logging.info(f"Query for '{genus}' genus completed in {attempt} attempts.")
            return out_df
        
        #handle exceptions
        except requests.exceptions.HTTPError as http_err:
            if response.status_code == 429: #retry for too many requests
                wait_time = 2 ** attempt
                logging.warning(f"Request limit reached for '{genus}'. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            else:
                logging.error(f"HTTP Error for '{genus}' on attempt {attempt}: {http_err}")
                break
        except Exception as e:
            logging.error(f"Unexpected error for '{genus}' on attempt {attempt}: {e}")
            break
    logging.error(f"Query for '{genus}' failed after {max_attempts} attempts.")
    return None
