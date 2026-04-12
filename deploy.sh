#!/bin/bash

# Myle Dashboard Deployment Script
# Complete deployment for development/production

set -e

echo "=== Myle Dashboard Deployment ==="

# Configuration
MODE=${1:-development}  # development or production
BACKEND_PORT=${2:-8000}
FRONTEND_PORT=${3:-3000}

echo "Mode: $MODE"
echo "Backend Port: $BACKEND_PORT"
echo "Frontend Port: $FRONTEND_PORT"

# Function to check if service is running
check_service() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null ; then
        return 0
    else
        return 1
    fi
}

# Function to wait for service
wait_for_service() {
    local port=$1
    local service=$2
    local max_attempts=30
    local attempt=1
    
    echo "Waiting for $service on port $port..."
    
    while [ $attempt -le $max_attempts ]; do
        if check_service $port; then
            echo "$service is running on port $port"
            return 0
        fi
        
        echo "Attempt $attempt/$max_attempts: $service not ready yet..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo "ERROR: $service failed to start on port $port"
    return 1
}

# Step 1: Environment Setup
echo "Step 1: Setting up environment..."
if [ -f "setup_environment.sh" ]; then
    ./setup_environment.sh
else
    echo "ERROR: setup_environment.sh not found"
    exit 1
fi

# Step 2: Database Setup
echo "Step 2: Setting up database..."
cd backend

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "ERROR: Python virtual environment not found"
    exit 1
fi

# Initialize database
python3 init_database.py

if [ $? -ne 0 ]; then
    echo "ERROR: Database initialization failed"
    exit 1
fi

# Step 3: Start Backend Server
echo "Step 3: Starting backend server..."

if [ "$MODE" = "development" ]; then
    # Development mode with auto-reload
    uvicorn app.main:app --reload --host 0.0.0.0 --port $BACKEND_PORT &
    BACKEND_PID=$!
    echo "Backend server started (PID: $BACKEND_PID)"
    
    # Wait for backend to start
    sleep 5
    
    # Check if backend is responding
    if curl -f http://localhost:$BACKEND_PORT/health >/dev/null 2>&1; then
        echo "Backend health check: OK"
    else
        echo "Backend health check: FAILED (continuing anyway...)"
    fi
    
elif [ "$MODE" = "production" ]; then
    # Production mode with Gunicorn
    pip install gunicorn
    gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$BACKEND_PORT --daemon
    BACKEND_PID=$!
    echo "Backend server started in production mode (PID: $BACKEND_PID)"
fi

# Step 4: Build Frontend
echo "Step 4: Building frontend..."
cd ../frontend

if [ "$MODE" = "development" ]; then
    echo "Development mode: Skipping frontend build"
elif [ "$MODE" = "production" ]; then
    npm run build
    echo "Frontend build completed"
fi

# Step 5: Start Frontend Server
echo "Step 5: Starting frontend server..."

if [ "$MODE" = "development" ]; then
    # Development mode
    npm run dev &
    FRONTEND_PID=$!
    echo "Frontend development server started (PID: $FRONTEND_PID)"
    
elif [ "$MODE" = "production" ]; then
    # Production mode - serve with nginx or node
    if command -v nginx &> /dev/null; then
        # Use nginx if available
        sudo cp -r dist/* /var/www/html/ 2>/dev/null || echo "Warning: Could not copy to nginx directory"
        sudo nginx -s reload 2>/dev/null || echo "Warning: Could not reload nginx"
        echo "Frontend served via nginx"
    else
        # Use node serve
        npm install -g serve
        serve -s dist -l $FRONTEND_PORT &
        FRONTEND_PID=$!
        echo "Frontend served via node (PID: $FRONTEND_PID)"
    fi
fi

# Step 6: Run Tests
echo "Step 6: Running tests..."
cd ../backend

if [ "$MODE" = "development" ]; then
    echo "Running comprehensive tests..."
    python3 run_all_tests.py
    
    if [ $? -eq 0 ]; then
        echo "All tests passed!"
    else
        echo "Some tests failed - check the output above"
    fi
else
    echo "Production mode: Skipping tests (run manually if needed)"
fi

# Step 7: Display Deployment Information
echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Services Status:"
echo "  Backend: http://localhost:$BACKEND_PORT"
echo "  Frontend: http://localhost:$FRONTEND_PORT"
echo "  API Docs: http://localhost:$BACKEND_PORT/docs"
echo ""
echo "Default Admin Account:"
echo "  Email: admin@myle.com"
echo "  Password: admin123"
echo ""
echo "Available Routes:"
echo "  Dashboard: http://localhost:$FRONTEND_PORT/dashboard"
echo "  Training: http://localhost:$FRONTEND_PORT/dashboard/training"
echo "  Pipeline: http://localhost:$FRONTEND_PORT/dashboard/pipeline"
echo "  Analytics: http://localhost:$FRONTEND_PORT/dashboard/analytics"
echo "  Settings: http://localhost:$FRONTEND_PORT/dashboard/settings/profile"
echo "  Wallet: http://localhost:$FRONTEND_PORT/dashboard/finance/wallet"
echo ""
echo "Process IDs:"
echo "  Backend PID: $BACKEND_PID"
if [ ! -z "$FRONTEND_PID" ]; then
    echo "  Frontend PID: $FRONTEND_PID"
fi
echo ""
echo "To stop services:"
echo "  kill $BACKEND_PID"
if [ ! -z "$FRONTEND_PID" ]; then
    echo "  kill $FRONTEND_PID"
fi
echo ""
echo "To view logs:"
echo "  Backend: Check terminal output or use journalctl (systemd)"
echo "  Frontend: Check browser console or npm logs"
echo ""

# Save PIDs to file for cleanup
echo "$BACKEND_PID" > .backend_pid
if [ ! -z "$FRONTEND_PID" ]; then
    echo "$FRONTEND_PID" > .frontend_pid
fi

echo "Deployment information saved to .backend_pid and .frontend_pid"
echo ""
echo "=== Ready to Use Myle Dashboard ==="
