#!/bin/bash

echo "Starting sensor network with 5 nodes..."

echo "Starting sensor 1"
python3 lab5.py &

echo "Starting sensor 2"
python3 lab5.py &

echo "Starting sensor 3"
python3 lab5.py &

echo "Starting sensor 4"
python3 lab5.py &

echo "Starting sensor 5"
python3 lab5.py &


echo "All sensors started."

# Wait for all background processes
wait
