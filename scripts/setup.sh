#!/bin/bash

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install

# Start the application
echo "Starting the application..."
echo "Backend will run on http://localhost:8000"
echo "Frontend will run on http://localhost:3000"

# Start backend in background
cd ..
python src/api/main.py &
BACKEND_PID=$!

# Start frontend
cd frontend
npm start &
FRONTEND_PID=$!

# Handle script termination
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT TERM

# Wait for both processes
wait 