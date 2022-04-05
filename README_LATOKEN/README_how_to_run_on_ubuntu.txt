# 1. init hummingbot installation v1.1.0
cd ~
sudo apt-get update
sudo apt-get install -y build-essential
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
sh Miniconda3-latest-Linux-x86_64.sh
exec bash
hummmingbot_version="1.1.0"
curl https://codeload.github.com/hummingbot/hummingbot/zip/refs/tags/v$hummmingbot_version -o hummingbot.zip
unzip hummingbot.zip
export hummingbotPath="$(pwd)/hummingbot-$hummmingbot_version" && cd $hummingbotPath && ./clean && ./install
conda activate hummingbot && ./compile
bin/hummingbot.py


# 2. pulling from latoken gitlab (needs testing)
cd ~
sudo apt-get update
sudo apt-get install -y build-essential
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
sh Miniconda3-latest-Linux-x86_64.sh
exec bash
git clone --branch TRD-3815-latoken-into-hummingbot-integration https://gitlab.nekotal.tech/market-making/quantitative/humming-bot.git
export hummingbotPath="$(pwd)/humming-bot" && cd $hummingbotPath && ./clean && ./install
conda activate hummingbot && ./compile



# 3. pulling from latoken gitlab (needs testing), humming-bot folder already present in Downloads
cd ~/Downloads
sudo apt-get update
sudo apt-get install -y build-essential
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
sh Miniconda3-latest-Linux-x86_64.sh
rm Miniconda3-latest-Linux-x86_64.sh
export hummingbotPath="$(pwd)/humming-bot" && cd $hummingbotPath && ./clean && ./install
conda activate hummingbot && ./compile


# open project in pycharm, create venv/hummingbot, see image
# create 'hummingbot' venv for PYTHON="$(pwd)/miniconda3/envs/hummingbot/python3" 
# with pycharm create in 'add python interpreter' right bottom of screen click -> conda tab, set name hummingbot and Python v3.9 (or at least 3.7)
