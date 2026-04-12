# Myle Dashboard Deployment Guide

## Overview

This guide covers deploying the Myle Dashboard from Flask to FastAPI/React. The migration includes 5 complete phases with modern architecture, comprehensive testing, and production-ready features.

## System Requirements

### Backend (FastAPI)
- Python 3.12+
- PostgreSQL 14+
- Redis 6+ (for caching/sessions)
- Node.js 18+ (for frontend build)

### Frontend (React)
- Node.js 18+
- npm or yarn
- Modern browser support

### Infrastructure
- Docker (recommended)
- SSL certificate
- Load balancer (optional)
- File storage (for uploads)

## Architecture

```
Frontend (React) -> Backend (FastAPI) -> Database (PostgreSQL)
                     -> Cache (Redis)
                     -> Storage (File System/S3)
```

## Phase 1: Training System

### Features
- 7-day training certification pipeline
- Calendar enforcement and scheduling
- Training progress tracking
- Certificate generation

### Components
- `TrainingSurfaceService` - Business logic
- `CertificateService` - Certificate management
- `/api/v1/training/*` - API endpoints
- `TrainingPage.tsx` - React frontend

### Database Tables
- `training_modules`
- `user_training_progress` 
- `certificates`
- `training_calendar`

## Phase 2: Lead Pipeline

### Features
- 13-stage kanban board pipeline
- Role-based lead management
- Status transition validation
- Payment proof upload system
- Auto-expiry and retarget logic

### Components
- `PipelineService` - Pipeline business logic
- `PaymentService` - Payment management
- `/api/v1/pipeline/*` - Pipeline API
- `/api/v1/payments/*` - Payment API
- `PipelinePage.tsx` - Kanban interface

### Pipeline Stages
1. New Lead
2. Contacted
3. Invited
4. Video Sent
5. Video Watched
6. Paid (Payment Required: 19600 cents)
7. Day 1
8. Day 2
9. Interview
10. Track Selected
11. Seat Hold
12. Converted

## Phase 3: Wallet System

### Features
- Ledger-based wallet system
- Lead claiming with wallet deduction
- Recharge request approval workflow
- Transaction history and analytics
- Balance validation

### Components
- `WalletService` - Wallet business logic
- `/api/v1/wallet/*` - Wallet API
- `/api/v1/wallet-enhanced/*` - Enhanced API
- `WalletPage.tsx` - Wallet interface

### Database Tables
- `wallet_ledger_entries` (append-only)
- `wallet_recharges` (approval workflow)

## Phase 4: Reports & Analytics

### Features
- Team performance analytics
- Individual performance tracking
- Performance leaderboard
- System overview for admins
- Daily trends analysis
- Export functionality

### Components
- `AnalyticsService` - Analytics business logic
- `/api/v1/analytics/*` - Analytics API
- `AnalyticsPage.tsx` - Analytics dashboard

### Metrics Tracked
- Call pickup rates
- Conversion rates
- Payment completion
- Training progress
- Wallet activity

## Phase 5: System Settings

### Features
- User profile management
- Notification preferences
- System configuration
- Security settings
- Audit logging
- Role-based access control

### Components
- `SettingsService` - Settings business logic
- `/api/v1/settings-enhanced/*` - Settings API
- `SettingsPage.tsx` - Settings interface

### Database Tables
- `app_settings` (key-value store)
- `user_preferences` (notification settings)
- `audit_log` (activity tracking)

## Deployment Steps

### 1. Environment Setup

```bash
# Clone repository
git clone <repository-url>
cd myle-vl2

# Backend setup
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install
```

### 2. Database Setup

```bash
# Create PostgreSQL database
createdb myle_dashboard

# Run migrations (if using Alembic)
cd backend
alembic upgrade head

# Or create tables manually
python3 -c "
from app.db.base import Base
from app.db.session import engine
Base.metadata.create_all(bind=engine)
print('Database tables created')
"
```

### 3. Environment Configuration

Create `.env` file in backend directory:

```env
# Database
DATABASE_URL=postgresql://username:password@localhost/myle_dashboard

# Redis (optional)
REDIS_URL=redis://localhost:6379

# Security
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# File Storage
UPLOAD_DIR=./uploads
MAX_UPLOAD_SIZE=10485760  # 10MB

# Email (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### 4. Frontend Configuration

Create `.env` file in frontend directory:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_NAME=Myle Dashboard
VITE_VERSION=1.0.0
```

### 5. Build Frontend

```bash
cd frontend
npm run build
```

### 6. Backend Deployment

```bash
cd backend

# Option 1: Direct run
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Option 2: Production with Gunicorn
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Option 3: Docker
docker build -t myle-backend .
docker run -p 8000:8000 myle-backend
```

### 7. Frontend Deployment

```bash
cd frontend

# Option 1: Serve with nginx
cp -r dist/* /var/www/html/

# Option 2: Serve with Node.js
npm run preview

# Option 3: Docker
docker build -t myle-frontend .
docker run -p 3000:80 myle-frontend
```

## Docker Deployment

### Backend Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend Dockerfile

```dockerfile
FROM node:18-alpine as build

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:14
    environment:
      POSTGRES_DB: myle_dashboard
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:6-alpine
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql://postgres:password@postgres/myle_dashboard
      REDIS_URL: redis://redis:6379
    depends_on:
      - postgres
      - redis
    ports:
      - "8000:8000"

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

volumes:
  postgres_data:
```

## Testing

### Run All Tests

```bash
cd backend
python3 run_all_tests.py
```

### Individual Phase Tests

```bash
python3 test_training_system.py
python3 test_pipeline_system.py
python3 test_wallet_system.py
python3 test_analytics_system.py
python3 test_settings_system.py
```

### Frontend Tests

```bash
cd frontend
npm run test
npm run lint
npm run type-check
```

## Monitoring & Logging

### Application Logging

Configure logging in backend:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
```

### Health Checks

```bash
# Backend health
curl http://localhost:8000/health

# Frontend health
curl http://localhost:3000
```

## Security Considerations

1. **Environment Variables**: Never commit secrets to repository
2. **Database Security**: Use strong passwords and SSL
3. **API Security**: Enable CORS, rate limiting, authentication
4. **File Uploads**: Validate file types and sizes
5. **HTTPS**: Use SSL certificates in production
6. **Dependencies**: Regularly update packages

## Performance Optimization

### Backend
- Database indexing on frequently queried columns
- Redis caching for expensive operations
- Connection pooling for database
- Async operations for I/O bound tasks

### Frontend
- Code splitting and lazy loading
- Image optimization
- Bundle size optimization
- Service worker for offline support

## Backup & Recovery

### Database Backup

```bash
# Manual backup
pg_dump myle_dashboard > backup_$(date +%Y%m%d).sql

# Automated backup (cron)
0 2 * * * pg_dump myle_dashboard > /backups/myle_$(date +\%Y\%m\%d).sql
```

### File Backup

```bash
# Backup uploads
tar -czf uploads_backup_$(date +%Y%m%d).tar.gz uploads/
```

## Troubleshooting

### Common Issues

1. **Database Connection**: Check PostgreSQL is running and credentials are correct
2. **Port Conflicts**: Ensure ports 8000 and 3000 are available
3. **Permission Issues**: Check file permissions for uploads directory
4. **Memory Issues**: Monitor memory usage, adjust container limits
5. **CORS Issues**: Configure CORS settings for frontend domain

### Debug Mode

```bash
# Backend debug mode
uvicorn app.main:app --reload --log-level debug

# Frontend debug mode
npm run dev
```

## Scaling Considerations

### Horizontal Scaling
- Load balancer for multiple backend instances
- Database read replicas
- CDN for static assets
- Session storage in Redis

### Vertical Scaling
- Increase server resources
- Database optimization
- Caching strategies

## Maintenance

### Regular Tasks
- Monitor system performance
- Update dependencies
- Review logs for errors
- Backup data regularly
- Security audits

### Updates
- Test updates in staging environment
- Plan for zero-downtime deployments
- Rollback procedures

## Support

For issues with:
- **Backend**: Check application logs and database connectivity
- **Frontend**: Check browser console and network requests
- **Database**: Check PostgreSQL logs and connection pool
- **Infrastructure**: Check system resources and network connectivity

## Version History

- **v1.0.0**: Complete migration from Flask to FastAPI/React
  - All 5 phases implemented
  - Comprehensive testing suite
  - Production-ready deployment
  - Modern architecture and best practices
