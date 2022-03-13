# dependencies
# install winget if you don't have it installed https://www.microsoft.com/nl-nl/p/app-installer/9nblggh4nns1?rtc=1#activetab=pivot:overviewtab


# 1. init hummingbot installation v1.1.0 (only necessary at beginning so skip to 2 if you want to pull from gitlab)

# from git for windows, open git bash, included in vs2019 installation
# initialized conda
conda init bash
# exit git-bash to take effect
exit
# launch Git Bash App again


cd ~
winget install miniconda3
# create 'hummingbot' venv for PYTHON="$(pwd)/miniconda3/envs/hummingbot/python3" 
# with pycharm create in 'add python interpreter' right bottom of screen click -> conda tab, set name hummingbot and Python v3.9
export CONDAPATH="$(pwd)/miniconda3"
export PYTHON="$(pwd)/miniconda3/envs/hummingbot/python3"
# Clone Hummingbot version tag
hummmingbot_version="1.1.0"
git clone https://github.com/hummingbot/hummingbot.git v$hummmingbot_version
# Install Hummingbot
export hummingbotPath="$(pwd)/v$hummmingbot_version" && cd $hummingbotPath && ./install
# Activate environment and compile code
conda activate hummingbot && ./compile
# Start Hummingbot
winpty python bin/hummingbot.py




# 2. pulling from latoken gitlab (needs testing) install same dependencies as above

# from git for windows, open git bash, included in vs2019 installation
# initialize conda
conda init bash
# exit git-bash to take effect
exit
# launch Git Bash App again


cd ~
winget install miniconda3
# create 'hummingbot' venv for PYTHON="$(pwd)/miniconda3/envs/hummingbot/python3" 
# with pycharm create in 'add python interpreter' right bottom of screen click -> conda tab, set name hummingbot and Python v3.9
export CONDAPATH="$(pwd)/miniconda3"
export PYTHON="$(pwd)/miniconda3/envs/hummingbot/python3"
git clone --branch TRD-3815-latoken-into-hummingbot-integration https://gitlab.nekotal.tech/market-making/quantitative/humming-bot.git
export hummingbotPath="$(pwd)/humming-bot" && cd $hummingbotPath && ./clean && ./install
# Activate environment and compile code
conda activate hummingbot && ./compile
# Start Hummingbot
winpty python bin/hummingbot.py
