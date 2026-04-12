#!/bin/bash

# Myle Dashboard Environment Setup Script
# This script sets up the complete development environment

set -e

echo "=== Myle Dashboard Environment Setup ==="
echo "Setting up development environment for all 5 phases..."

# Check if we're on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Detected macOS system"
    
    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        echo "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    else
        echo "Homebrew already installed"
    fi
    
    # Install PostgreSQL
    if ! command -v postgres &> /dev/null; then
        echo "Installing PostgreSQL..."
        brew install postgresql@14
        brew services start postgresql@14
    else
        echo "PostgreSQL already installed"
        brew services start postgresql@14 || true
    fi
    
    # Install Redis (optional but recommended)
    if ! command -v redis-server &> /dev/null; then
        echo "Installing Redis..."
        brew install redis
        brew services start redis || true
    else
        echo "Redis already installed"
        brew services start redis || true
    fi
    
    # Install Node.js if not present
    if ! command -v node &> /dev/null; then
        echo "Installing Node.js..."
        brew install node
    else
        echo "Node.js already installed"
    fi
    
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Detected Linux system"
    
    # Ubuntu/Debian
    if command -v apt-get &> /dev/null; then
        echo "Installing dependencies with apt..."
        sudo apt-get update
        sudo apt-get install -y postgresql postgresql-contrib redis-server nodejs npm python3 python3-pip python3-venv
        
        # Start PostgreSQL
        sudo systemctl start postgresql
        sudo systemctl enable postgresql
        
        # Start Redis
        sudo systemctl start redis-server
        sudo systemctl enable redis-server
        
    # CentOS/RHEL
    elif command -v yum &> /dev/null; then
        echo "Installing dependencies with yum..."
        sudo yum install -y postgresql-server redis nodejs npm python3 python3-pip
        
        # Initialize PostgreSQL
        sudo postgresql-setup initdb
        sudo systemctl start postgresql
        sudo systemctl enable postgresql
        
        # Start Redis
        sudo systemctl start redis
        sudo systemctl enable redis
    fi
else
    echo "Unsupported operating system: $OSTYPE"
    echo "Please install PostgreSQL, Redis, Node.js, and Python manually"
    exit 1
fi

# Create database
echo "Setting up database..."
if command -v createdb &> /dev/null; then
    # Try to create database (might fail if user doesn't exist, that's OK)
    createdb myle_dashboard 2>/dev/null || echo "Database creation skipped (might need user setup)"
else
    echo "createdb command not found, will create database manually"
fi

# Setup Python virtual environment
echo "Setting up Python environment..."
cd backend
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate virtual environment and install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Setup frontend dependencies
echo "Setting up frontend..."
cd ../frontend
npm install

# Create environment files
echo "Creating environment files..."

# Backend .env
cd ../backend
if [ ! -f ".env" ]; then
    cat > .env << EOF
# Database Configuration
DATABASE_URL=postgresql://postgres:password@localhost/myle_dashboard

# Redis Configuration (optional)
REDIS_URL=redis://localhost:6379

# Security
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# File Storage
UPLOAD_DIR=./uploads
MAX_UPLOAD_SIZE=10485760

# Email Configuration (optional)
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=your-email@gmail.com
# SMTP_PASSWORD=your-app-password
EOF
    echo "Created backend/.env file"
else
    echo "Backend .env file already exists"
fi

# Frontend .env
cd ../frontend
if [ ! -f ".env" ]; then
    cat > .env << EOF
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_NAME=Myle Dashboard
VITE_VERSION=1.0.0
EOF
    echo "Created frontend/.env file"
else
    echo "Frontend .env file already exists"
fi

echo ""
echo "=== Environment Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Start PostgreSQL service (if not already running)"
echo "2. Create database and user if needed"
echo "3. Run database migrations"
echo "4. Start backend server"
echo "5. Start frontend development server"
echo ""
echo "Commands:"
echo "  # Backend"
echo "  cd backend"
echo "  source venv/bin/activate"
echo "  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "  # Frontend (new terminal)"
echo "  cd frontend"
echo "  npm run dev"
echo ""
echo "  # Run tests (new terminal)"
echo "  cd backend"
echo "  python3 run_all_tests.py"
