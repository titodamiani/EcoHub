#!/bin/bash

#check if conda environment piperFIM already exists
if conda env list | grep -q 'ecohub'; then

    #if env exists, print message and activate environment
    echo "Conda environment 'ecohub' already exists. Activating existing environment..."
    conda activate ecohub

else
    #if env doesn't exist, create it and install packages in requirements.txt
    echo "Creating conda environment ecohub..."
    conda create -y --name ecohub
    echo "Installing packages..."
    conda install --file requirements.txt -y
    conda activate ecohub
fi

#export cwd to PYTHONPATH
echo "Exporting current working directory to PYTHONPATH..."
export PYTHONPATH=$(pwd):$PYTHONPATH
echo "EcoHub ready!"