# Deployment Guide

**Classification**: Internal Use Only  
**Last Updated**: 2026-08-24

---

## 1. System Requirements

### 1.1 Hardware

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **CPU** | 2 cores | 4+ cores |
| **RAM** | 4 GB | 8+ GB |
| **Storage** | 10 GB | 50+ GB |
| **Network** | 100 Mbps | 1 Gbps |

### 1.2 Software

| Component | Version |
|-----------|---------|
| **Python** | 3.12+ |
| **Node.js** | 24.x |
| **MongoDB** | 6.0+ (Atlas recommended) |
| **Supabase** | Latest |
| **Git** | 2.30+ |

---

## 2. Production Deployment

### 2.1 Infrastructure Options

| Option | Use Case |
|--------|----------|
| **Cloud VM** | Full control, custom configuration |
| **Container (Docker/K8s)** | Scalable, portable |
| **PaaS (Heroku/Railway)** | Quick deployment, managed |
| **Air-gapped** | Maximum security, classified networks |

### 2.2 Cloud MongoDB Setup

1. Create MongoDB Atlas cluster
2. Create database user with least-privilege access
3. Whitelist deployment IPs
4. Enable TLS enforcement
5. Update `MONGO_URL` in `.env`

### 2.3 Supabase Setup (Optional)

1. Create Supabase project
2. Enable Row Level Security
3. Configure JWKS endpoint
4. Update environment variables:
   ```bash
   SUPABASE_URL=https://xxx.supabase.co
   SUPABASE_JWKS_URL=https://xxx.supabase.co/auth/v1/.well-known/jwks.json
   SUPABASE_SECRET_KEY=sb_secret_xxx
   ```

---

## 3. Environment Configuration

### 3.1 Required Variables

Create `backend/.env`:

```bash
# Database
MONGO_URL=mongodb://user:pass@cluster.mongodb.net:27017/dbname?ssl=true
DB_NAME=DP3

# Application
CORS_ORIGINS="https://yourdomain.com"
APP_URL=https://yourdomain.com

# Authentication
JWT_SECRET=<64-char-hex-secret>
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_PASSWORD=<strong-password>

# Model API
MODEL_API_KEY=<openai-compatible-key>
MODEL_API_URL=https://api.example.com/v1
MODEL_NAME=agnes-2.5-flash

# Supabase (optional)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_JWKS_URL=https://xxx.supabase.co/auth/v1/.well-known/jwks.json
SUPABASE_SECRET_KEY=sb_secret_xxx
```

### 3.2 Security Requirements

- **JWT_SECRET**: Minimum 64 characters, hex-only
- **MONGO_URL**: Must include `?ssl=true`
- **CORS_ORIGINS**: Restrict to production domain(s)
- **ADMIN_PASSWORD**: Meet complexity requirements

---

## 4. Deployment Steps

### 4.1 Clone Repository

```bash
git clone https://github.com/smartscott-LLC/Dimensions.git
cd Dimensions
```

### 4.2 Install Dependencies

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd ../frontend
pnpm install
```

### 4.3 Configure Environment

```bash
cd ../backend
cp .env.example .env  # If template exists
# Edit .env with production values
nano .env
```

### 4.4 Initialize Database

```bash
# Seed demo data
python seed.py
```

### 4.5 Start Services

```bash
# Backend
uvicorn server:app --host 0.0.0.0 --port 8001 --workers 4

# Frontend
pnpm build
# Serve with nginx or similar
```

---

## 5. Container Deployment

### 5.1 Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8001:8001"
    env_file:
      - ./backend/.env
    depends_on:
      - mongo
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    restart: unless-stopped

  mongo:
    image: mongo:6
    ports:
      - "27017:27017"
    volumes:
      - mongo-data:/data/db
    restart: unless-stopped

volumes:
  mongo-data:
```

### 5.2 Build and Run

```bash
docker-compose up -d
docker-compose logs -f
```

---

## 6. Reverse Proxy Configuration

### 6.1 Nginx

```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /api {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
    }
}
```

### 6.2 Apache

```apache
<VirtualHost *:443>
    ServerName yourdomain.com
    
    SSLEngine on
    SSLCertificateFile /path/to/cert.pem
    SSLCertificateKeyFile /path/to/key.pem
    
    ProxyPass /api http://localhost:8001
    ProxyPassReverse /api http://localhost:8001
    
    ProxyPass / http://localhost:3000
    ProxyPassReverse / http://localhost:3000
</VirtualHost>
```

---

## 7. Monitoring & Logging

### 7.1 Health Checks

```bash
# Backend
curl -s https://yourdomain.com/api/health

# Frontend
curl -s -o /dev/null -w "%{http_code}" https://yourdomain.com
```

### 7.2 Log Aggregation

Configure centralized logging:
- Backend: `/var/log/supervisor/backend.*.log`
- Frontend: `/var/log/supervisor/frontend.*.log`
- MongoDB: Atlas logs or local mongod.log

### 7.3 Metrics

Track these KPIs:
- Authentication success/failure rates
- Rate limit hits
- API key usage
- Event verification latency
- Polytope violation rates

---

## 8. Backup & Recovery

### 8.1 MongoDB Backup

```bash
# Full backup
mongodump --uri="MONGO_URL" --out=/backup/$(date +%Y%m%d)

# Restore
mongorestore --uri="MONGO_URL" /backup/20260824
```

### 8.2 Configuration Backup

```bash
# Backup .env (exclude from git!)
tar -czvf config-backup-$(date +%Y%m%d).tar.gz backend/.env

# Restore
tar -xzvf config-backup-20260824.tar.gz
```

---

## 9. Security Hardening

### 9.1 Firewall Rules

```bash
# Allow only necessary ports
ufw allow 22/tcp    # SSH
ufw allow 443/tcp   # HTTPS
ufw deny 8001/tcp   # Block direct backend access
ufw deny 3000/tcp   # Block direct frontend access
ufw enable
```

### 9.2 System Hardening

```bash
# Disable unused services
systemctl disable bluetooth
systemctl disable cups

# Enable automatic security updates
apt-get install unattended-upgrades
systemctl enable unattended-upgrades
```

### 9.3 File Permissions

```bash
# Secure .env
chmod 600 backend/.env

# Secure code
chmod 755 backend/server.py
chmod 644 backend/**/*.py
```

---

## 10. Troubleshooting

### 10.1 Common Issues

**Backend won't start**:
```bash
# Check syntax
python -m py_compile server.py

# Check dependencies
pip list | grep fastapi

# Check .env
cat .env | grep JWT_SECRET
```

**Frontend blank page**:
```bash
# Check build
pnpm build

# Check types
pnpm typecheck
```

**MongoDB connection failed**:
```bash
# Test connection
mongo "MONGO_URL" --eval "db.adminCommand('ping')"

# Check network
nc -zv cluster.mongodb.net 27017
```

### 10.2 Performance Tuning

**MongoDB**:
```javascript
// Add indexes
db.events.createIndex({created_at: -1})
db.events.createIndex({profile_id: 1, created_at: -1})
db.login_attempts.createIndex({ip: 1, timestamp: -1})
```

**Uvicorn**:
```bash
# Increase workers for load
uvicorn server:app --host 0.0.0.0 --port 8001 --workers 4
```

---

## 11. Compliance Checklist

- [ ] All default passwords changed
- [ ] JWT_SECRET rotated to secure value
- [ ] MongoDB connection uses TLS
- [ ] CORS restricted to production domains
- [ ] HTTPS enforced
- [ ] Firewall configured
- [ ] Logging enabled
- [ ] Backup strategy implemented
- [ ] Monitoring configured
- [ ] Incident response plan documented

---

**Document Status**: Production-ready  
**Next Review**: After first production incident or quarterly
