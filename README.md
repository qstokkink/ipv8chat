## Installation

```
git clone --recursive git@github.com:qstokkink/ipv8chat.git
cd ipv8chat
pip install websockets
cd pyipv8
pip install -r requirements.txt
```

## Usage

1. Run the service using `python main.py PORT` (e.g. `python main.py 13345`).
2. Open `index.html?wsport=PORT` in your favorite browser (e.g. `file:///home/quinten/Documents/ipv8chat/index.html?wsport=13345`).
