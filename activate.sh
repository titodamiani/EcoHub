#!/bin/bash

#check if conda environment piperFIM already exists
if conda env list | grep -q 'tropicana'; then

    #if env exists, print message and activate environment
    echo "Conda environment 'tropicana' already exists. Activating existing environment..."
    conda activate tropicana

else
    #if env doesn't exist, create it and install packages in requirements.txt
    echo "Creating conda environment tropicana..."
    conda create -y --name tropicana
    echo "Installing packages..."
    conda install --file requirements.txt -y
    conda activate tropicana
fi

#export cwd to PYTHONPATH
echo "Exporting current working directory to PYTHONPATH..."
export PYTHONPATH=$(pwd):$PYTHONPATH
echo "Tropicana ready!"