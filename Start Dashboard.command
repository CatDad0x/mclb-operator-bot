#!/bin/bash
cd "/Users/akash/Test Web3 App/mclb-bot"
lsof -ti:8080 | xargs kill -9 2>/dev/null
python3 dashboard.py
