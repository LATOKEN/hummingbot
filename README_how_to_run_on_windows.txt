# init hummingbot installation v1.1.0
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


# pulling from latoken gitlab (needs testing)
cd ~
sudo apt-get update
sudo apt-get install -y build-essential
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
sh Miniconda3-latest-Linux-x86_64.sh
exec bash
git clone --branch TRD-3815-latoken-into-hummingbot-integration https://gitlab.nekotal.tech/market-making/quantitative/humming-bot.git
export hummingbotPath="$(pwd)/humming-bot" && cd $hummingbotPath && ./clean && ./install
conda activate hummingbot && ./compile
bin/hummingbot.py
