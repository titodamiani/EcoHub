# EcoHub
Platform to integrate metabolomics, ecology and phylogenomics data for plant natural product discovery.

## Requirements
- [Miniconda/Anaconda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html)
- Python 3.11.0 or higher

## Setup
Run the following command in your terminal:

1. Clone the GitHub repository to your local machine:
~~~
git clone https://github.com/titodamiani/EcoHub.git
~~~

2. Create a conda environment containing all the dependencies listed in `requirements.yaml`
~~~
conda env create -f requirements.yaml
~~~

3. Activate the environment
~~~
conda activate ecohub
~~~

4. Download the `data` folder from Zenodo (TODO) inside the main repository directory.

## Usage
Paths and names of all input and output files are listed in the `config/config.yaml` file and can be changed directly from there.